"""
Tests for meta resolver service.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.services.meta_resolver import resolve_meta, _resolve_genre_from_standard, _get_fallback_meta


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


def test_resolve_meta_success(app_context):
    """Test successful meta resolution"""
    # Mock the database query chain
    mock_essay = MagicMock()
    mock_essay.enrollment.student.id = 123
    mock_essay.assignment.title = "测试作文题目"
    mock_essay.assignment.grading_standard.grade_level.name = "五年级"
    mock_essay.assignment.grading_standard.title = "五年级记叙文评分标准"
    
    with patch('app.services.meta_resolver.db.session.query') as mock_query:
        mock_query.return_value.join.return_value.join.return_value.join.return_value.outerjoin.return_value.outerjoin.return_value.filter.return_value.first.return_value = mock_essay
        
        result = resolve_meta(1)
        
        assert result['student_id'] == '123'
        assert result['grade'] == '五年级'
        assert result['genre'] == 'narrative'
        assert result['topic'] == '测试作文题目'
        assert result['words'] == 0


def test_resolve_meta_not_found(app_context):
    """Test meta resolution when essay not found"""
    with patch('app.services.meta_resolver.db.session.query') as mock_query:
        mock_query.return_value.join.return_value.join.return_value.join.return_value.outerjoin.return_value.outerjoin.return_value.filter.return_value.first.return_value = None
        
        result = resolve_meta(999)
        
        # Should return fallback meta
        assert result['student_id'] == 'unknown'
        assert result['grade'] == '五年级'
        assert result['genre'] == 'narrative'
        assert result['topic'] == '未知题目'


def test_resolve_meta_no_grading_standard(app_context):
    """Test meta resolution when essay has no grading standard"""
    mock_essay = MagicMock()
    mock_essay.enrollment.student.id = 123
    mock_essay.assignment.title = "测试作文题目"
    mock_essay.assignment.grading_standard = None
    
    with patch('app.services.meta_resolver.db.session.query') as mock_query:
        mock_query.return_value.join.return_value.join.return_value.join.return_value.outerjoin.return_value.outerjoin.return_value.filter.return_value.first.return_value = mock_essay
        
        result = resolve_meta(1)
        
        assert result['student_id'] == '123'
        assert result['grade'] == '五年级'  # fallback
        assert result['genre'] == 'narrative'
        assert result['topic'] == '测试作文题目'


def test_resolve_genre_from_standard():
    """Test genre resolution from grading standard"""
    # Test narrative
    mock_standard = MagicMock()
    mock_standard.title = "五年级记叙文评分标准"
    
    genre = _resolve_genre_from_standard(mock_standard)
    assert genre == 'narrative'
    
    # Test expository
    mock_standard.title = "五年级说明文评分标准"
    genre = _resolve_genre_from_standard(mock_standard)
    assert genre == 'expository'
    
    # Test argumentative
    mock_standard.title = "五年级议论文评分标准"
    genre = _resolve_genre_from_standard(mock_standard)
    assert genre == 'argumentative'
    
    # Test fallback
    mock_standard.title = "未知类型评分标准"
    genre = _resolve_genre_from_standard(mock_standard)
    assert genre == 'narrative'
    
    # Test None standard
    genre = _resolve_genre_from_standard(None)
    assert genre == 'narrative'


def test_get_fallback_meta():
    """Test fallback metadata"""
    meta = _get_fallback_meta()
    
    assert meta['student_id'] == 'unknown'
    assert meta['grade'] == '五年级'
    assert meta['genre'] == 'narrative'
    assert meta['topic'] == '未知题目'
    assert meta['words'] == 0