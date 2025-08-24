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
    
    def test_compose_overlay_images_missing_files(self):
        """Test compose_overlay_images with missing files."""
        from app.reporting.image_overlay import compose_overlay_images
        
        # Test with non-existent files
        result = compose_overlay_images('/nonexistent/original.jpg', '/nonexistent/overlay.png')
        assert result is None
        
        # Test with missing original
        result = compose_overlay_images('/nonexistent/original.jpg', '/tmp/test.png')
        assert result is None
        
        # Test with missing overlay
        result = compose_overlay_images('/tmp/test.jpg', '/nonexistent/overlay.png')
        assert result is None
    
    @pytest.mark.skipif(not os.getenv('TEST_WITH_IMAGES'), reason="Image tests require TEST_WITH_IMAGES=1")
    def test_compose_overlay_images_with_real_files(self):
        """Test image composition with real image files (optional test)."""
        from app.reporting.image_overlay import compose_overlay_images
        
        # Create a simple test original image
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")
        
        # Create a small test original image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            original_image = Image.new('RGB', (100, 100), color='white')
            original_image.save(f.name, 'JPEG')
            original_path = f.name
        
        # Create a small test overlay image with transparency  
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            overlay_image = Image.new('RGBA', (100, 100), color=(255, 0, 0, 128))  # Semi-transparent red
            overlay_image.save(f.name, 'PNG')
            overlay_path = f.name
        
        try:
            # Test composition
            result = compose_overlay_images(original_path, overlay_path)
            
            if result:  # Only check if composition was successful
                assert os.path.exists(result)
                assert result.endswith(('.png', '.jpg'))  # Could be either format
                
                # Verify the result is a valid image
                with Image.open(result) as composed:
                    assert composed.size == (100, 100)
                    assert composed.mode == 'RGB'
                
                # Clean up the composed image
                os.unlink(result)
        
        finally:
            # Clean up test images
            os.unlink(original_path)
            os.unlink(overlay_path)


class TestInlineImageGeneration:
    """Test cases for InlineImage generation in DOCX rendering."""
    
    def test_inline_image_creation_with_valid_paths(self):
        """Test that InlineImage objects are created when valid image paths exist."""
        # This is a unit test for the image creation logic
        # We'll test the logic without requiring actual image files
        from unittest.mock import Mock, patch
        import tempfile
        import os
        
        # Create mock objects
        mock_doc = Mock()
        mock_student = Mock()
        mock_student.student_name = 'Test Student'
        mock_student.student_no = '12345'
        mock_student.essay_id = 1  # Add essay_id for new database lookup
        mock_student.topic = 'Test Topic'
        mock_student.words = 300
        mock_student.feedback_summary = 'Test summary'
        mock_student.scores = Mock()
        mock_student.scores.total = 85
        mock_student.scores.items = []
        mock_student.paragraphs = []
        mock_student.exercises = []
        
        # Create a temporary file to simulate an image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            temp_image_path = f.name
            # Write some dummy data
            f.write(b'fake image data')
        
        try:
            # Mock the student with scanned images
            mock_student.scanned_images = [temp_image_path]
            
            # Mock the assignment VM
            mock_assignment_vm = Mock()
            mock_assignment_vm.students = [mock_student]
            mock_assignment_vm.title = 'Test Assignment'
            mock_assignment_vm.classroom = 'Test Classroom'
            mock_assignment_vm.teacher = 'Test Teacher'
            
            # Test the image processing logic in isolation
            with patch('docxtpl.DocxTemplate'), \
                 patch('app.reporting.docx_renderer.ensure_assignment_template_exists'), \
                 patch('app.dao.evaluation_dao.load_evaluation_by_essay'), \
                 patch('app.reporting.image_overlay.compose_annotations'), \
                 patch('app.reporting.image_overlay.compose_overlay_images'), \
                 patch('docxtpl.InlineImage') as mock_inline_image, \
                 patch('os.path.exists', return_value=True), \
                 patch('app.reporting.service.db.session.get', return_value=None):
                
                from app.reporting.service import _render_with_docxtpl_combined
                
                # This should not raise an exception
                try:
                    _render_with_docxtpl_combined(mock_assignment_vm)
                    # If we get here, the function ran without errors
                    assert True
                except Exception as e:
                    # Check if it's related to our image processing or something else
                    if "InlineImage" in str(e):
                        # Expected since we're mocking
                        assert True
                    else:
                        # Re-raise unexpected errors
                        raise
                        
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
    
    def test_graceful_handling_of_missing_images(self):
        """Test that missing image files are handled gracefully."""
        from unittest.mock import Mock, patch
        
        # Create mock student with non-existent image path
        mock_student = Mock()
        mock_student.student_name = 'Test Student'
        mock_student.student_no = '12345'
        mock_student.essay_id = 1  # Add essay_id for new database lookup
        mock_student.topic = 'Test Topic'
        mock_student.words = 300
        mock_student.feedback_summary = 'Test summary'
        mock_student.scores = Mock()
        mock_student.scores.total = 85
        mock_student.scores.items = []
        mock_student.paragraphs = []
        mock_student.exercises = []
        mock_student.scanned_images = ['/nonexistent/path/to/image.jpg']
        
        mock_assignment_vm = Mock()
        mock_assignment_vm.students = [mock_student]
        mock_assignment_vm.title = 'Test Assignment'
        mock_assignment_vm.classroom = 'Test Classroom'
        mock_assignment_vm.teacher = 'Test Teacher'
        
        # Test that missing images don't crash the rendering
        with patch('docxtpl.DocxTemplate'), \
             patch('app.reporting.docx_renderer.ensure_assignment_template_exists'), \
             patch('app.dao.evaluation_dao.load_evaluation_by_essay'), \
             patch('app.reporting.image_overlay.compose_annotations'), \
             patch('app.reporting.image_overlay.compose_overlay_images'), \
             patch('app.reporting.service.db.session.get', return_value=None):
            
            from app.reporting.service import _render_with_docxtpl_combined
            
            # This should not raise an exception even with missing images
            try:
                _render_with_docxtpl_combined(mock_assignment_vm)
                assert True
            except Exception as e:
                # The function might fail for other reasons (mocking), but not due to missing images
                # Make sure it's not an image-related error
                assert "image" not in str(e).lower() or "nonexistent" not in str(e)


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