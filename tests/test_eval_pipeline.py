"""
Tests for the evaluation pipeline.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.eval_pipeline import analyze, score, assemble, _format_standard_for_prompt
from app.schemas.evaluation import StandardDTO, EvaluationResult
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


@pytest.fixture
def mock_standard():
    """Mock grading standard for testing"""
    return StandardDTO(
        title="测试评分标准",
        total_score=100,
        grade="五年级",
        genre="narrative",
        dimensions=[
            {
                "name": "内容",
                "max_score": 30,
                "rubrics": [
                    {
                        "level_name": "优秀",
                        "min_score": 26,
                        "max_score": 30,
                        "description": "内容充实"
                    }
                ]
            },
            {
                "name": "结构", 
                "max_score": 20,
                "rubrics": [
                    {
                        "level_name": "优秀",
                        "min_score": 18,
                        "max_score": 20,
                        "description": "结构清晰"
                    }
                ]
            }
        ]
    )


def test_format_standard_for_prompt(mock_standard):
    """Test formatting standard for LLM prompt"""
    formatted = _format_standard_for_prompt(mock_standard)
    
    assert "评分标准：测试评分标准" in formatted
    assert "总分：100分" in formatted
    assert "**内容**" in formatted
    assert "**结构**" in formatted
    assert "内容充实" in formatted
    assert "结构清晰" in formatted


def test_analyze_success(app_context):
    """Test successful analysis step"""
    # Mock LLM provider
    mock_provider = MagicMock()
    mock_provider.call_llm.return_value = MOCK_ANALYSIS_RESULT
    
    result = analyze(SAMPLE_ESSAY, SAMPLE_META, llm_provider=mock_provider)
    
    assert result is not None
    assert 'outline' in result
    assert 'issues' in result
    assert len(result['outline']) == 5
    assert len(result['issues']) == 2


def test_analyze_failure(app_context):
    """Test analysis step failure handling"""
    # Mock LLM provider failure
    mock_provider = MagicMock()
    mock_provider.call_llm.side_effect = Exception("API Error")
    
    result = analyze(SAMPLE_ESSAY, SAMPLE_META, llm_provider=mock_provider)
    
    # Should return default structure on failure
    assert result is not None
    assert 'outline' in result
    assert 'issues' in result
    assert 'AI分析失败' in result['issues']


def test_score_success(app_context, mock_standard):
    """Test successful scoring step"""
    # Mock LLM provider
    mock_provider = MagicMock()
    mock_provider.call_llm.return_value = MOCK_SCORES_RESULT
    
    result = score(SAMPLE_ESSAY, mock_standard, MOCK_ANALYSIS_RESULT, llm_provider=mock_provider)
    
    assert result is not None
    assert 'content' in result
    assert 'structure' in result
    assert 'total' in result
    assert 'rationale' in result
    assert result['total'] == 75.5


def test_score_failure(app_context, mock_standard):
    """Test scoring step failure handling"""
    # Mock LLM provider failure
    mock_provider = MagicMock()
    mock_provider.call_llm.side_effect = Exception("API Error")
    
    result = score(SAMPLE_ESSAY, mock_standard, MOCK_ANALYSIS_RESULT, llm_provider=mock_provider)
    
    # Should return default scores on failure
    assert result is not None
    assert result['total'] == 0.0
    assert '评分失败' in result['rationale']


def test_assemble(app_context):
    """Test assembling final evaluation result"""
    result = assemble(
        meta=SAMPLE_META,
        analysis=MOCK_ANALYSIS_RESULT,
        scores=MOCK_SCORES_RESULT,
        diagnostics=[],
        exercises=[],
        summary="测试总结"
    )
    
    assert isinstance(result, EvaluationResult)
    assert result.meta.grade == "五年级"
    assert result.meta.student_id == "test_student_123"
    assert len(result.analysis.outline) == 5
    assert len(result.analysis.issues) == 2
    assert result.scores.total == 75.5
    assert result.summary == "测试总结"