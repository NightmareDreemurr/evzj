"""
Tests for the standards DAO.
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.dao.standards import get_grading_standard


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


def test_get_grading_standard_yaml_fallback(app_context):
    """Test loading grading standard from YAML fallback"""
    standard = get_grading_standard('五年级', 'narrative')
    
    assert standard is not None
    assert standard.title == "五年级记叙文评分标准"
    assert standard.total_score == 100
    assert standard.grade == "五年级"
    assert standard.genre == "narrative"
    assert len(standard.dimensions) == 5
    
    # Check dimension names
    dim_names = [dim['name'] for dim in standard.dimensions]
    expected_names = ['内容', '结构', '语言', '文采', '规范']
    assert dim_names == expected_names
    
    # Check total scores add up
    total_max = sum(dim['max_score'] for dim in standard.dimensions)
    assert total_max == 100


def test_get_grading_standard_nonexistent(app_context):
    """Test loading non-existent grading standard"""
    standard = get_grading_standard('十年级', 'unknown')
    assert standard is None


def test_dimension_structure(app_context):
    """Test that dimensions have correct structure"""
    standard = get_grading_standard('五年级', 'narrative')
    
    for dim in standard.dimensions:
        assert 'name' in dim
        assert 'max_score' in dim
        assert 'rubrics' in dim
        assert isinstance(dim['rubrics'], list)
        
        for rubric in dim['rubrics']:
            assert 'level_name' in rubric
            assert 'description' in rubric
            assert 'min_score' in rubric
            assert 'max_score' in rubric