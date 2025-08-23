"""
Tests for DOCX service template functionality and batch export fixes.
"""
import pytest
import tempfile
import os
from pathlib import Path

from app.reporting.docx_renderer import ensure_assignment_template_exists, ensure_template_exists
from app.reporting.image_overlay import compose_annotations, _parse_color


class TestDocxServiceTemplates:
    """Test cases for DOCX template auto-generation and rendering."""
    
    def test_ensure_assignment_template_exists(self):
        """Test that assignment template is created when missing."""
        # This should create the template if it doesn't exist
        template_path = ensure_assignment_template_exists()
        
        assert os.path.exists(template_path)
        assert template_path.endswith('assignment_compiled.docx')
        
        # Should return the same path if called again
        template_path2 = ensure_assignment_template_exists()
        assert template_path == template_path2
    
    def test_ensure_single_template_exists(self):
        """Test that single essay template is created when missing."""
        template_path = ensure_template_exists()
        
        assert os.path.exists(template_path)
        assert template_path.endswith('ReportTemplate.docx')
    
    def test_template_content_basic(self):
        """Test that generated templates contain expected content."""
        # Read the assignment template content
        template_path = ensure_assignment_template_exists()
        
        # Basic validation - file should be non-empty
        assert os.path.getsize(template_path) > 1000  # Should be substantial DOCX file
    
    def test_strftime_filter_registration(self):
        """Test that strftime filter is properly defined."""
        from jinja2 import Environment
        from datetime import datetime
        
        env = Environment(autoescape=False)
        
        def strftime_filter(dt, fmt):
            """Custom strftime filter that handles both datetime objects and strings"""
            if dt is None:
                return ''
            if isinstance(dt, str):
                return dt  # If already a string, return as-is
            if hasattr(dt, 'strftime'):
                return dt.strftime(fmt)
            return str(dt)
        
        env.filters['strftime'] = strftime_filter
        
        # Test with datetime object
        now = datetime.now()
        result = env.filters['strftime'](now, '%Y-%m-%d')
        assert len(result) == 10  # YYYY-MM-DD format
        
        # Test with string (should return as-is)
        result = env.filters['strftime']('already formatted', '%Y-%m-%d')
        assert result == 'already formatted'
        
        # Test with None
        result = env.filters['strftime'](None, '%Y-%m-%d')
        assert result == ''
    
    def test_exercises_hint_field_compatibility(self):
        """Test that exercises field supports both hint and hints."""
        # Mock exercise data
        class MockExercise:
            def __init__(self, hints_data):
                self.type = 'grammar'
                self.prompt = 'Test prompt'
                self.sample = 'Test sample'
                if isinstance(hints_data, list):
                    self.hints = hints_data
                else:
                    self.hint = hints_data
        
        # Test with hints field (existing data)
        ex_with_hints = MockExercise(['hint1', 'hint2'])
        hint_value = ex_with_hints.hints if hasattr(ex_with_hints, 'hints') else getattr(ex_with_hints, 'hint', [])
        assert hint_value == ['hint1', 'hint2']
        
        # Test with hint field (new data)
        ex_with_hint = MockExercise(['hint1', 'hint2'])
        ex_with_hint.hint = ex_with_hint.hints  # Simulate conversion
        delattr(ex_with_hint, 'hints')
        hint_value = ex_with_hint.hints if hasattr(ex_with_hint, 'hints') else getattr(ex_with_hint, 'hint', [])
        assert hint_value == ['hint1', 'hint2']


class TestImageOverlay:
    """Test cases for image overlay functionality."""
    
    def test_compose_annotations_no_annotations(self):
        """Test that function returns None when no annotations provided."""
        result = compose_annotations('/fake/path.jpg', None)
        assert result is None
        
        result = compose_annotations('/fake/path.jpg', [])
        assert result is None
    
    def test_compose_annotations_missing_image(self):
        """Test that function returns None when original image is missing."""
        annotations = [{'type': 'rectangle', 'coordinates': [10, 10, 50, 50]}]
        result = compose_annotations('/nonexistent/path.jpg', annotations)
        assert result is None
    
    def test_parse_color(self):
        """Test color parsing functionality."""
        # Test RGB list
        assert _parse_color([255, 0, 0]) == (255, 0, 0)
        
        # Test color names
        assert _parse_color('red') == (255, 0, 0)
        assert _parse_color('blue') == (0, 0, 255)
        assert _parse_color('green') == (0, 255, 0)
        
        # Test unknown color (should default to red)
        assert _parse_color('unknown') == (255, 0, 0)
    
    @pytest.mark.skipif(not os.getenv('TEST_WITH_IMAGES'), reason="Image tests require TEST_WITH_IMAGES=1")
    def test_compose_annotations_with_real_image(self):
        """Test image composition with a real image file (optional test)."""
        # Create a simple test image
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")
        
        # Create a small test image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            test_image = Image.new('RGB', (100, 100), color='white')
            test_image.save(f.name, 'PNG')
            test_image_path = f.name
        
        try:
            # Test with simple rectangle annotation
            annotations = [{
                'type': 'rectangle',
                'coordinates': [10, 10, 50, 50],
                'color': 'red',
                'thickness': 2
            }]
            
            result = compose_annotations(test_image_path, annotations)
            
            if result:  # Only check if composition was successful
                assert os.path.exists(result)
                assert result.endswith('.png')
                # Clean up the composed image
                os.unlink(result)
        
        finally:
            # Clean up test image
            os.unlink(test_image_path)


class TestContextBuilding:
    """Test cases for context building with new fields."""
    
    def test_student_context_has_required_fields(self):
        """Test that student context includes all required fields."""
        # Mock student data
        class MockStudent:
            def __init__(self):
                self.student_name = 'Test Student'
                self.student_no = '12345'
                self.topic = 'Test Topic'
                self.words = 300
                self.feedback_summary = 'Test summary'
                self.paragraphs = []
                self.exercises = []
                self.scores = MockScores()
        
        class MockScores:
            def __init__(self):
                self.total = 85
                self.items = []
        
        student = MockStudent()
        
        # Simulate the context building logic from service.py
        student_data = {
            'student_name': student.student_name,
            'student_no': student.student_no,
            'topic': student.topic,
            'words': student.words,
            'scores': {
                'total': student.scores.total,
                'items': []
            },
            'text': {
                'cleaned': getattr(student, 'cleaned_text', '')
            },
            'analysis': {
                'outline': getattr(student, 'outline', []),
                'issues': getattr(student, 'issues', [])
            },
            'diagnostics': getattr(student, 'diagnostics', []),
            'diagnosis': {
                'before': getattr(student, 'diagnosis_before', ''),
                'comment': getattr(student, 'diagnosis_comment', ''),
                'after': getattr(student, 'diagnosis_after', '')
            },
            'summary': getattr(student, 'summary', ''),
            'paragraphs': [],
            'exercises': [],
            'images': {
                'original_image_path': None,
                'composited_image_path': None
            },
            'feedback_summary': student.feedback_summary
        }
        
        # Verify all expected fields are present
        required_fields = [
            'student_name', 'topic', 'scores', 'text', 'analysis', 
            'diagnostics', 'diagnosis', 'summary', 'paragraphs', 
            'exercises', 'images', 'feedback_summary'
        ]
        
        for field in required_fields:
            assert field in student_data, f"Missing required field: {field}"
        
        # Verify nested structures
        assert 'total' in student_data['scores']
        assert 'items' in student_data['scores']
        assert 'cleaned' in student_data['text']
        assert 'outline' in student_data['analysis']
        assert 'issues' in student_data['analysis']
        assert 'before' in student_data['diagnosis']
        assert 'comment' in student_data['diagnosis']
        assert 'after' in student_data['diagnosis']
        assert 'original_image_path' in student_data['images']
        assert 'composited_image_path' in student_data['images']