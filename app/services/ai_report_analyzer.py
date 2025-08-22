import json
import requests
from flask import current_app
from app.extensions import db
from app.models import Essay, EssayAssignment, StudentProfile, User, Enrollment
from sqlalchemy import func
from collections import defaultdict, Counter
import statistics

class AIReportError(Exception):
    """Custom exception for AI report analysis errors."""
    pass

def analyze_assignment_with_ai(assignment_id: int) -> dict:
    """
    使用AI分析作业的整体情况，生成作业报告数据
    
    Args:
        assignment_id: 作业ID
        
    Returns:
        包含AI分析结果的字典
        
    Raises:
        AIReportError: AI分析服务连接或处理错误
    """
    try:
        # 获取作业基本信息
        assignment = db.session.get(EssayAssignment, assignment_id)
        if not assignment:
            raise AIReportError(f"作业 {assignment_id} 不存在")
            
        # 获取所有已评分的作文（包括AI评分和教师评分）
        essays = db.session.query(Essay).filter(
            Essay.assignment_id == assignment_id,
            db.or_(
                Essay.ai_score.isnot(None),
                Essay.final_score.isnot(None)
            )
        ).all()
        
        if not essays:
            raise AIReportError("没有找到已评分的作文")
            
        # 收集数据用于AI分析
        analysis_data = _collect_assignment_data(assignment, essays)
        
        # 构建AI分析prompt
        prompt = _build_analysis_prompt(analysis_data)
        
        # 调用AI服务
        ai_result = _call_ai_analysis_service(prompt)
        
        # 解析AI返回结果
        report_data = _parse_ai_analysis_result(ai_result)
        
        # 添加统计数据（传递AI分析结果用于生成准确的图表数据）
        report_data.update(_calculate_statistics(assignment, essays, report_data))
        
        return report_data
        
    except Exception as e:
        current_app.logger.error(f"AI作业报告分析失败: {e}")
        raise AIReportError(f"AI分析失败: {str(e)}")

def _collect_assignment_data(assignment, essays):
    """收集作业相关数据用于AI分析"""
    data = {
        'assignment_info': {
            'title': assignment.title,
            'description': assignment.description,
            'total_score': assignment.grading_standard.total_score,
            'dimensions': []
        },
        'essays_data': [],
        'statistics': {}
    }
    
    # 收集评分标准维度信息
    for dim in assignment.grading_standard.dimensions:
        data['assignment_info']['dimensions'].append({
            'name': dim.name,
            'max_score': dim.max_score
        })
    
    # 收集作文数据
    for essay in essays:
        essay_data = {
            'essay_id': essay.id,  # 添加essay_id用于AI引用
            'student_name': essay.enrollment.student.user.full_name or essay.enrollment.student.user.username,
            'content': essay.content[:1000] if essay.content else '',  # 增加长度限制以提供更多上下文
            'full_content': essay.content if essay.content else '',  # 提供完整内容用于AI分析
            'final_score': essay.final_score,
            'ai_score_data': None,
            'word_count': len(essay.content) if essay.content else 0
        }
        
        # 获取AI评分数据
        if essay.ai_score:
            # ai_score字段在数据库中是JSON类型，SQLAlchemy已自动解析为字典
            essay_data['ai_score_data'] = essay.ai_score
                
        data['essays_data'].append(essay_data)
    
    return data

def _build_analysis_prompt(data):
    """构建AI分析的prompt"""
    prompt = f"""
你是一位资深的语文教学专家和数据分析师。请基于以下作业数据，生成一份全面的作业分析报告。

作业信息：
- 标题：{data['assignment_info']['title']}
- 描述：{data['assignment_info']['description']}
- 总分：{data['assignment_info']['total_score']}
- 评分维度：{', '.join([d['name'] for d in data['assignment_info']['dimensions']])}

学生作文数据：
共{len(data['essays_data'])}篇作文

请分析以下方面并返回JSON格式结果：
1. 班级共性问题分析（语法错误、逻辑不清、词汇不足等）
2. 优秀作文特点总结
3. 需要改进的问题分类
4. 各维度表现分析
5. 教学建议

**重要要求：**
- 对于每个问题类型，必须提供具体的学生姓名、问题句子和句子在作文中的位置
- 对于每个优秀特点，必须提供具体的学生姓名、优秀句子和句子位置
- 示例文本必须是作文中的原文片段，不能是概括性描述

你的回答必须是一个完整的JSON对象，格式如下：
{{
  "common_issues": [
    {{
      "type": "语法错误",
      "description": "具体问题描述",
      "examples": ["示例1", "示例2"],
      "percentage": 65.5,
      "suggestions": "改进建议",
      "detailed_examples": [
        {{
          "student_name": "张三",
          "essay_id": 123,
          "problem_sentence": "我和朋友们一起去了公园玩耍，我们玩的很开心。",
          "sentence_position": "第2段第1句",
          "problem_explanation": "句子结构重复，缺乏变化"
        }}
      ]
    }}
  ],
  "excellent_features": [
    {{
      "feature": "特点名称",
      "description": "详细描述",
      "examples": ["优秀示例"],
      "detailed_examples": [
        {{
          "student_name": "李四",
          "essay_id": 124,
          "excellent_sentence": "夕阳西下，金色的光芒洒在湖面上，波光粼粼，如同撒了一地的碎金。",
          "sentence_position": "第3段第2句",
          "excellence_explanation": "运用比喻修辞，描写生动形象"
        }}
      ]
    }}
  ],
  "dimension_analysis": [
    {{
      "dimension_name": "维度名称",
      "average_performance": "良好",
      "strengths": "优势描述",
      "weaknesses": "不足描述",
      "improvement_suggestions": "改进建议"
    }}
  ],
  "teaching_suggestions": [
    "教学建议1",
    "教学建议2"
  ],
  "overall_summary": "整体评价总结"
}}

作文详细数据：
{json.dumps(data['essays_data'], ensure_ascii=False, indent=2)}
"""
    return prompt

def _call_ai_analysis_service(prompt):
    """调用AI分析服务"""
    try:
        api_key = current_app.config.get('DEEPSEEK_API_KEY')
        api_url = current_app.config.get('DEEPSEEK_API_URL')
        
        if not api_key or not api_url:
            raise AIReportError("DeepSeek API配置缺失")
            
        payload = {
            "model": current_app.config.get('DEEPSEEK_MODEL_CHAT'),
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(api_url, headers=headers, 
                               data=json.dumps(payload), timeout=120)
        response.raise_for_status()
        
        result = response.json()
        
        if "choices" in result and result["choices"]:
            return result["choices"][0]["message"]["content"].strip()
        else:
            raise AIReportError("AI服务返回格式错误")
            
    except requests.RequestException as e:
        raise AIReportError(f"AI服务请求失败: {e}")
    except Exception as e:
        raise AIReportError(f"AI服务调用异常: {e}")

def _parse_ai_analysis_result(ai_result):
    """解析AI分析结果"""
    try:
        # 尝试提取JSON部分
        if '```json' in ai_result:
            start = ai_result.find('```json') + 7
            end = ai_result.find('```', start)
            json_str = ai_result[start:end].strip()
        elif '{' in ai_result and '}' in ai_result:
            start = ai_result.find('{')
            end = ai_result.rfind('}') + 1
            json_str = ai_result[start:end]
        else:
            json_str = ai_result
            
        return json.loads(json_str)
        
    except json.JSONDecodeError as e:
        current_app.logger.error(f"AI分析结果JSON解析失败: {e}")
        current_app.logger.error(f"原始结果: {ai_result}")
        raise AIReportError("AI分析结果格式错误")

def _calculate_statistics(assignment, essays, ai_report_data=None):
    """计算统计数据"""
    scores = [essay.final_score for essay in essays if essay.final_score]
    word_counts = [len(essay.content) if essay.content else 0 for essay in essays]
    
    # 维度得分统计
    dimension_scores = defaultdict(list)
    for essay in essays:
        if essay.ai_score:
            # ai_score字段在数据库中已是JSON类型，SQLAlchemy自动解析为字典，无需json.loads
            ai_data = essay.ai_score
            if isinstance(ai_data, dict) and 'dimensions' in ai_data:
                for dim in ai_data['dimensions']:
                    dimension_scores[dim['dimension_name']].append(dim['score'])
    
    # 获取评分标准中的维度最大分数
    dimension_max_scores = {}
    for dim in assignment.grading_standard.dimensions:
        dimension_max_scores[dim.name] = dim.max_score
    
    # 计算各维度平均分
    dimension_averages = {}
    for dim_name, scores_list in dimension_scores.items():
        if scores_list:
            dimension_averages[dim_name] = {
                'average': round(statistics.mean(scores_list), 2),
                'max': max(scores_list),
                'min': min(scores_list),
                'max_possible': dimension_max_scores.get(dim_name, max(scores_list))
            }
    
    # 生成分数分布数据
    score_distribution = _calculate_score_distribution(scores, assignment.grading_standard.total_score)
    
    # 生成图表数据（传递AI分析结果）
    charts_data = _generate_charts_data(scores, dimension_averages, word_counts, assignment.grading_standard.total_score, ai_report_data)
    
    return {
        'basic_statistics': {
            'total_essays': len(essays),
            'average_score': round(statistics.mean(scores), 2) if scores else 0,
            'max_score': max(scores) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'total_possible_score': assignment.grading_standard.total_score,
            'average_word_count': round(statistics.mean(word_counts), 0) if word_counts else 0,
            'score_distribution': score_distribution
        },
        'dimension_statistics': dimension_averages,
        'top_essays': _get_top_essays(essays, 3),
        'bottom_essays': _get_bottom_essays(essays, 3),
        'charts': charts_data
    }

def _calculate_score_distribution(scores, total_score):
    """计算分数分布"""
    if not scores:
        return {}
        
    # 按百分比分段
    ranges = {
        '优秀(90-100%)': 0,
        '良好(80-89%)': 0,
        '中等(70-79%)': 0,
        '及格(60-69%)': 0,
        '不及格(<60%)': 0
    }
    
    for score in scores:
        percentage = (score / total_score) * 100
        if percentage >= 90:
            ranges['优秀(90-100%)'] += 1
        elif percentage >= 80:
            ranges['良好(80-89%)'] += 1
        elif percentage >= 70:
            ranges['中等(70-79%)'] += 1
        elif percentage >= 60:
            ranges['及格(60-69%)'] += 1
        else:
            ranges['不及格(<60%)'] += 1
            
    return ranges

def _get_top_essays(essays, limit):
    """获取最高分作文"""
    def get_essay_score(essay):
        """获取作文的有效分数"""
        if essay.final_score is not None:
            return essay.final_score
        
        # 尝试从AI评分中获取总分
        if essay.ai_score and isinstance(essay.ai_score, dict):
            return essay.ai_score.get('total_score', 0)
        
        return 0
    
    def get_student_name(essay):
        """安全地获取学生姓名"""
        try:
            if (essay.enrollment and 
                essay.enrollment.student_profile and 
                essay.enrollment.student_profile.name):
                return essay.enrollment.student_profile.name
            elif (essay.enrollment and 
                  essay.enrollment.student and 
                  essay.enrollment.student.user):
                return essay.enrollment.student.user.full_name or essay.enrollment.student.user.username
            return "未知"
        except AttributeError:
            return "未知"
    
    sorted_essays = sorted(essays, key=get_essay_score, reverse=True)
    return [{
        'essay_id': essay.id,
        'student_name': get_student_name(essay),
        'score': float(get_essay_score(essay)),
        'content_preview': (essay.content or "").strip()[:180] + "..." if essay.content and len(essay.content.strip()) > 180 else (essay.content or "").strip()
    } for essay in sorted_essays[:limit]]

def _get_bottom_essays(essays, limit):
    """获取最低分作文"""
    def get_essay_score(essay):
        """获取作文的有效分数"""
        if essay.final_score is not None:
            return essay.final_score
        
        # 尝试从AI评分中获取总分
        if essay.ai_score and isinstance(essay.ai_score, dict):
            return essay.ai_score.get('total_score', 0)
        
        return 0
    
    def get_student_name(essay):
        """安全地获取学生姓名"""
        try:
            if (essay.enrollment and 
                essay.enrollment.student_profile and 
                essay.enrollment.student_profile.name):
                return essay.enrollment.student_profile.name
            elif (essay.enrollment and 
                  essay.enrollment.student and 
                  essay.enrollment.student.user):
                return essay.enrollment.student.user.full_name or essay.enrollment.student.user.username
            return "未知"
        except AttributeError:
            return "未知"
    
    sorted_essays = sorted(essays, key=get_essay_score)
    return [{
        'essay_id': essay.id,
        'student_name': get_student_name(essay),
        'score': float(get_essay_score(essay)),
        'content_preview': (essay.content or "").strip()[:180] + "..." if essay.content and len(essay.content.strip()) > 180 else (essay.content or "").strip()
    } for essay in sorted_essays[:limit]]

def _generate_charts_data(scores, dimension_averages, word_counts, total_score, ai_report_data=None):
    """生成图表数据"""
    # 分数分布图表数据
    score_distribution = _calculate_score_distribution(scores, total_score)
    score_chart_data = {
        'labels': list(score_distribution.keys()),
        'data': list(score_distribution.values())
    }
    
    # 维度雷达图数据（转换为百分比）
    dimension_labels = list(dimension_averages.keys())
    dimension_data = []
    for label in dimension_labels:
        avg_score = dimension_averages[label]['average']
        max_possible_score = dimension_averages[label]['max_possible']
        # 计算得分率百分比
        percentage = (avg_score / max_possible_score * 100) if max_possible_score > 0 else 0
        dimension_data.append(round(percentage, 1))
    
    dimension_chart_data = {
        'labels': dimension_labels,
        'data': dimension_data
    }
    
    # 问题类型分布（基于AI分析结果）
    if ai_report_data and 'common_issues' in ai_report_data:
        problem_types_labels = []
        problem_types_counts = []
        
        for issue in ai_report_data['common_issues']:
            problem_types_labels.append(issue['type'])
            # 使用detailed_examples的实际数量而不是percentage
            actual_count = len(issue.get('detailed_examples', []))
            problem_types_counts.append(actual_count)
        
        problem_types_data = {
            'labels': problem_types_labels,
            'data': problem_types_counts
        }
    else:
        # 如果没有AI数据，使用空数据
        problem_types_data = {
            'labels': [],
            'data': []
        }
    
    # 字数分布图表数据
    if word_counts:
        # 按字数范围分组
        word_ranges = {
            '0-200字': 0,
            '200-400字': 0,
            '400-600字': 0,
            '600-800字': 0,
            '800字以上': 0
        }
        
        for count in word_counts:
            if count <= 200:
                word_ranges['0-200字'] += 1
            elif count <= 400:
                word_ranges['200-400字'] += 1
            elif count <= 600:
                word_ranges['400-600字'] += 1
            elif count <= 800:
                word_ranges['600-800字'] += 1
            else:
                word_ranges['800字以上'] += 1
        
        word_count_chart_data = {
            'labels': list(word_ranges.keys()),
            'data': list(word_ranges.values())
        }
    else:
        word_count_chart_data = {
            'labels': [],
            'data': []
        }
    
    return {
        'score_distribution': score_chart_data,
        'dimension_radar': dimension_chart_data,
        'problem_types': problem_types_data,
        'word_count': word_count_chart_data
    }