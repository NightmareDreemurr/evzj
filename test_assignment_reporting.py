#!/usr/bin/env python3
"""
Test enhanced assignment-level DOCX reporting functionality.
"""
import tempfile
import os
from app.schemas.evaluation import (
    EvaluationResult, Meta, Scores, RubricScore, TextBlock, 
    Analysis, OutlineItem, DiagnosticItem, ExerciseItem
)
from app.reporting.viewmodels import (
    StudentReportVM, AssignmentReportVM, ParaVM, ExerciseVM, ScoreVM, ScoreItemVM,
    map_paragraphs_to_vm, map_exercises_to_vm, build_feedback_summary
)
from app.reporting.service import _render_with_docxtpl_combined


def create_test_student_vms():
    """Create test StudentReportVM instances."""
    students = []
    
    # Student 1
    students.append(StudentReportVM(
        student_id=1,
        student_name='李小华',
        student_no='2024001',
        essay_id=101,
        topic='我的妈妈',
        words=180,
        scores=ScoreVM(
            total=85.5,
            items=[
                ScoreItemVM(key='content', name='内容', score=25.0, max_score=30.0),
                ScoreItemVM(key='structure', name='结构', score=22.0, max_score=25.0),
                ScoreItemVM(key='language', name='语言', score=20.5, max_score=25.0),
                ScoreItemVM(key='literary', name='文采', score=18.0, max_score=20.0),
            ]
        ),
        feedback='情感真挚，结构清晰',
        original_paragraphs=[
            '我的妈妈是一个非常好的人。',
            '她每天都很辛苦地工作，照顾我们全家。',
            '妈妈做的饭菜特别香，我最喜欢吃她做的红烧肉。',
            '我要好好学习，将来报答妈妈的恩情。'
        ],
        paragraphs=[
            ParaVM(
                para_num=1,
                original_text='我的妈妈是一个非常好的人。',
                feedback='写作意图：开篇总述妈妈的好',
                polished_text='我的妈妈是一个非常温柔善良的人。',
                intent='开篇总述妈妈的好'
            ),
            ParaVM(
                para_num=2,
                original_text='她每天都很辛苦地工作，照顾我们全家。',
                feedback='写作意图：具体描述妈妈的辛苦\\n问题：描述过于笼统\\n建议：增加具体的工作内容描述',
                polished_text='她每天早上六点就起床为我们准备早餐，白天辛苦工作，晚上还要照顾我们全家的生活起居。',
                intent='具体描述妈妈的辛苦'
            ),
            ParaVM(
                para_num=3,
                original_text='妈妈做的饭菜特别香，我最喜欢吃她做的红烧肉。',
                feedback='写作意图：举例说明妈妈的厨艺\\n问题：细节不够丰富\\n建议：可以写更多拿手菜',
                polished_text='妈妈做的饭菜特别香，红烧肉、糖醋排骨、西红柿鸡蛋汤，每一道菜都让我回味无穷。',
                intent='举例说明妈妈的厨艺'
            ),
            ParaVM(
                para_num=4,
                original_text='我要好好学习，将来报答妈妈的恩情。',
                feedback='写作意图：表达对妈妈的感激之情',
                polished_text='我一定要努力学习，取得优异的成绩，将来找到好工作，让妈妈过上幸福的生活。',
                intent='表达对妈妈的感激之情'
            )
        ],
        exercises=[
            ExerciseVM(
                type='细节描写练习',
                prompt='请为"妈妈很辛苦地工作"这句话增加具体的细节描写',
                hints=['想想妈妈具体做什么工作', '描述工作时的动作和神情', '可以写时间（早晚）'],
                sample='妈妈每天早上六点就起床，匆匆忙忙地为我们准备早餐，然后赶去公司上班。'
            ),
            ExerciseVM(
                type='外貌描写练习',
                prompt='为妈妈增加外貌描写，让读者能够想象出妈妈的样子',
                hints=['描写眼睛、头发、身材等特征', '可以用比喻的修辞手法', '要体现妈妈的特点'],
                sample='妈妈有一双温柔的眼睛，像秋水一样清澈；她的头发总是梳得整整齐齐。'
            )
        ],
        scanned_images=[],
        feedback_summary='这是一篇情感真挚的作文，结构完整，但需要增加具体描写。'
    ))
    
    # Student 2
    students.append(StudentReportVM(
        student_id=2,
        student_name='张小明',
        student_no='2024002',
        essay_id=102,
        topic='我的妈妈',
        words=220,
        scores=ScoreVM(
            total=78.0,
            items=[
                ScoreItemVM(key='content', name='内容', score=22.0, max_score=30.0),
                ScoreItemVM(key='structure', name='结构', score=20.0, max_score=25.0),
                ScoreItemVM(key='language', name='语言', score=18.0, max_score=25.0),
                ScoreItemVM(key='literary', name='文采', score=18.0, max_score=20.0),
            ]
        ),
        feedback='内容较丰富，需要注意语言表达',
        original_paragraphs=[
            '我有一个好妈妈。',
            '妈妈工作很忙。',
            '妈妈做饭很好吃。'
        ],
        paragraphs=[
            ParaVM(
                para_num=1,
                original_text='我有一个好妈妈。',
                feedback='写作意图：开头介绍\\n问题：太过简单\\n建议：增加具体描述',
                polished_text='我有一个勤劳善良的好妈妈。',
                intent='开头介绍'
            ),
            ParaVM(
                para_num=2,
                original_text='妈妈工作很忙。',
                feedback='写作意图：描述妈妈的工作\\n问题：内容单薄\\n建议：具体说明工作内容',
                polished_text='妈妈在医院工作，每天都要照顾很多病人，工作非常忙碌。',
                intent='描述妈妈的工作'
            ),
            ParaVM(
                para_num=3,
                original_text='妈妈做饭很好吃。',
                feedback='写作意图：赞美妈妈的厨艺\\n问题：缺乏具体例子\\n建议：举出具体菜名',
                polished_text='妈妈做的红烧肉、蒸蛋羹、青椒炒肉丝都特别好吃。',
                intent='赞美妈妈的厨艺'
            )
        ],
        exercises=[
            ExerciseVM(
                type='扩句练习',
                prompt='把"我有一个好妈妈"这句话写得更具体',
                hints=['描述妈妈的特点', '说明为什么说她好', '可以加上外貌或性格描写'],
                sample='我有一个温柔美丽、勤劳善良的好妈妈。'
            )
        ],
        scanned_images=[],
        feedback_summary='文章简洁，但内容需要进一步丰富，语言表达可以更加生动。'
    ))
    
    return students


def test_assignment_docx_rendering():
    """Test enhanced assignment DOCX rendering."""
    print("Testing enhanced assignment DOCX rendering...")
    
    # Create test assignment data
    students = create_test_student_vms()
    
    assignment_vm = AssignmentReportVM(
        assignment_id=1,
        title='第一次作文作业',
        classroom={'name': '五年级一班', 'id': 1},
        teacher={'name': '王老师', 'id': 1},
        students=students
    )
    
    # Test rendering to temp file
    try:
        result_bytes = _render_with_docxtpl_combined(assignment_vm)
        
        # Save to temp file for inspection
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            tmp.write(result_bytes)
            output_path = tmp.name
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✓ Assignment DOCX file created: {output_path}")
            print(f"  File size: {file_size} bytes")
            print(f"  Students included: {len(students)}")
            
            # Verify content by checking file size is reasonable for multiple students
            if file_size > 40000:  # Should be larger than single student report
                print("✓ File size indicates multi-student content")
                return True
            else:
                print("✗ File size seems too small for multi-student content")
                return False
        else:
            print("✗ Assignment DOCX file was not created")
            return False
            
    except Exception as e:
        print(f"✗ Assignment rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        if 'output_path' in locals() and os.path.exists(output_path):
            print(f"Cleaning up: {output_path}")
            os.unlink(output_path)


def main():
    """Run assignment-level tests."""
    print("=== Enhanced Assignment DOCX Reporting Tests ===\\n")
    
    try:
        if not test_assignment_docx_rendering():
            print("✗ Assignment DOCX rendering test failed")
            return False
        
        print("\\n=== Assignment Tests Passed! ===")
        return True
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)