"""
Tests for AI pre-grader and evaluation builder functionality.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from flask import Flask

from app.services.ai_pregrader import generate_preanalysis, _validate_and_sanitize_response, _get_empty_preanalysis
from app.services.evaluation_builder import build_and_persist_evaluation, _build_context_for_essay, _build_evaluation_result
from app.services.evaluation_result_types import (
    from_ai_grader_json, from_corrector_text, create_meta_from_essay, 
    create_empty_evaluation_result, validate_pregrader_output
)
from app.schemas.evaluation import EvaluationResult, Meta, TextBlock, Scores, Analysis, OutlineItem


class TestAIPregrader:
    """Test AI pre-grader service functionality."""
    
    def test_generate_preanalysis_empty_text(self):
        """Test pre-grader with empty text returns empty structure."""
        result = generate_preanalysis("")
        expected = _get_empty_preanalysis()
        assert result == expected
    
    def test_generate_preanalysis_no_api_config(self, app):
        """Test pre-grader without API config returns empty structure."""
        with app.app_context():
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.return_value = None
                result = generate_preanalysis("Some essay text")
                expected = _get_empty_preanalysis()
                assert result == expected
    
    @patch('app.services.ai_pregrader.requests.post')
    def test_generate_preanalysis_success(self, mock_post, app):
        """Test successful pre-grader API call."""
        with app.app_context():
            # Mock API response
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            "analysis": {"outline": [{"para": 1, "intent": "开篇"}]},
                            "diagnostics": [{"para": 1, "issue": "测试问题", "evidence": "测试证据", "advice": ["建议1"]}],
                            "exercises": [{"type": "练习", "prompt": "测试练习", "hint": ["提示1"], "sample": "示例"}],
                            "summary": "测试总结",
                            "diagnosis": {"before": "之前", "comment": "评论", "after": "之后"}
                        })
                    }
                }]
            }
            mock_post.return_value = mock_response
            
            # Mock app config
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.side_effect = lambda key: {
                    'DEEPSEEK_API_KEY': 'test_key',
                    'DEEPSEEK_API_URL': 'http://test.com',
                    'DEEPSEEK_MODEL_CHAT': 'test_model'
                }.get(key)
                
                result = generate_preanalysis("测试作文内容")
                
                # Verify structure
                assert "analysis" in result
                assert "outline" in result["analysis"]
                assert len(result["analysis"]["outline"]) == 1
                assert result["analysis"]["outline"][0]["para"] == 1
                assert result["analysis"]["outline"][0]["intent"] == "开篇"
                
                assert "diagnostics" in result
                assert len(result["diagnostics"]) == 1
                assert result["diagnostics"][0]["issue"] == "测试问题"
                
                assert "exercises" in result
                assert "summary" in result
                assert "diagnosis" in result
    
    @patch('app.services.ai_pregrader.requests.post')
    def test_generate_preanalysis_api_error(self, mock_post, app):
        """Test pre-grader API error returns empty structure."""
        with app.app_context():
            mock_post.side_effect = Exception("API Error")
            
            with patch('flask.current_app.config') as mock_config:
                mock_config.get.side_effect = lambda key: {
                    'DEEPSEEK_API_KEY': 'test_key',
                    'DEEPSEEK_API_URL': 'http://test.com',
                    'DEEPSEEK_MODEL_CHAT': 'test_model'
                }.get(key)
                
                result = generate_preanalysis("测试作文内容")
                expected = _get_empty_preanalysis()
                assert result == expected
    
    def test_validate_and_sanitize_response_valid(self):
        """Test validation with valid response data."""
        valid_data = {
            "analysis": {"outline": [{"para": 1, "intent": "测试意图"}]},
            "diagnostics": [{"para": 1, "issue": "问题", "evidence": "证据", "advice": ["建议"]}],
            "exercises": [{"type": "练习", "prompt": "要求", "hint": ["提示"], "sample": "示例"}],
            "summary": "总结",
            "diagnosis": {"before": "之前", "comment": "评论", "after": "之后"}
        }
        
        result = _validate_and_sanitize_response(valid_data)
        assert result["analysis"]["outline"][0]["para"] == 1
        assert result["diagnostics"][0]["issue"] == "问题"
        assert result["exercises"][0]["type"] == "练习"
        assert result["summary"] == "总结"
        assert result["diagnosis"]["before"] == "之前"
    
    def test_validate_and_sanitize_response_invalid(self):
        """Test validation with invalid response data."""
        invalid_data = {"invalid": "structure"}
        
        result = _validate_and_sanitize_response(invalid_data)
        expected = _get_empty_preanalysis()
        assert result == expected


class TestEvaluationResultTypes:
    """Test evaluation result type conversion functions."""
    
    def test_from_ai_grader_json_empty(self):
        """Test AI grader JSON conversion with empty data."""
        result = from_ai_grader_json({}, 1)
        assert result["total"] == 0
        assert result["rubrics"] == []
    
    def test_from_ai_grader_json_with_scores(self):
        """Test AI grader JSON conversion with score data."""
        ai_score_data = {
            "total_score": 85,
            "scores": {
                "content": 18,
                "structure": 16,
                "language": 17
            },
            "dimensions": [
                {"dimension": "content", "feedback": "内容丰富"},
                {"dimension": "structure", "feedback": "结构清晰"}
            ]
        }
        
        result = from_ai_grader_json(ai_score_data, 1)
        assert result["total"] == 85
        assert len(result["rubrics"]) == 3
        
        content_rubric = next((r for r in result["rubrics"] if r["name"] == "内容"), None)
        assert content_rubric is not None
        assert content_rubric["score"] == 18
        assert content_rubric["reason"] == "内容丰富"
    
    def test_from_corrector_text(self):
        """Test text block creation from corrector output."""
        original = "原始文本"
        cleaned = "清洁文本"
        
        result = from_corrector_text(original, cleaned)
        assert result["original"] == original
        assert result["cleaned"] == cleaned
        
        # Test with no cleaned text
        result2 = from_corrector_text(original, None)
        assert result2["cleaned"] == original
    
    def test_create_meta_from_essay(self):
        """Test meta creation from essay data."""
        essay_data = {
            "student_name": "张三",
            "student_id": 123,
            "class_name": "五年级一班",
            "teacher_name": "李老师",
            "topic": "我的家乡",
            "grade": "五年级",
            "word_count": 450
        }
        
        result = create_meta_from_essay(1, essay_data)
        assert result["student"] == "张三"
        assert result["class_"] == "五年级一班"
        assert result["teacher"] == "李老师"
        assert result["topic"] == "我的家乡"
        assert result["words"] == 450
    
    def test_validate_pregrader_output_valid(self):
        """Test validation with valid pre-grader output."""
        valid_output = {
            "analysis": {"outline": [{"para": 1, "intent": "测试"}]},
            "diagnostics": [{"para": 1, "issue": "问题", "evidence": "证据", "advice": ["建议"]}],
            "exercises": [{"type": "练习", "prompt": "要求"}],
            "summary": "总结"
        }
        
        assert validate_pregrader_output(valid_output) is True
    
    def test_validate_pregrader_output_invalid(self):
        """Test validation with invalid pre-grader output."""
        invalid_outputs = [
            {},  # Empty
            {"analysis": {}},  # Missing outline
            {"analysis": {"outline": []}, "diagnostics": "not_list"},  # Wrong type
            "not_dict"  # Wrong type
        ]
        
        for invalid in invalid_outputs:
            assert validate_pregrader_output(invalid) is False


class TestEvaluationBuilder:
    """Test evaluation builder functionality."""
    
    @patch('app.services.evaluation_builder.db.session')
    def test_build_context_for_essay(self, mock_session):
        """Test context building for essay."""
        # Create mock essay with all relationships
        mock_essay = Mock()
        mock_essay.id = 1
        mock_essay.content = "测试作文内容"
        mock_essay.created_at.date.return_value.isoformat.return_value = "2023-08-23"
        
        # Mock assignment
        mock_essay.assignment.title = "我的家乡"
        mock_essay.assignment.grading_standard.grade = "五年级"
        mock_essay.assignment.grading_standard.total_score = 100
        mock_essay.assignment.teacher_profile.user.full_name = "李老师"
        
        # Mock enrollment and student
        mock_essay.enrollment.student.user.full_name = "张三"
        mock_essay.enrollment.student.id = 123
        mock_essay.enrollment.classroom.name = "五年级一班"
        
        with patch('app.services.evaluation_builder.count_words_zh', return_value=450):
            result = _build_context_for_essay(mock_essay)
        
        assert result["topic"] == "我的家乡"
        assert result["student_name"] == "张三"
        assert result["teacher_name"] == "李老师"
        assert result["class_name"] == "五年级一班"
        assert result["word_count"] == 450
    
    @patch('app.services.evaluation_builder.db.session')
    @patch('app.services.evaluation_builder.generate_preanalysis')
    @patch('app.services.evaluation_builder.correct_text_with_ai')
    @patch('app.services.evaluation_builder.grade_essay_with_ai')
    def test_build_and_persist_evaluation_success(self, mock_grade, mock_correct, mock_preanalysis, mock_session, app):
        """Test successful evaluation building and persistence."""
        with app.app_context():
            # Mock essay
            mock_essay = Mock()
            mock_essay.id = 1
            mock_essay.content = "测试作文内容"
            mock_essay.corrected_content = None
            mock_essay.ai_score = None
            mock_essay.created_at.date.return_value.isoformat.return_value = "2023-08-23"
            
            # Setup relationships
            mock_essay.assignment.title = "我的家乡"
            mock_essay.assignment.grading_standard.grade = "五年级"
            mock_essay.assignment.teacher_profile.user.full_name = "李老师"
            mock_essay.enrollment.student.user.full_name = "张三"
            mock_essay.enrollment.classroom.name = "五年级一班"
            
            mock_session.get.return_value = mock_essay
            
            # Mock services
            mock_correct.return_value = "清洁后的内容"
            mock_preanalysis.return_value = {
                "analysis": {"outline": [{"para": 1, "intent": "开篇"}]},
                "diagnostics": [],
                "exercises": [],
                "summary": "测试总结",
                "diagnosis": {}
            }
            
            # Mock AI grader updating the essay
            def mock_grade_side_effect(essay_id):
                mock_essay.ai_score = {"total_score": 85, "scores": {"content": 18}}
            mock_grade.side_effect = mock_grade_side_effect
            
            with patch('app.services.evaluation_builder.count_words_zh', return_value=450):
                result = build_and_persist_evaluation(1)
            
            # Verify result structure
            assert result is not None
            assert isinstance(result, EvaluationResult)
            assert result.meta.student == "张三"
            assert result.text.original == "测试作文内容"
            assert result.text.cleaned == "清洁后的内容"
            assert result.scores.total == 85
    
    @patch('app.services.evaluation_builder.db.session')  
    def test_build_and_persist_evaluation_essay_not_found(self, mock_session):
        """Test evaluation building with non-existent essay."""
        mock_session.get.return_value = None
        
        with pytest.raises(Exception):  # Should raise EvaluationBuilderError
            build_and_persist_evaluation(999)


@pytest.fixture
def app():
    """Create test Flask application."""
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app