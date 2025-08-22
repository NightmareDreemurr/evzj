"""
Tests for the batch reporting functionality.
"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch

from app.reporting.viewmodels import (
    ScoreItemVM, ScoreVM, StudentReportVM, AssignmentReportVM,
    map_scores_to_vm, safe_get_student_name, safe_get_topic,
    safe_get_feedback, safe_get_original_paragraphs
)
from app.reporting.service import (
    build_student_vm, build_assignment_vm, render_student_docx, render_assignment_docx
)


class TestViewModels:
    """Test ViewModel mapping functionality."""
    
    def test_score_item_vm_creation(self):
        """Test ScoreItemVM creation."""
        item = ScoreItemVM(
            key="content", 
            name="内容", 
            score=18.5, 
            max_score=20.0
        )
        assert item.key == "content"
        assert item.name == "内容"
        assert item.score == 18.5
        assert item.max_score == 20.0
    
    def test_score_vm_creation(self):
        """Test ScoreVM creation with items."""
        items = [
            ScoreItemVM(key="content", name="内容", score=18.5, max_score=20.0),
            ScoreItemVM(key="structure", name="结构", score=16.0, max_score=20.0)
        ]
        score_vm = ScoreVM(total=85.0, items=items)
        assert score_vm.total == 85.0
        assert len(score_vm.items) == 2
    
    def test_student_report_vm_creation(self):
        """Test StudentReportVM creation."""
        scores = ScoreVM(total=85.0, items=[])
        student_vm = StudentReportVM(
            student_id=1,
            student_name="张三",
            student_no="2023001",
            essay_id=100,
            topic="我的家乡",
            words=500,
            scores=scores,
            feedback="写得很好",
            original_paragraphs=["第一段", "第二段"]
        )
        assert student_vm.student_id == 1
        assert student_vm.student_name == "张三"
        assert student_vm.essay_id == 100
        assert len(student_vm.original_paragraphs) == 2
    
    def test_assignment_report_vm_creation(self):
        """Test AssignmentReportVM creation."""
        students = [
            StudentReportVM(
                student_id=1, student_name="张三", essay_id=100, 
                topic="测试", scores=ScoreVM(total=85.0)
            )
        ]
        assignment_vm = AssignmentReportVM(
            assignment_id=1,
            title="作业一",
            classroom={"name": "五年级一班", "id": 1},
            teacher={"name": "李老师", "id": 1},
            students=students
        )
        assert assignment_vm.assignment_id == 1
        assert assignment_vm.title == "作业一"
        assert len(assignment_vm.students) == 1
    
    def test_safe_get_student_name_with_meta(self):
        """Test safe student name extraction with meta."""
        mock_eval = Mock()
        mock_eval.meta = Mock()
        mock_eval.meta.student = "张三"
        
        result = safe_get_student_name(mock_eval)
        assert result == "张三"
    
    def test_safe_get_student_name_fallback(self):
        """Test safe student name extraction with fallback."""
        mock_eval = Mock()
        mock_eval.meta = None
        
        result = safe_get_student_name(mock_eval)
        assert result == "未知学生"
    
    def test_safe_get_topic_with_meta(self):
        """Test safe topic extraction with meta."""
        mock_eval = Mock()
        mock_eval.meta = Mock()
        mock_eval.meta.topic = "我的家乡"
        
        result = safe_get_topic(mock_eval)
        assert result == "我的家乡"
    
    def test_safe_get_topic_fallback(self):
        """Test safe topic extraction with fallback."""
        mock_eval = Mock()
        mock_eval.meta = None
        
        result = safe_get_topic(mock_eval)
        assert result == "未知题目"
    
    def test_safe_get_feedback_with_diagnosis(self):
        """Test feedback extraction from diagnosis."""
        mock_eval = Mock()
        mock_eval.diagnosis = Mock()
        mock_eval.diagnosis.comment = "写得很好"
        mock_eval.diagnosis.before = "注意开头"
        mock_eval.diagnosis.after = "结尾可以改进"
        
        result = safe_get_feedback(mock_eval)
        assert "写得很好" in result
        assert "注意开头" in result
        assert "结尾可以改进" in result
    
    def test_safe_get_feedback_fallback(self):
        """Test feedback extraction fallback."""
        mock_eval = Mock()
        mock_eval.diagnosis = None
        mock_eval.summary = "总体不错"
        
        result = safe_get_feedback(mock_eval)
        assert result == "总体不错"
    
    def test_safe_get_feedback_empty_fallback(self):
        """Test feedback extraction empty fallback."""
        mock_eval = Mock()
        mock_eval.diagnosis = None
        del mock_eval.summary  # Remove summary attribute
        
        result = safe_get_feedback(mock_eval)
        assert result == "暂无评语"
    
    def test_safe_get_original_paragraphs_with_text(self):
        """Test paragraph extraction with text."""
        mock_eval = Mock()
        mock_eval.text = Mock()
        mock_eval.text.original = "第一段内容\n第二段内容\n\n第三段内容"
        
        result = safe_get_original_paragraphs(mock_eval)
        assert len(result) == 3
        assert "第一段内容" in result
        assert "第二段内容" in result
        assert "第三段内容" in result
    
    def test_safe_get_original_paragraphs_fallback(self):
        """Test paragraph extraction fallback."""
        mock_eval = Mock()
        mock_eval.text = None
        
        result = safe_get_original_paragraphs(mock_eval)
        assert result == ["原文内容不可用"]
    
    def test_map_scores_to_vm_with_rubrics(self):
        """Test score mapping with rubrics."""
        mock_eval = Mock()
        mock_eval.scores = Mock()
        mock_eval.scores.total = 85.0
        
        mock_rubric1 = Mock()
        mock_rubric1.name = "内容"
        mock_rubric1.score = 18.0
        mock_rubric1.max = 20.0
        
        mock_rubric2 = Mock()
        mock_rubric2.name = "结构"
        mock_rubric2.score = 16.0
        mock_rubric2.max = 20.0
        
        mock_eval.scores.rubrics = [mock_rubric1, mock_rubric2]
        
        result = map_scores_to_vm(mock_eval)
        assert result.total == 85.0
        assert len(result.items) == 2
        assert result.items[0].name == "内容"
        assert result.items[0].score == 18.0
    
    def test_map_scores_to_vm_fallback(self):
        """Test score mapping fallback."""
        mock_eval = Mock()
        mock_eval.scores = None
        
        result = map_scores_to_vm(mock_eval)
        assert result.total == 0.0
        assert len(result.items) == 0


class TestService:
    """Test service layer functionality."""
    
    @patch('app.reporting.service.load_evaluation_by_essay')
    @patch('app.reporting.service.db.session.get')
    def test_build_student_vm_success(self, mock_db_get, mock_load_eval):
        """Test successful student VM building."""
        # Mock evaluation
        mock_eval = Mock()
        mock_eval.meta = Mock()
        mock_eval.meta.student = "张三"
        mock_eval.meta.topic = "我的家乡"
        mock_eval.meta.words = 500
        mock_eval.scores = Mock()
        mock_eval.scores.total = 85.0
        mock_eval.scores.rubrics = []
        mock_eval.text = Mock()
        mock_eval.text.original = "原文内容"
        mock_eval.diagnosis = Mock()
        mock_eval.diagnosis.comment = "写得很好"
        mock_eval.diagnosis.before = None
        mock_eval.diagnosis.after = None
        
        mock_load_eval.return_value = mock_eval
        
        # Mock essay
        mock_essay = Mock()
        mock_essay.enrollment = Mock()
        mock_essay.enrollment.student_profile = Mock()
        mock_essay.enrollment.student_profile.id = 1
        mock_essay.enrollment.student_profile.user = Mock()
        mock_essay.enrollment.student_profile.user.full_name = "张三"
        
        mock_db_get.return_value = mock_essay
        
        result = build_student_vm(100)
        
        assert result is not None
        assert result.student_id == 1
        assert result.student_name == "张三"
        assert result.essay_id == 100
        assert result.topic == "我的家乡"
        assert result.scores.total == 85.0
    
    @patch('app.reporting.service.load_evaluation_by_essay')
    def test_build_student_vm_no_evaluation(self, mock_load_eval):
        """Test student VM building with no evaluation."""
        mock_load_eval.return_value = None
        
        result = build_student_vm(100)
        assert result is None
    
    @patch('app.reporting.service.db.session.query')
    def test_build_assignment_vm_success(self, mock_query):
        """Test successful assignment VM building."""
        # Mock assignment
        mock_assignment = Mock()
        mock_assignment.id = 1
        mock_assignment.title = "作业一"
        mock_assignment.teacher = Mock()
        mock_assignment.teacher.id = 1
        mock_assignment.teacher.user = Mock()
        mock_assignment.teacher.user.full_name = "李老师"
        mock_assignment.teacher.classrooms = [Mock()]
        mock_assignment.teacher.classrooms[0].name = "五年级一班"
        mock_assignment.teacher.classrooms[0].id = 1
        
        # Mock essays
        mock_essay = Mock()
        mock_essay.id = 100
        
        # Setup query chain
        mock_assignment_query = Mock()
        mock_assignment_query.filter.return_value.first.return_value = mock_assignment
        
        mock_essay_query = Mock()
        mock_essay_query.filter.return_value.all.return_value = [mock_essay]
        
        mock_query.side_effect = [mock_assignment_query, mock_essay_query]
        
        # Mock build_student_vm
        with patch('app.reporting.service.build_student_vm') as mock_build_student:
            mock_student_vm = Mock()
            mock_student_vm.student_name = "张三"
            mock_build_student.return_value = mock_student_vm
            
            result = build_assignment_vm(1)
            
            assert result is not None
            assert result.assignment_id == 1
            assert result.title == "作业一"
            assert result.teacher["name"] == "李老师"
            assert result.classroom["name"] == "五年级一班"
            assert len(result.students) == 1
    
    @patch('app.reporting.service.db.session.query')
    def test_build_assignment_vm_not_found(self, mock_query):
        """Test assignment VM building with assignment not found."""
        mock_query.return_value.filter.return_value.first.return_value = None
        
        result = build_assignment_vm(999)
        assert result is None
    
    @patch('app.reporting.service.load_evaluation_by_essay')
    @patch('app.reporting.service.render_essay_docx')
    def test_render_student_docx_success(self, mock_render_essay, mock_load_eval):
        """Test successful student DOCX rendering."""
        mock_eval = Mock()
        mock_load_eval.return_value = mock_eval
        
        mock_render_essay.return_value = "/tmp/test.docx"
        
        # Mock file reading
        test_content = b"fake docx content"
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = test_content
            
            result = render_student_docx(100)
            assert result == test_content
    
    @patch('app.reporting.service.load_evaluation_by_essay')
    def test_render_student_docx_no_evaluation(self, mock_load_eval):
        """Test student DOCX rendering with no evaluation."""
        mock_load_eval.return_value = None
        
        with pytest.raises(ValueError, match="No evaluation found"):
            render_student_docx(100)
    
    @patch('app.reporting.service.build_assignment_vm')
    def test_render_assignment_docx_combined_mode(self, mock_build_vm):
        """Test assignment DOCX rendering in combined mode."""
        mock_vm = Mock()
        mock_vm.students = [Mock()]  # At least one student
        mock_build_vm.return_value = mock_vm
        
        with patch('app.reporting.service._render_assignment_combined') as mock_render:
            mock_render.return_value = b"fake combined docx"
            
            result = render_assignment_docx(1, mode="combined")
            assert result == b"fake combined docx"
    
    @patch('app.reporting.service.build_assignment_vm')
    def test_render_assignment_docx_zip_mode(self, mock_build_vm):
        """Test assignment DOCX rendering in zip mode."""
        mock_vm = Mock()
        mock_vm.students = [Mock()]  # At least one student
        mock_build_vm.return_value = mock_vm
        
        with patch('app.reporting.service._render_assignment_zip') as mock_render:
            mock_zip = Mock()
            mock_render.return_value = mock_zip
            
            result = render_assignment_docx(1, mode="zip")
            assert result == mock_zip
    
    @patch('app.reporting.service.build_assignment_vm')
    def test_render_assignment_docx_no_data(self, mock_build_vm):
        """Test assignment DOCX rendering with no data."""
        mock_build_vm.return_value = None
        
        with pytest.raises(ValueError, match="No data found"):
            render_assignment_docx(999)
    
    @patch('app.reporting.service.build_assignment_vm')
    def test_render_assignment_docx_no_students(self, mock_build_vm):
        """Test assignment DOCX rendering with no students."""
        mock_vm = Mock()
        mock_vm.students = []  # No students
        mock_build_vm.return_value = mock_vm
        
        with pytest.raises(ValueError, match="No student data found"):
            render_assignment_docx(1)


class TestPerformance:
    """Test performance aspects of batch reporting."""
    
    @patch('app.reporting.service.build_student_vm')
    @patch('app.reporting.service.db.session.query')
    def test_large_assignment_handling(self, mock_query, mock_build_student):
        """Test handling of assignments with many students (200+)."""
        # Mock assignment
        mock_assignment = Mock()
        mock_assignment.id = 1
        mock_assignment.title = "大型作业"
        mock_assignment.teacher = Mock()
        mock_assignment.teacher.user = Mock()
        mock_assignment.teacher.user.full_name = "李老师"
        mock_assignment.teacher.classrooms = []
        
        # Mock 200 essays
        mock_essays = [Mock() for _ in range(200)]
        for i, essay in enumerate(mock_essays):
            essay.id = i + 1
        
        # Setup query chain
        mock_assignment_query = Mock()
        mock_assignment_query.filter.return_value.first.return_value = mock_assignment
        
        mock_essay_query = Mock()
        mock_essay_query.filter.return_value.all.return_value = mock_essays
        
        mock_query.side_effect = [mock_assignment_query, mock_essay_query]
        
        # Mock student VM building to return valid VMs
        def mock_student_vm_side_effect(essay_id):
            vm = Mock()
            vm.student_name = f"学生{essay_id}"
            vm.essay_id = essay_id
            return vm
        
        mock_build_student.side_effect = mock_student_vm_side_effect
        
        # Test that it doesn't crash with large numbers
        result = build_assignment_vm(1)
        
        assert result is not None
        assert len(result.students) == 200
        assert mock_build_student.call_count == 200
    
    def test_empty_assignment_graceful_handling(self):
        """Test graceful handling of empty assignments."""
        with patch('app.reporting.service.db.session.query') as mock_query:
            # Mock empty assignment
            mock_assignment = Mock()
            mock_assignment.id = 1
            mock_assignment.title = "空作业"
            mock_assignment.teacher = Mock()
            mock_assignment.teacher.user = Mock()
            mock_assignment.teacher.user.full_name = "李老师"
            mock_assignment.teacher.classrooms = []
            
            # Mock no essays
            mock_assignment_query = Mock()
            mock_assignment_query.filter.return_value.first.return_value = mock_assignment
            
            mock_essay_query = Mock()
            mock_essay_query.filter.return_value.all.return_value = []
            
            mock_query.side_effect = [mock_assignment_query, mock_essay_query]
            
            result = build_assignment_vm(1)
            
            assert result is not None
            assert len(result.students) == 0