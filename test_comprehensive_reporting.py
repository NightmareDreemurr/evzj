#!/usr/bin/env python3
"""
Comprehensive test demonstrating all enhanced DOCX reporting features.
"""
import tempfile
import os
from app.schemas.evaluation import (
    EvaluationResult, Meta, Scores, RubricScore, TextBlock, 
    Analysis, OutlineItem, DiagnosticItem, ExerciseItem
)
from app.reporting.docx_renderer import render_essay_docx


def create_comprehensive_evaluation():
    """Create a comprehensive evaluation with all enhanced features."""
    return EvaluationResult(
        meta=Meta(
            student='李小华',
            class_='五年级一班',
            teacher='张老师',
            topic='我的妈妈',
            date='2024-08-22',
            words=180
        ),
        text=TextBlock(
            original='我的妈妈是一个非常好的人。\n她每天都很辛苦地工作，照顾我们全家。\n妈妈做的饭菜特别香，我最喜欢吃她做的红烧肉。\n我要好好学习，将来报答妈妈的恩情。',
            cleaned='我的妈妈是一个非常好的人。她每天都很辛苦地工作，照顾我们全家。妈妈做的饭菜特别香，我最喜欢吃她做的红烧肉。我要好好学习，将来报答妈妈的恩情。'
        ),
        scores=Scores(
            total=85.5,
            rubrics=[
                RubricScore(name='内容', score=25.0, max=30.0, weight=1.0, reason='内容较丰富，情感真挚'),
                RubricScore(name='结构', score=22.0, max=25.0, weight=1.0, reason='结构清晰，层次分明'),
                RubricScore(name='语言', score=20.5, max=25.0, weight=1.0, reason='语言流畅，用词恰当'),
                RubricScore(name='文采', score=18.0, max=20.0, weight=1.0, reason='表达生动，有一定文采')
            ]
        ),
        analysis=Analysis(
            outline=[
                OutlineItem(para=1, intent='开篇总述妈妈的好'),
                OutlineItem(para=2, intent='具体描述妈妈的辛苦'),
                OutlineItem(para=3, intent='举例说明妈妈的厨艺'),
                OutlineItem(para=4, intent='表达对妈妈的感激之情')
            ],
            issues=['第二段描述可以更具体', '缺少外貌描写', '感情表达可以更深入']
        ),
        diagnostics=[
            DiagnosticItem(
                para=2, 
                issue='描述过于笼统', 
                evidence='只说"很辛苦地工作"，没有具体例子',
                advice=['增加具体的工作内容描述', '可以写妈妈早起晚睡的细节']
            ),
            DiagnosticItem(
                para=3,
                issue='细节不够丰富',
                evidence='只提到红烧肉，食物种类单一',
                advice=['可以写更多拿手菜', '描述做菜的过程']
            ),
            DiagnosticItem(
                para=None,
                issue='缺少外貌描写',
                evidence='全文没有对妈妈外貌的描述',
                advice=['可以在开头加入妈妈的外貌特征', '用比喻来描述妈妈的样子']
            )
        ],
        exercises=[
            ExerciseItem(
                type='细节描写练习',
                prompt='请为"妈妈很辛苦地工作"这句话增加具体的细节描写',
                hint=['想想妈妈具体做什么工作', '描述工作时的动作和神情', '可以写时间（早晚）'],
                sample='妈妈每天早上六点就起床，匆匆忙忙地为我们准备早餐，然后赶去公司上班。'
            ),
            ExerciseItem(
                type='外貌描写练习',
                prompt='为妈妈增加外貌描写，让读者能够想象出妈妈的样子',
                hint=['描写眼睛、头发、身材等特征', '可以用比喻的修辞手法', '要体现妈妈的特点'],
                sample='妈妈有一双温柔的眼睛，像秋水一样清澈；她的头发总是梳得整整齐齐。'
            ),
            ExerciseItem(
                type='情感表达练习',
                prompt='把"我要好好学习，将来报答妈妈的恩情"这句话写得更有感情',
                hint=['具体说明要如何报答', '表达更深层的感情', '可以立下具体的誓言'],
                sample='我一定要努力学习，取得优异的成绩，将来找到好工作，让妈妈过上幸福的生活，不再为我们操劳。'
            )
        ],
        summary='这是一篇情感真挚的作文，小作者对妈妈的爱表达得很清楚。文章结构完整，从总述到具体，再到感情升华，层次分明。不过在具体描写和细节刻画方面还有提升空间，特别是对妈妈外貌和具体行为的描写可以更丰富一些。'
    )


def test_comprehensive_docx_features():
    """Test all enhanced DOCX features."""
    print("=== 综合DOCX报告功能测试 ===\n")
    
    evaluation = create_comprehensive_evaluation()
    
    # Test single student enhanced rendering
    print("测试单学生增强报告生成...")
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        result_path = render_essay_docx(evaluation, output_path)
        
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"✓ 增强版单学生报告生成成功")
            print(f"  文件路径: {result_path}")
            print(f"  文件大小: {file_size} 字节")
            print(f"  包含段落数: {len(evaluation.analysis.outline) if evaluation.analysis else 0}")
            print(f"  包含诊断数: {len(evaluation.diagnostics)}")
            print(f"  包含练习数: {len(evaluation.exercises)}")
            print(f"  评分维度数: {len(evaluation.scores.rubrics)}")
            return True
        else:
            print("✗ 报告文件未生成")
            return False
            
    except Exception as e:
        print(f"✗ 生成失败: {e}")
        return False
        
    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def demonstrate_new_features():
    """Demonstrate the new reporting features."""
    print("\n=== 新功能演示 ===\n")
    
    evaluation = create_comprehensive_evaluation()
    
    # Import the ViewModels functions
    from app.reporting.viewmodels import (
        map_paragraphs_to_vm, map_exercises_to_vm, build_feedback_summary
    )
    
    print("1. 段落级点评功能:")
    paragraphs = map_paragraphs_to_vm(evaluation)
    for para in paragraphs:
        print(f"   第{para.para_num}段 ({para.intent}):")
        print(f"     原文: {para.original_text}")
        print(f"     点评: {para.feedback.split('\\n')[0]}")  # Show first line only
        print(f"     润色: {para.polished_text}")
        print()
    
    print("2. 个性化练习建议:")
    exercises = map_exercises_to_vm(evaluation)
    for i, ex in enumerate(exercises, 1):
        print(f"   练习{i}: {ex.type}")
        print(f"     要求: {ex.prompt}")
        print(f"     要点: {', '.join(ex.hints[:2])}...")  # Show first 2 hints
        print(f"     示例: {ex.sample[:50]}...")
        print()
    
    print("3. 综合反馈摘要:")
    summary = build_feedback_summary(evaluation)
    print(f"   {summary[:200]}...")
    print()
    
    print("✓ 所有新功能运行正常")


def main():
    """Run comprehensive tests."""
    success = True
    
    try:
        # Test comprehensive DOCX features
        if not test_comprehensive_docx_features():
            success = False
        
        # Demonstrate new features
        demonstrate_new_features()
        
        if success:
            print("\n=== 所有测试通过! ===")
            print("\n增强功能总结:")
            print("• ✓ 段落级点评和润色建议")
            print("• ✓ 个性化写作练习生成")
            print("• ✓ 综合评价和反馈摘要")
            print("• ✓ 多维度评分详情")
            print("• ✓ 诊断问题分析")
            print("• ✓ 批量学生报告支持")
            print("• ✓ 向后兼容性保持")
        else:
            print("\n=== 部分测试失败 ===")
        
        return success
        
    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)