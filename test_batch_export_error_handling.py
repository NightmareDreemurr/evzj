#!/usr/bin/env python3
"""
Test cases specifically for the batch export error handling fix.

This module tests the improved error handling implemented for batch DOCX export
to address the issue where "No teacher view documents could be generated" 
was shown without detailed information about what went wrong.
"""

import pytest
from unittest.mock import Mock, patch
from app.reporting.service import (
    _render_assignment_combined_teacher_view,
    _render_assignment_zip_teacher_view,
)
from app.reporting.viewmodels import AssignmentReportVM, StudentReportVM, ScoreVM

class TestBatchExportErrorHandling:
    """Test cases for improved batch export error handling."""
    
    def test_combined_mode_all_failures_detailed_error(self):
        """Test that combined mode provides detailed error when all students fail."""
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="Test Assignment",
            classroom={"name": "Test Class", "id": 1},
            teacher={"name": "Test Teacher", "id": 1},
            students=[
                StudentReportVM(
                    student_id=1,
                    student_name="Student 1",
                    essay_id=101,
                    topic="Test Topic",
                    scores=ScoreVM(total=85.0)
                ),
                StudentReportVM(
                    student_id=2,
                    student_name="Student 2", 
                    essay_id=102,
                    topic="Test Topic",
                    scores=ScoreVM(total=90.0)
                )
            ]
        )
        
        # Mock render_teacher_view_docx to always fail with different errors
        def mock_render_side_effect(essay_id):
            if essay_id == 101:
                raise ValueError("No evaluation data found for essay 101")
            elif essay_id == 102:
                raise ValueError("Essay 102 not found in database")
        
        with patch('app.reporting.service.render_teacher_view_docx') as mock_render:
            mock_render.side_effect = mock_render_side_effect
            
            with pytest.raises(ValueError) as exc_info:
                _render_assignment_combined_teacher_view(assignment_vm)
            
            error_msg = str(exc_info.value)
            
            # Check that error contains detailed information
            assert "Test Assignment" in error_msg
            assert "Student 1" in error_msg
            assert "Student 2" in error_msg
            assert "essay_id: 101" in error_msg 
            assert "essay_id: 102" in error_msg
            assert "No evaluation data found for essay 101" in error_msg
            assert "Essay 102 not found in database" in error_msg
            assert "Common causes:" in error_msg
            assert "Essays have no evaluation data" in error_msg
    
    def test_zip_mode_all_failures_detailed_error(self):
        """Test that ZIP mode provides detailed error when all students fail."""
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="Test Assignment",
            classroom={"name": "Test Class", "id": 1},
            teacher={"name": "Test Teacher", "id": 1},
            students=[
                StudentReportVM(
                    student_id=1,
                    student_name="Student 1",
                    essay_id=101,
                    topic="Test Topic",
                    scores=ScoreVM(total=85.0)
                )
            ]
        )
        
        with patch('app.reporting.service.render_teacher_view_docx') as mock_render:
            mock_render.side_effect = ValueError("No evaluation data found")
            
            with pytest.raises(ValueError) as exc_info:
                result = _render_assignment_zip_teacher_view(assignment_vm)
                # Need to consume the generator to trigger the validation
                list(result)
            
            error_msg = str(exc_info.value)
            
            # Check that ZIP mode has same detailed error format as combined mode
            assert "Test Assignment" in error_msg
            assert "Student 1" in error_msg
            assert "Common causes:" in error_msg
    
    @patch('app.reporting.service.render_teacher_view_docx')
    def test_zip_mode_partial_success(self, mock_render):
        """Test that ZIP mode works when some students succeed."""
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="Test Assignment",
            classroom={"name": "Test Class", "id": 1},
            teacher={"name": "Test Teacher", "id": 1},
            students=[
                StudentReportVM(
                    student_id=1,
                    student_name="Student 1",
                    essay_id=101,
                    topic="Test Topic",
                    scores=ScoreVM(total=85.0)
                ),
                StudentReportVM(
                    student_id=2,
                    student_name="Student 2",
                    essay_id=102,
                    topic="Test Topic", 
                    scores=ScoreVM(total=90.0)
                )
            ]
        )
        
        # Mock: first student succeeds, second fails
        def mock_render_side_effect(essay_id):
            if essay_id == 101:
                return b"Mock DOCX content for student 1"
            else:
                raise ValueError("No evaluation data found")
        
        mock_render.side_effect = mock_render_side_effect
        
        # Should succeed with partial results
        result = _render_assignment_zip_teacher_view(assignment_vm)
        
        # Consume the generator to check results
        chunks = list(result)
        assert len(chunks) > 0  # Should have some content
    
    def test_error_message_consistency(self):
        """Test that both modes provide consistent error messages."""
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="Test Assignment",
            classroom={"name": "Test Class", "id": 1},
            teacher={"name": "Test Teacher", "id": 1},
            students=[
                StudentReportVM(
                    student_id=1,
                    student_name="Student 1",
                    essay_id=101,
                    topic="Test Topic",
                    scores=ScoreVM(total=85.0)
                )
            ]
        )
        
        with patch('app.reporting.service.render_teacher_view_docx') as mock_render:
            mock_render.side_effect = ValueError("Test error")
            
            # Get error from combined mode
            with pytest.raises(ValueError) as combined_exc:
                _render_assignment_combined_teacher_view(assignment_vm)
            
            # Get error from ZIP mode
            with pytest.raises(ValueError) as zip_exc:
                result = _render_assignment_zip_teacher_view(assignment_vm)
                list(result)  # Consume generator
            
            combined_error = str(combined_exc.value)
            zip_error = str(zip_exc.value)
            
            # Check that both errors have the same structure
            for common_element in [
                "Test Assignment",
                "Student 1", 
                "essay_id: 101",
                "Test error",
                "Common causes:"
            ]:
                assert common_element in combined_error
                assert common_element in zip_error

    def test_logging_for_successful_exports(self):
        """Test that successful exports are properly logged."""
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="Test Assignment",
            classroom={"name": "Test Class", "id": 1},
            teacher={"name": "Test Teacher", "id": 1},
            students=[
                StudentReportVM(
                    student_id=1,
                    student_name="Student 1",
                    essay_id=101,
                    topic="Test Topic",
                    scores=ScoreVM(total=85.0)
                )
            ]
        )
        
        with patch('app.reporting.service.render_teacher_view_docx') as mock_render:
            mock_render.return_value = b"Mock DOCX content"
            
            with patch('app.reporting.service.logger') as mock_logger:
                # ZIP mode should succeed and log success
                result = _render_assignment_zip_teacher_view(assignment_vm)
                list(result)  # Consume generator
                
                # Should have logged success
                mock_logger.info.assert_called_with(
                    "ZIP export successful for all 1 students"
                )

if __name__ == '__main__':
    pytest.main([__file__, '-v'])