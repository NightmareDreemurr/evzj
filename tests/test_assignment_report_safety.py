"""
Test assignment report template safety with missing essay_id fields
"""
import pytest
import json
from jinja2 import Environment, DictLoader


def test_assignment_report_template_safety():
    """Test that assignment report template handles missing essay_id gracefully"""
    
    # Test data with mixed presence of essay_id
    test_report_data = {
        'top_essays': [
            {'essay_id': 1, 'student_name': '张三', 'score': 95, 'content_preview': '优秀作文预览'},
            {'student_name': '李四', 'score': 88, 'content_preview': '没有essay_id的作文'},  # Missing essay_id
        ],
        'bottom_essays': [
            {'essay_id': 3, 'student_name': '王五', 'score': 60, 'content_preview': '需要改进的作文'},
            {'student_name': '赵六', 'content_preview': '没有分数和essay_id的作文'},  # Missing essay_id and score
        ],
        'excellent_features': [
            {
                'feature': '描写生动',
                'description': '运用了丰富的修辞手法',
                'detailed_examples': [
                    {
                        'essay_id': 1,
                        'student_name': '张三',
                        'excellent_sentence': '优秀句子示例',
                        'sentence_position': '第2段',
                        'excellence_explanation': '很好的描述'
                    },
                    {
                        'student_name': '李四',  # Missing essay_id
                        'excellent_sentence': '另一个优秀句子',
                        'sentence_position': '第1段',
                        'excellence_explanation': '也很不错'
                    }
                ]
            }
        ],
        'common_issues': [
            {
                'type': '语法错误',
                'description': '存在语法问题',
                'detailed_examples': [
                    {
                        'essay_id': 4,
                        'student_name': '马六',
                        'problem_sentence': '有问题的句子',
                        'sentence_position': '第1段',
                        'problem_explanation': '语法不正确'
                    },
                    {
                        'student_name': '孙七',  # Missing essay_id
                        'problem_sentence': '另一个有问题的句子',
                        'sentence_position': '第2段',
                        'problem_explanation': '也有语法问题'
                    }
                ]
            }
        ]
    }
    
    # Test template fragments that mimic the actual template
    top_essays_template = """
{%- for example in report_data.top_essays -%}
{% set eid = example.get('essay_id') %}
Student: {{ example.get('student_name', '未知') }}
Score: {{ example.get('score', '未评分') }}
{% if eid %}Download: essay_{{ eid }}{% endif %}
{% endfor %}
"""

    excellent_features_template = """
{%- for strength in report_data.excellent_features -%}
Feature: {{ strength.feature }}
{% for example in strength.detailed_examples %}
{% set eid = example.get('essay_id') %}
Student: {{ example.get('student_name', '未知') }}
{% if eid %}Link: essay_{{ eid }}{% else %}No_link{% endif %}
{% endfor %}
{% endfor %}
"""

    problem_issues_template = """
{%- for problem in report_data.common_issues -%}
Issue: {{ problem.type }}
{% for example in problem.detailed_examples %}
{% set eid = example.get('essay_id') %}
Student: {{ example.get('student_name', '未知') }}
{% if eid %}Link: essay_{{ eid }}{% else %}No_link{% endif %}
{% endfor %}
{% endfor %}
"""

    env = Environment(loader=DictLoader({
        'top_essays': top_essays_template,
        'excellent_features': excellent_features_template,
        'problem_issues': problem_issues_template
    }))
    
    # Test top essays template - should not crash
    template = env.get_template('top_essays')
    result = template.render(report_data=test_report_data)
    assert 'Student: 张三' in result
    assert 'Student: 李四' in result
    assert 'Download: essay_1' in result  # Should have download for essay with ID
    assert 'Score: 95' in result
    assert 'Score: 88' in result
    
    # Test excellent features template - should not crash
    template = env.get_template('excellent_features')
    result = template.render(report_data=test_report_data)
    assert 'Student: 张三' in result
    assert 'Student: 李四' in result  
    assert 'Link: essay_1' in result  # Should have link for essay with ID
    assert 'No_link' in result  # Should handle missing essay_id gracefully
    
    # Test problem issues template - should not crash
    template = env.get_template('problem_issues')
    result = template.render(report_data=test_report_data)
    assert 'Student: 马六' in result
    assert 'Student: 孙七' in result
    assert 'Link: essay_4' in result  # Should have link for essay with ID
    assert 'No_link' in result  # Should handle missing essay_id gracefully


def test_essay_id_types():
    """Test that essay_id values are properly typed as integers"""
    from app.services.ai_report_analyzer import _get_top_essays, _get_bottom_essays
    
    # Mock data for testing
    class MockUser:
        def __init__(self, name, username):
            self.full_name = name
            self.username = username

    class MockStudentProfile:
        def __init__(self, name):
            self.name = name
            
    class MockEnrollment:
        def __init__(self, name):
            self.student_profile = MockStudentProfile(name)

    class MockEssay:
        def __init__(self, id, name, final_score=None, ai_score=None, content=""):
            self.id = id
            self.final_score = final_score
            self.ai_score = ai_score
            self.content = content
            self.enrollment = MockEnrollment(name)

    essays = [
        MockEssay(1, "张三", final_score=95, content="优秀作文内容"),
        MockEssay(2, "李四", ai_score={"total_score": 88}, content="不错的作文"),
    ]

    # Test top essays
    top_essays = _get_top_essays(essays, 2)
    for essay in top_essays:
        assert isinstance(essay['essay_id'], int), f"essay_id should be int, got {type(essay['essay_id'])}"
        assert essay['essay_id'] > 0, "essay_id should be positive"
        assert isinstance(essay['score'], (int, float)), f"score should be numeric, got {type(essay['score'])}"
        
    # Test bottom essays
    bottom_essays = _get_bottom_essays(essays, 2)
    for essay in bottom_essays:
        assert isinstance(essay['essay_id'], int), f"essay_id should be int, got {type(essay['essay_id'])}"
        assert essay['essay_id'] > 0, "essay_id should be positive"
        assert isinstance(essay['score'], (int, float)), f"score should be numeric, got {type(essay['score'])}"


if __name__ == "__main__":
    test_assignment_report_template_safety()
    test_essay_id_types()
    print("✅ All template safety tests passed!")