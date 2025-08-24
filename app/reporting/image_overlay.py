"""
Image overlay module for composition of original essay images with teacher annotations.

This module provides functionality to overlay teacher annotations (circles, rectangles, 
highlights, etc.) onto the original essay scanned images for enhanced DOCX reports.
"""
import os
import tempfile
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


def compose_annotations(original_image_path: str, annotations: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    """
    Compose teacher annotations onto the original essay image.
    
    Args:
        original_image_path: Path to the original scanned essay image
        annotations: List of annotation dictionaries with format:
            {
                'type': 'circle'|'rectangle'|'highlight'|'text',
                'coordinates': [x1, y1, x2, y2] or [x, y, radius],
                'color': 'red'|'blue'|'green'|[r, g, b],
                'text': 'annotation text' (for text annotations),
                'thickness': int (line thickness, default 2)
            }
    
    Returns:
        Path to the composed image file, or None if no annotations or error occurred
    """
    if not PIL_AVAILABLE:
        logger.warning("PIL/Pillow not available, skipping image composition")
        return None
    
    if not annotations:
        logger.debug("No annotations provided, skipping image composition")
        return None
    
    if not os.path.exists(original_image_path):
        logger.warning(f"Original image not found: {original_image_path}")
        return None
    
    try:
        # Load the original image
        with Image.open(original_image_path) as original:
            # Convert to RGB if necessary to ensure compatibility
            if original.mode != 'RGB':
                original = original.convert('RGB')
            
            # Create a copy for drawing
            composite = original.copy()
            draw = ImageDraw.Draw(composite)
            
            # Process each annotation
            for annotation in annotations:
                _draw_annotation(draw, annotation, composite.size)
            
            # Save to temporary file
            temp_dir = tempfile.gettempdir()
            temp_filename = f"essay_annotated_{os.path.basename(original_image_path)}"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            composite.save(temp_path, format='PNG', quality=95)
            logger.info(f"Composed annotated image saved to: {temp_path}")
            return temp_path
            
    except Exception as e:
        logger.error(f"Failed to compose annotations on image {original_image_path}: {e}")
        return None


def _draw_annotation(draw: ImageDraw.Draw, annotation: Dict[str, Any], image_size: tuple):
    """
    Draw a single annotation on the image.
    
    Args:
        draw: PIL ImageDraw object
        annotation: Annotation dictionary
        image_size: (width, height) of the image
    """
    annotation_type = annotation.get('type', 'rectangle').lower()
    coordinates = annotation.get('coordinates', [])
    color = _parse_color(annotation.get('color', 'red'))
    thickness = annotation.get('thickness', 2)
    
    if not coordinates:
        logger.warning(f"No coordinates provided for annotation: {annotation}")
        return
    
    try:
        if annotation_type == 'rectangle':
            if len(coordinates) >= 4:
                x1, y1, x2, y2 = coordinates[:4]
                draw.rectangle([x1, y1, x2, y2], outline=color, width=thickness)
        
        elif annotation_type == 'circle':
            if len(coordinates) >= 3:
                x, y, radius = coordinates[:3]
                x1, y1 = x - radius, y - radius
                x2, y2 = x + radius, y + radius
                draw.ellipse([x1, y1, x2, y2], outline=color, width=thickness)
        
        elif annotation_type == 'highlight':
            if len(coordinates) >= 4:
                x1, y1, x2, y2 = coordinates[:4]
                # Semi-transparent highlight
                highlight_color = color + (128,)  # Add alpha
                draw.rectangle([x1, y1, x2, y2], fill=highlight_color, outline=color, width=1)
        
        elif annotation_type == 'text':
            if len(coordinates) >= 2:
                x, y = coordinates[:2]
                text = annotation.get('text', 'Annotation')
                try:
                    # Try to use a default font, fall back to built-in if not available
                    font = ImageFont.load_default()
                except:
                    font = None
                draw.text((x, y), text, fill=color, font=font)
        
        else:
            logger.warning(f"Unknown annotation type: {annotation_type}")
            
    except Exception as e:
        logger.error(f"Failed to draw annotation {annotation}: {e}")


def _parse_color(color) -> tuple:
    """
    Parse color specification into RGB tuple.
    
    Args:
        color: Color as string ('red', 'blue', etc.) or RGB list/tuple
        
    Returns:
        RGB tuple (r, g, b)
    """
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return tuple(color[:3])
    
    color_map = {
        'red': (255, 0, 0),
        'blue': (0, 0, 255),
        'green': (0, 255, 0),
        'yellow': (255, 255, 0),
        'orange': (255, 165, 0),
        'purple': (128, 0, 128),
        'black': (0, 0, 0),
        'white': (255, 255, 255)
    }
    
    return color_map.get(str(color).lower(), (255, 0, 0))  # Default to red


def compose_overlay_images(original_image_path: str, overlay_image_path: str) -> Optional[str]:
    """
    Compose an original image with an annotation overlay image.
    
    Args:
        original_image_path: Path to the original scanned essay image
        overlay_image_path: Path to the annotation overlay image (PNG with transparency)
    
    Returns:
        Path to the composed image file, or None if composition failed
    """
    if not PIL_AVAILABLE:
        logger.warning("PIL/Pillow not available, skipping image composition")
        return None
    
    if not os.path.exists(original_image_path):
        logger.warning(f"Original image not found: {original_image_path}")
        return None
        
    if not os.path.exists(overlay_image_path):
        logger.warning(f"Overlay image not found: {overlay_image_path}")
        return None
    
    try:
        # Load the original image
        with Image.open(original_image_path) as original:
            # Convert to RGBA to ensure proper transparency handling
            if original.mode != 'RGBA':
                original = original.convert('RGBA')
            
            # Load the overlay image
            with Image.open(overlay_image_path) as overlay:
                # Ensure overlay is in RGBA mode for transparency
                if overlay.mode != 'RGBA':
                    overlay = overlay.convert('RGBA')
                
                # Resize overlay to match original if they have different sizes
                if overlay.size != original.size:
                    overlay = overlay.resize(original.size, Image.Resampling.LANCZOS)
                
                # Composite the images (overlay on top of original)
                composed = Image.alpha_composite(original, overlay)
                
                # Convert back to RGB for DOCX compatibility
                composed = composed.convert('RGB')
                
                # Save to temporary file
                temp_dir = tempfile.gettempdir()
                temp_filename = f"essay_composed_{os.path.basename(original_image_path)}"
                temp_path = os.path.join(temp_dir, temp_filename)
                
                composed.save(temp_path, format='PNG', quality=95)
                logger.info(f"Composed image with overlay saved to: {temp_path}")
                return temp_path
                
    except Exception as e:
        logger.error(f"Failed to compose overlay images {original_image_path} + {overlay_image_path}: {e}")
        return None


def cleanup_temp_images():
    """
    Clean up temporary annotated images from the temp directory.
    Call this periodically to avoid accumulating temporary files.
    """
    try:
        temp_dir = tempfile.gettempdir()
        for filename in os.listdir(temp_dir):
            if (filename.startswith('essay_annotated_') or filename.startswith('essay_composed_')) and filename.endswith(('.png', '.jpg', '.jpeg')):
                temp_path = os.path.join(temp_dir, filename)
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Cleaned up temporary image: {temp_path}")
                except OSError:
                    pass  # File might be in use or already deleted
    except Exception as e:
        logger.warning(f"Failed to cleanup temporary images: {e}")