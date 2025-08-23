#!/usr/bin/env python3
"""
Test script for teacher view aligned DOCX export.
"""
import os
import sys
import tempfile
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app.schemas.evaluation import EvaluationResult, Meta, TextBlock, Scores, RubricScore
from app.reporting.docx_renderer import render_essay_docx


def create_sample_evaluation() -> EvaluationResult:
    """Create sample evaluation data for testing"""
    
    meta = Meta(
        student="左子恒",
        topic="写读后感——实用-学术类设计",
        date="2025-08-23",
        class_="五年级一班", 
        teacher="张老师"
    )
    
    # Sample scoring data
    rubrics = [
        RubricScore(name="内容理解", score=8, max=10, weight=1.0, reason="对文本理解较好"),
        RubricScore(name="结构组织", score=7, max=10, weight=1.0, reason="结构清晰但转换略生硬"),
        RubricScore(name="语言表达", score=9, max=10, weight=1.0, reason="语言流畅生动"),
        RubricScore(name="文采创新", score=9, max=10, weight=1.0, reason="用词精准，有创意")
    ]
    
    scores = Scores(total=33, rubrics=rubrics)
    
    text_block = TextBlock(
        original="这是原始的作文内容...",
        cleaned="这是经过教师修改的作文内容，文字更加规范，表达更加清晰。通过阅读《西游记》，我深深被孙悟空的勇敢和智慧所感动..."
    )
    
    # Sample AI enhanced content
    outline = [
        {"index": 1, "intention": "开篇点题与背景介绍"},
        {"index": 2, "intention": "描述'三打白骨精'情节并分析人物性格"},
        {"index": 3, "intention": "总结感悟和启发"}
    ]
    
    diagnoses = [
        {
            "id": 1,
            "target": "第1段",
            "evidence": "开头过于简单，缺乏吸引力",
            "suggestions": ["增加背景描述", "使用设问句引入"]
        },
        {
            "id": 2, 
            "target": "第2段",
            "evidence": "情节描述不够生动",
            "suggestions": ["添加细节描写", "运用修辞手法"]
        }
    ]
    
    personalized_practices = [
        {"title": "段落开头练习", "requirement": "练习写3种不同的段落开头方式"},
        {"title": "细节描写训练", "requirement": "选择一个场景，用200字进行细节描写"},
        {"title": "修辞手法运用", "requirement": "在作文中至少使用3种修辞手法"}
    ]
    
    summary_data = {
        "problemSummary": "主要问题集中在段落开头的吸引力不够和情节描述的生动性有待提高", 
        "improvementPlan": "通过加强开头技巧训练和细节描写练习来改进",
        "expectedOutcome": "预期能在文章开头和情节描述方面有明显提升"
    }
    
    return EvaluationResult(
        meta=meta,
        text=text_block,
        scores=scores,
        highlights=[],
        diagnosis=None,
        
        # Teacher-view aligned fields
        assignmentTitle="写读后感——实用-学术类设计",
        studentName="左子恒",
        submittedAt="2025-08-23 09:16:36",
        currentEssayContent="经过教师修改的作文内容：\n\n这是一篇关于《西游记》的读后感。通过阅读'三打白骨精'这一经典情节，我深深被孙悟空的勇敢和智慧所感动。\n\n在这个故事中，白骨精三次变化，企图欺骗唐僧。但孙悟空凭借火眼金睛识破了她的伪装。这让我明白了在生活中要保持清醒的头脑，不被表面现象迷惑。\n\n读完这个故事，我觉得我们都应该像孙悟空一样，面对困难要勇敢，面对诱惑要保持清醒。",
        
        # AI enhanced content
        outline=outline,
        diagnoses=diagnoses,
        personalizedPractices=personalized_practices,
        summaryData=summary_data,
        parentSummary="左子恒同学的这篇读后感结构清晰，对名著内容理解较好。建议在开头和细节描写方面加强练习，相信会有更大进步。",
        
        # Additional fields
        overall_comment="这是一篇结构清晰的读后感，体现了对名著的深度思考。开头略显平淡，建议增加吸引力。",
        strengths=["对文本理解准确", "结构层次清晰", "语言表达流畅", "观点表达明确"],
        improvements=["开头可以更有吸引力", "增加具体的情节细节", "加强修辞手法的运用", "结尾可以更有感染力"]
    )


def test_render():
    """Test rendering functionality"""
    print("创建测试数据...")
    evaluation = create_sample_evaluation()
    
    print("开始渲染DOCX...")
    try:
        output_path = render_essay_docx(evaluation)
        print(f"✅ DOCX渲染成功: {output_path}")
        
        # Check file exists and has content
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ 文件大小: {file_size} bytes")
            return output_path
        else:
            print("❌ 文件未生成")
            return None
            
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=== 教师视图对齐的DOCX导出测试 ===")
    result = test_render()
    if result:
        print(f"\n📄 可以查看生成的文档: {result}")
    else:
        print("\n❌ 测试失败")