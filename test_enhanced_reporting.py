#!/usr/bin/env python3
"""
Test script for enhanced DOCX reporting functionality.
"""
import tempfile
import os
from app.schemas.evaluation import (
    EvaluationResult, Meta, Scores, RubricScore, TextBlock, 
    Analysis, OutlineItem, DiagnosticItem, ExerciseItem
)
from app.reporting.viewmodels import (
    StudentReportVM, ParaVM, ExerciseVM, ScoreVM, ScoreItemVM,
    map_paragraphs_to_vm, map_exercises_to_vm, build_feedback_summary
)
from app.reporting.docx_renderer import render_essay_docx


def create_test_evaluation():
    """Create a comprehensive test evaluation with all data types."""
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


def test_enhanced_viewmodels():
    """Test the enhanced ViewModels functionality."""
    print("Testing enhanced ViewModels...")
    
    evaluation = create_test_evaluation()
    
    # Test paragraph mapping
    paragraphs = map_paragraphs_to_vm(evaluation)
    print(f"✓ Mapped {len(paragraphs)} paragraphs")
    
    for para in paragraphs:
        print(f"  Para {para.para_num}: {para.intent}")
        print(f"    Original: {para.original_text[:50]}...")
        print(f"    Feedback: {para.feedback[:100]}...")
        print()
    
    # Test exercise mapping
    exercises = map_exercises_to_vm(evaluation)
    print(f"✓ Mapped {len(exercises)} exercises")
    
    for ex in exercises:
        print(f"  {ex.type}: {ex.prompt}")
        print(f"    Hints: {', '.join(ex.hints)}")
        print(f"    Sample: {ex.sample[:50]}...")
        print()
    
    # Test feedback summary
    summary = build_feedback_summary(evaluation)
    print(f"✓ Built feedback summary ({len(summary)} chars)")
    print(f"  Summary: {summary[:200]}...")
    print()
    
    return True


def test_enhanced_docx_rendering():
    """Test enhanced DOCX rendering with rich data."""
    print("Testing enhanced DOCX rendering...")
    
    evaluation = create_test_evaluation()
    
    # Test rendering to temp file
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
        output_path = tmp.name
    
    try:
        result_path = render_essay_docx(evaluation, output_path)
        
        if os.path.exists(result_path):
            file_size = os.path.getsize(result_path)
            print(f"✓ DOCX file created: {result_path}")
            print(f"  File size: {file_size} bytes")
            return True
        else:
            print("✗ DOCX file was not created")
            return False
            
    finally:
        # Cleanup
        if os.path.exists(output_path):
            os.unlink(output_path)


def main():
    """Run all tests."""
    print("=== Enhanced DOCX Reporting Tests ===\n")
    
    try:
        # Test ViewModels
        if not test_enhanced_viewmodels():
            print("✗ ViewModels test failed")
            return False
        
        # Test DOCX rendering
        if not test_enhanced_docx_rendering():
            print("✗ DOCX rendering test failed")
            return False
        
        print("=== All Tests Passed! ===")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)