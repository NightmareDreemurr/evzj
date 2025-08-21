"""
Tests for download routes functionality.
"""
import pytest
from unittest.mock import Mock, patch
import tempfile
import os

from app import create_app


@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def test_user():
    """Create a mock test user"""
    user = Mock()
    user.id = 1
    user.role = 'teacher'
    user.full_name = 'Test Teacher'
    return user


def test_download_essay_report_route_requires_login(app):
    """Test that download route requires authentication"""
    with app.test_client() as client:
        response = client.get('/assignments/essays/1/report/download')
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location or 'login' in response.location


def test_download_assignment_report_route_requires_login(app):
    """Test that assignment download route requires authentication"""
    with app.test_client() as client:
        response = client.get('/assignments/1/report/download')
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location or 'login' in response.location


@patch('app.dao.evaluation_dao.load_evaluation_by_essay')
@patch('app.reporting.docx_renderer.render_essay_docx')
def test_download_essay_report_success(mock_render, mock_load, app, test_user):
    """Test successful essay report download"""
    from app.schemas.evaluation import EvaluationResult, Meta, Scores
    import tempfile
    import os
    
    # Mock evaluation data
    mock_evaluation = EvaluationResult(
        meta=Meta(
            student="Test Student",
            class_="Test Class", 
            teacher="Test Teacher",
            topic="Test Topic",
            date="2024-08-21"
        ),
        scores=Scores(total=85.0, rubrics=[])
    )
    mock_load.return_value = mock_evaluation
    
    # Mock file creation
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
        temp_file.write(b'fake docx content')
        mock_render.return_value = temp_file.name
        
        try:
            with app.test_client() as client:
                # Login first
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(test_user.id)
                    sess['_fresh'] = True
                
                response = client.get('/assignments/essays/1/report/download')
                
                # Should return file
                assert response.status_code == 200
                assert response.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                assert 'attachment' in response.headers.get('Content-Disposition', '')
                
                # Check mocks were called
                mock_load.assert_called_once_with(1)
                mock_render.assert_called_once()
                
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


@patch('app.dao.evaluation_dao.load_evaluation_by_essay')
def test_download_essay_report_not_found(mock_load, app, test_user):
    """Test essay download when evaluation not found"""
    mock_load.return_value = None
    
    with app.test_client() as client:
        # Login first  
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.get('/assignments/essays/999/report/download', follow_redirects=True)
        
        # Should redirect with error message
        assert response.status_code == 200
        # In a real test, we'd check for flash message in the response


@patch('app.dao.evaluation_dao.load_evaluations_by_assignment')
@patch('app.reporting.docx_renderer.render_assignment_docx')
def test_download_assignment_report_success(mock_render, mock_load, app, test_user):
    """Test successful assignment report download"""
    from app.schemas.evaluation import EvaluationResult, Meta, Scores
    import tempfile
    import os
    
    # Mock evaluation data
    mock_evaluations = [
        EvaluationResult(
            meta=Meta(
                student="Student 1",
                class_="Test Class",
                teacher="Test Teacher", 
                topic="Test Assignment",
                date="2024-08-21"
            ),
            scores=Scores(total=85.0, rubrics=[])
        )
    ]
    mock_load.return_value = mock_evaluations
    
    # Mock file creation
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
        temp_file.write(b'fake assignment docx content')
        mock_render.return_value = temp_file.name
        
        try:
            with app.test_client() as client:
                # Login first
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(test_user.id)
                    sess['_fresh'] = True
                
                response = client.get('/assignments/1/report/download')
                
                # Should return file
                assert response.status_code == 200
                assert response.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                assert 'attachment' in response.headers.get('Content-Disposition', '')
                
                # Check mocks were called
                mock_load.assert_called_once_with(1)
                mock_render.assert_called_once_with(1, mock_evaluations)
                
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)


@patch('app.dao.evaluation_dao.load_evaluations_by_assignment')
def test_download_assignment_report_no_data(mock_load, app, test_user):
    """Test assignment download when no evaluation data found"""
    mock_load.return_value = []
    
    with app.test_client() as client:
        # Login first
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.get('/assignments/999/report/download', follow_redirects=True)
        
        # Should redirect with warning message
        assert response.status_code == 200
        # In a real test, we'd check for flash message in the response


@patch('app.dao.evaluation_dao.load_evaluations_by_assignment')  
@patch('app.reporting.docx_renderer.render_assignment_docx')
def test_download_assignment_report_not_implemented(mock_render, mock_load, app, test_user):
    """Test assignment download when NotImplementedError is raised"""
    from app.schemas.evaluation import EvaluationResult, Meta, Scores
    
    # Mock evaluation data
    mock_evaluations = [
        EvaluationResult(
            meta=Meta(
                student="Student 1",
                class_="Test Class",
                teacher="Test Teacher",
                topic="Test Assignment", 
                date="2024-08-21"
            ),
            scores=Scores(total=85.0, rubrics=[])
        )
    ]
    mock_load.return_value = mock_evaluations
    mock_render.side_effect = NotImplementedError("Assignment summary not implemented")
    
    with app.test_client() as client:
        # Login first
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True
        
        response = client.get('/assignments/1/report/download', follow_redirects=True)
        
        # Should redirect with info message about fallback
        assert response.status_code == 200
        # In a real test, we'd check for flash message about representative essay


def test_download_filename_sanitization():
    """Test that download filenames are properly sanitized"""
    from app.schemas.evaluation import EvaluationResult, Meta, Scores
    from app.reporting.docx_renderer import render_essay_docx
    
    # Create evaluation with problematic characters in meta
    evaluation = EvaluationResult(
        meta=Meta(
            student="张 三/四",  # Name with space and slash
            class_="五年级1班",
            teacher="李老师", 
            topic="我的/家乡 作文",  # Topic with slash and space
            date="2024-08-21"
        ),
        scores=Scores(total=85.0, rubrics=[])
    )
    
    # Render and check filename
    result_path = render_essay_docx(evaluation)
    filename = os.path.basename(result_path)
    
    # Check problematic characters are replaced
    assert ' ' not in filename
    assert '/' not in filename
    assert filename.endswith('.docx')
    
    # Cleanup
    if os.path.exists(result_path):
        os.unlink(result_path)