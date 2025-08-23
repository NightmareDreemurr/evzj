"""
Test cases for evaluation DAO legacy data handling improvements.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.dao.evaluation_dao import _is_legacy_ai_score_format, _normalize_legacy_ai_score, load_evaluation_by_essay
from app.schemas.evaluation import EvaluationResult
from app.models import Essay


class TestEvaluationDAOFixes:
    """Test the evaluation DAO improvements for legacy data handling"""
    
    def test_legacy_format_detection(self):
        """Test the legacy format detection function"""
        
        # Legacy format indicators
        legacy_cases = [
            {"total_score": 32},
            {"dimensions": [{"name": "content", "score": 18}]},
            {"analysis": "Detailed analysis..."},
            {"summary": "Summary text"},
            {"overall_feedback": "Good work"},
            {"meta": {"student": "John"}, "total_score": 85},  # Mixed - should be legacy
        ]
        
        # New format indicators
        new_cases = [
            {"meta": {"student": "John"}, "scores": {"total": 85.0}},
            {"meta": {}, "scores": {"total": 90.0, "rubrics": []}},
        ]
        
        # Edge cases
        edge_cases = [
            {},  # Empty - should be treated as new format
        ]
        
        # Test legacy cases
        for data in legacy_cases:
            assert _is_legacy_ai_score_format(data) is True, f"Should detect as legacy: {data}"
        
        # Test new format cases
        for data in new_cases:
            assert _is_legacy_ai_score_format(data) is False, f"Should detect as new format: {data}"
        
        # Test edge cases
        for data in edge_cases:
            assert _is_legacy_ai_score_format(data) is False, f"Should default to new format: {data}"
    
    def test_normalization_robustness(self):
        """Test that normalization handles malformed data gracefully"""
        
        essay = Essay()
        essay.id = 1
        essay.content = "Test content"
        essay.created_at = datetime.now()
        essay.enrollment = None
        essay.assignment = None
        essay.teacher_corrected_text = None
        
        # Test cases with malformed data
        malformed_cases = [
            {"total_score": "not_a_number"},
            {"total_score": None},
            {"scores": {"total": "invalid"}},
            {"dimensions": "not_a_list"},
            {"dimensions": [{"name": "content"}]},  # Missing score
            {"dimensions": [{"score": 18}]},        # Missing name
            {"dimensions": [{"name": "content", "score": "invalid"}]},
            {},  # Empty data
        ]
        
        for data in malformed_cases:
            # Should not raise an exception
            normalized = _normalize_legacy_ai_score(data, essay)
            
            # Should produce valid EvaluationResult
            evaluation = EvaluationResult.model_validate(normalized)
            
            # Should have basic required structure
            assert evaluation.meta is not None
            assert evaluation.scores is not None
            assert isinstance(evaluation.scores.total, (int, float))
            assert isinstance(evaluation.scores.rubrics, list)
    
    def test_mixed_valid_invalid_data(self):
        """Test handling of data with mix of valid and invalid fields"""
        
        essay = Essay()
        essay.id = 1
        essay.content = "Test content"
        essay.created_at = datetime.now()
        essay.enrollment = None
        essay.assignment = None
        essay.teacher_corrected_text = None
        
        # Mix of valid and invalid data
        mixed_data = {
            "total_score": 85,
            "dimensions": [
                {"name": "content", "score": 18},
                {"name": "structure", "score": "invalid"},  # Should be skipped
                {"name": "language", "score": 16}
            ],
            "scores": {
                "content": 18,
                "structure": "also_invalid",  # Should be skipped
                "language": 16,
                "rationale": "Good work"
            }
        }
        
        normalized = _normalize_legacy_ai_score(mixed_data, essay)
        evaluation = EvaluationResult.model_validate(normalized)
        
        # Should preserve valid total score
        assert evaluation.scores.total == 85.0
        
        # Should have rubrics for valid dimensions only
        assert len(evaluation.scores.rubrics) == 2  # content and language only
        rubric_names = [r.name for r in evaluation.scores.rubrics]
        assert "content" in rubric_names
        assert "language" in rubric_names
        assert "structure" not in rubric_names  # Invalid score was skipped
    
    @patch('app.dao.evaluation_dao.db.session.get')
    @patch('app.dao.evaluation_dao.logger')
    def test_load_evaluation_avoids_unnecessary_warnings(self, mock_logger, mock_get):
        """Test that load_evaluation_by_essay avoids unnecessary warning messages for legacy data"""
        
        # Create mock essay with legacy data
        essay = MagicMock()
        essay.id = 13
        essay.ai_score = {"total_score": 32, "overall_feedback": "Good work"}
        essay.content = "Test content"
        essay.created_at = datetime.now()
        essay.enrollment = None
        essay.assignment = None
        essay.teacher_corrected_text = None
        
        mock_get.return_value = essay
        
        # Call the function
        result = load_evaluation_by_essay(13)
        
        # Should successfully return an evaluation
        assert result is not None
        assert isinstance(result, EvaluationResult)
        assert result.scores.total == 32.0
        
        # Should not have generated warnings about failed new format parsing
        warning_calls = [call for call in mock_logger.warning.call_args_list 
                        if 'Failed to parse ai_score as new format' in str(call)]
        assert len(warning_calls) == 0, "Should not generate unnecessary warnings for legacy data"
        
        # Should have logged successful legacy conversion
        info_calls = [call for call in mock_logger.info.call_args_list
                     if 'legacy format, auto-converted' in str(call)]
        assert len(info_calls) == 1, "Should log successful legacy conversion"
    
    @patch('app.dao.evaluation_dao.db.session.get')
    @patch('app.dao.evaluation_dao.logger')
    def test_load_evaluation_handles_new_format(self, mock_logger, mock_get):
        """Test that load_evaluation_by_essay still handles new format correctly"""
        
        # Create mock essay with new format data
        essay = MagicMock()
        essay.id = 14
        essay.ai_score = {
            "meta": {"student": "Test Student", "grade": "五年级"},
            "scores": {"total": 88.5, "rubrics": []},
            "highlights": [],
            "summary": "Great work"
        }
        essay.content = "Test content"
        essay.created_at = datetime.now()
        
        mock_get.return_value = essay
        
        # Call the function
        result = load_evaluation_by_essay(14)
        
        # Should successfully return an evaluation
        assert result is not None
        assert isinstance(result, EvaluationResult)
        assert result.scores.total == 88.5
        assert result.meta.student == "Test Student"
        
        # Should have logged successful new format parsing
        info_calls = [call for call in mock_logger.info.call_args_list
                     if 'new format' in str(call)]
        assert len(info_calls) == 1, "Should log successful new format parsing"
        
        # Should not have attempted legacy conversion
        legacy_calls = [call for call in mock_logger.info.call_args_list
                       if 'legacy format' in str(call)]
        assert len(legacy_calls) == 0, "Should not attempt legacy conversion for new format data"