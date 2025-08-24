"""
Path resolution utilities for handling image paths across different environments.

This module provides utilities to resolve image paths that may contain Windows-style
absolute paths to the local uploads directory, ensuring cross-platform compatibility.
"""
import os
import re
from pathlib import Path
from typing import Optional
from flask import current_app


def resolve_upload_path(path_str: str) -> Optional[str]:
    """
    Resolve an upload image path to a local accessible path.
    
    This function handles cases where the stored path might be an absolute Windows path
    from another machine, and attempts to resolve it to the local uploads directory.
    
    Args:
        path_str: The path string to resolve (may be absolute Windows path or relative)
        
    Returns:
        Resolved path if it exists, None otherwise
        
    Examples:
        >>> resolve_upload_path("uploads/image.jpg")  # Already relative
        "uploads/image.jpg"  (if exists)
        
        >>> resolve_upload_path("D:\\Github\\evzj\\uploads\\image.jpg")  # Windows abs path
        "/app/uploads/image.jpg"  (if exists locally)
    """
    if not path_str or not isinstance(path_str, str):
        return None
    
    # First, try the path as-is
    if os.path.exists(path_str):
        return path_str
    
    # Get the configured uploads directory
    uploads_dir = _get_uploads_directory()
    if not uploads_dir:
        return None
    
    # If the path contains "uploads" (case-insensitive), extract the subpath from "uploads" onward
    uploads_match = re.search(r'(?i)uploads[/\\](.+)', path_str)
    if uploads_match:
        relative_subpath = uploads_match.group(1)
        # Normalize path separators for current OS
        relative_subpath = relative_subpath.replace('\\', os.sep).replace('/', os.sep)
        
        # Try combining with local uploads directory
        candidate_path = os.path.join(uploads_dir, relative_subpath)
        if os.path.exists(candidate_path):
            return candidate_path
    
    # Also try extracting just the filename and looking for it in uploads
    filename = os.path.basename(path_str)
    if filename:
        candidate_path = os.path.join(uploads_dir, filename)
        if os.path.exists(candidate_path):
            return candidate_path
    
    # Path could not be resolved
    return None


def _get_uploads_directory() -> Optional[str]:
    """
    Get the uploads directory from configuration.
    
    Returns:
        Path to uploads directory, or None if not configured
    """
    try:
        # Try environment variable first
        uploads_dir = os.getenv('UPLOADS_DIR')
        if uploads_dir and os.path.isdir(uploads_dir):
            return uploads_dir
        
        # Fall back to Flask app config
        if current_app:
            upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if upload_folder and os.path.isdir(upload_folder):
                return upload_folder
        
        # Default fallback
        project_root = Path(__file__).parent.parent.parent
        default_uploads = project_root / 'uploads'
        if default_uploads.exists():
            return str(default_uploads)
            
    except Exception:
        # Silently handle any configuration errors
        pass
    
    return None


def get_friendly_image_message() -> str:
    """
    Get a friendly message to display when an image cannot be found.
    
    Returns:
        Localized friendly message for missing images
    """
    return "图片缺失或不可访问"