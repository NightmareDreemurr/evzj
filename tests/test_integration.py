"""
End-to-end integration test for the evaluation pipeline.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.eval_pipeline import evaluate_essay
from tests.fixtures import SAMPLE_ESSAY, SAMPLE_META, MOCK_ANALYSIS_RESULT, MOCK_SCORES_RESULT


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app('testing')
    return app


@pytest.fixture
def app_context(app):
    """Create application context for testing"""
    with app.app_context():
        yield app


@patch('app.services.eval_pipeline.get_llm_provider')
def test_evaluate_essay_end_to_end(mock_get_provider, app_context):
    """Test the complete evaluate_essay pipeline"""
    # Mock LLM provider for both analyze and score calls
    mock_provider = MagicMock()
    mock_provider.call_llm.side_effect = [
        MOCK_ANALYSIS_RESULT,  # First call for analyze
        MOCK_SCORES_RESULT     # Second call for score  
    ]
    mock_get_provider.return_value = mock_provider
    
    # Run the complete pipeline
    result = evaluate_essay(SAMPLE_ESSAY, SAMPLE_META)
    
    # Verify result structure
    assert result is not None
    assert hasattr(result, 'meta')
    assert hasattr(result, 'analysis')
    assert hasattr(result, 'scores')
    assert hasattr(result, 'diagnostics')
    assert hasattr(result, 'exercises')
    assert hasattr(result, 'summary')
    
    # Verify meta
    assert result.meta.grade == "五年级"
    assert result.meta.student_id == "test_student_123"
    assert result.meta.words > 0
    
    # Verify analysis
    assert len(result.analysis.outline) == 5
    assert len(result.analysis.issues) == 2
    
    # Verify scores
    assert result.scores.total == 75.5
    assert result.scores.content == 22.5
    assert result.scores.structure == 16.0
    
    # Verify LLM was called twice (analyze + score)
    assert mock_provider.call_llm.call_count == 2
    
    # Verify the result can be serialized to dict (for storage)
    result_dict = result.model_dump()
    assert isinstance(result_dict, dict)
    assert 'meta' in result_dict
    assert 'analysis' in result_dict
    assert 'scores' in result_dict


def test_evaluate_essay_json_serialization(app_context):
    """Test that EvaluationResult can be serialized and deserialized"""
    from app.schemas.evaluation import EvaluationResult, Meta, Analysis, Scores, OutlineItem
    
    # Create a sample result
    result = EvaluationResult(
        meta=Meta(grade="五年级", words=100),
        analysis=Analysis(
            outline=[OutlineItem(para=1, intent="测试意图")],
            issues=["测试问题"]
        ),
        scores=Scores(total=75.0, content=25.0, rationale="测试评分"),
        diagnostics=[],
        exercises=[],
        summary="测试总结"
    )
    
    # Serialize to dict
    result_dict = result.model_dump()
    assert isinstance(result_dict, dict)
    
    # Deserialize back
    result_restored = EvaluationResult.model_validate(result_dict)
    assert result_restored.meta.grade == "五年级"
    assert result_restored.scores.total == 75.0
    assert len(result_restored.analysis.outline) == 1