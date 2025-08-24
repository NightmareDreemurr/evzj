"""
Tests for the path resolver utility to ensure it correctly handles
Windows paths and resolves them to local uploads directory.
"""
import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock

from app.utils.path_resolver import resolve_upload_path, get_friendly_image_message


def test_resolve_upload_path_existing_file():
    """Test that existing files are returned as-is"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        try:
            result = resolve_upload_path(tmp_file.name)
            assert result == tmp_file.name
        finally:
            os.unlink(tmp_file.name)


def test_resolve_upload_path_windows_absolute_path():
    """Test resolving Windows absolute paths to local uploads directory"""
    # Create a temporary uploads directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        uploads_dir = os.path.join(temp_dir, 'uploads')
        os.makedirs(uploads_dir)
        
        # Create a test image file
        test_image = os.path.join(uploads_dir, 'test_image.jpg')
        with open(test_image, 'w') as f:
            f.write('fake image content')
        
        # Mock the uploads directory detection
        with patch('app.utils.path_resolver._get_uploads_directory', return_value=uploads_dir):
            # Test Windows absolute path
            windows_path = r'D:\Github\evzj\uploads\test_image.jpg'
            result = resolve_upload_path(windows_path)
            assert result == test_image
            
            # Test different separators
            unix_style_path = 'D:/Github/evzj/uploads/test_image.jpg'
            result = resolve_upload_path(unix_style_path)
            assert result == test_image


def test_resolve_upload_path_filename_only():
    """Test resolving by filename when full path fails"""
    with tempfile.TemporaryDirectory() as temp_dir:
        uploads_dir = os.path.join(temp_dir, 'uploads')
        os.makedirs(uploads_dir)
        
        # Create a test image file
        test_image = os.path.join(uploads_dir, 'image123.jpg')
        with open(test_image, 'w') as f:
            f.write('fake image content')
        
        # Mock the uploads directory detection
        with patch('app.utils.path_resolver._get_uploads_directory', return_value=uploads_dir):
            # Test with completely different path but same filename
            different_path = '/some/other/path/image123.jpg'
            result = resolve_upload_path(different_path)
            assert result == test_image


def test_resolve_upload_path_nonexistent():
    """Test that nonexistent files return None"""
    with tempfile.TemporaryDirectory() as temp_dir:
        uploads_dir = os.path.join(temp_dir, 'uploads')
        os.makedirs(uploads_dir)
        
        with patch('app.utils.path_resolver._get_uploads_directory', return_value=uploads_dir):
            result = resolve_upload_path('D:\\some\\nonexistent\\file.jpg')
            assert result is None


def test_resolve_upload_path_invalid_input():
    """Test handling of invalid inputs"""
    assert resolve_upload_path(None) is None
    assert resolve_upload_path('') is None
    assert resolve_upload_path(123) is None


def test_get_friendly_image_message():
    """Test that friendly message is returned"""
    message = get_friendly_image_message()
    assert message == "图片缺失或不可访问"
    assert isinstance(message, str)
    assert len(message) > 0


def test_uploads_directory_detection():
    """Test uploads directory detection with various configurations"""
    from app.utils.path_resolver import _get_uploads_directory
    
    # Test with environment variable
    with patch.dict(os.environ, {'UPLOADS_DIR': '/custom/uploads'}):
        with patch('os.path.isdir', return_value=True):
            result = _get_uploads_directory()
            assert result == '/custom/uploads'
    
    # Test with Flask app config
    mock_app = MagicMock()
    mock_app.config = {'UPLOAD_FOLDER': '/app/uploads'}
    with patch('app.utils.path_resolver.current_app', mock_app):
        with patch('os.path.isdir', return_value=True):
            result = _get_uploads_directory()
            assert result == '/app/uploads'


if __name__ == '__main__':
    pytest.main([__file__])