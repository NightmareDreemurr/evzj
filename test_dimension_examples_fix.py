#!/usr/bin/env python3
"""
Test the fix for dimension examples in DOCX reports.
This test verifies that example_good_sentence and example_improvement_suggestion 
data is properly preserved and displayed in reports instead of showing "（本项暂无数据）".
"""

import tempfile
from app.schemas.evaluation import (
    EvaluationResult, Meta, Scores, RubricScore, TextBlock, to_context
)


def test_dimension_examples_mapping():
    """Test that dimension examples are properly mapped from original grading result"""
    
    # Create a mock grading result with dimension examples (as would come from AI grader)
    mock_grading_result = {
        'total_score': 85,
        'dimensions': [
            {
                'dimension_name': '书籍内容概述提炼',
                'score': 18,
                'feedback': '内容概述较好',
                'example_good_sentence': '这本书生动地描述了主人公的成长历程。',
                'example_improvement_suggestion': {
                    'original': '书很好看。',
                    'suggested': '这本书通过细腻的描写展现了深刻的人生哲理。'
                }
            },
            {
                'dimension_name': '心得体会交流分享',
                'score': 16,
                'feedback': '心得体会表达清晰',
                'example_good_sentence': '通过阅读这本书，我深深地感受到了友谊的珍贵。',
                'example_improvement_suggestion': {
                    'original': '我觉得很有道理。',
                    'suggested': '这个观点让我重新思考了人与人之间关系的本质。'
                }
            },
            {
                'dimension_name': '语言表达学术规范',
                'score': 15,
                'feedback': '语言表达需要提升',
                'example_good_sentence': '作者运用了丰富的修辞手法，使文章生动有趣。',
                'example_improvement_suggestion': {
                    'original': '写得好。',
                    'suggested': '文章结构严谨，论证有力，表达准确。'
                }
            }
        ],
        'strengths': ['内容丰富', '结构清晰'],
        'improvements': ['语言表达可以更准确', '可以增加更多例证']
    }
    
    # Create EvaluationResult
    evaluation = EvaluationResult(
        meta=Meta(
            student="测试学生",
            class_="测试班级",
            teacher="测试老师",
            topic="读书心得",
            date="2024-08-21"
        ),
        scores=Scores(
            total=85.0,
            rubrics=[
                RubricScore(name="书籍内容概述提炼", score=18.0, max=20.0, weight=1.0, reason="内容概述较好"),
                RubricScore(name="心得体会交流分享", score=16.0, max=20.0, weight=1.0, reason="心得体会表达清晰"),
                RubricScore(name="语言表达学术规范", score=15.0, max=20.0, weight=1.0, reason="语言表达需要提升")
            ]
        ),
        text=TextBlock(
            original="这是测试的读书心得内容。",
            cleaned="这是测试的读书心得内容。"
        ),
        strengths=mock_grading_result['strengths'],
        improvements=mock_grading_result['improvements']
    )
    
    # Attach original grading result (this simulates what happens in reporting service)
    evaluation._original_grading_result = mock_grading_result
    
    # Convert to template context
    context = to_context(evaluation)
    
    # Verify that dimensions have the example data
    grading_result = context['gradingResult']
    dimensions = grading_result['dimensions']
    
    print("Checking dimensions data:")
    for i, dimension in enumerate(dimensions):
        print(f"\nDimension {i+1}: {dimension['dimension_name']}")
        print(f"  Example good sentence: {dimension['example_good_sentence']}")
        print(f"  Example improvement suggestion: {dimension['example_improvement_suggestion']}")
        
        # Verify example_good_sentence is populated
        assert dimension['example_good_sentence'], f"example_good_sentence should not be empty for dimension {dimension['dimension_name']}"
        assert len(dimension['example_good_sentence']) > 0, f"example_good_sentence should have content for dimension {dimension['dimension_name']}"
        
        # Verify example_improvement_suggestion is populated
        assert dimension['example_improvement_suggestion'], f"example_improvement_suggestion should not be empty for dimension {dimension['dimension_name']}"
        assert len(dimension['example_improvement_suggestion']) > 0, f"example_improvement_suggestion should have content for dimension {dimension['dimension_name']}"
        
        # Check the structure of improvement suggestion
        improvement_suggestion = dimension['example_improvement_suggestion'][0]
        assert 'original' in improvement_suggestion, f"improvement suggestion should have 'original' field"
        assert 'suggested' in improvement_suggestion, f"improvement suggestion should have 'suggested' field"
        assert improvement_suggestion['original'], f"improvement suggestion 'original' should not be empty"
        assert improvement_suggestion['suggested'], f"improvement suggestion 'suggested' should not be empty"
    
    print("\n✅ All dimension examples are properly populated!")
    print("\nThis should fix the '（本项暂无数据）' issue in DOCX reports.")
    
    return context


if __name__ == "__main__":
    test_dimension_examples_mapping()