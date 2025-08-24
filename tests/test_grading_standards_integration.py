"""
Tests for grading standards integration in ai_pregrader.
"""
import pytest
from unittest.mock import Mock

from app.services.grading_utils import format_grading_standard_for_prompt
from app.services.ai_pregrader import _build_analysis_prompt
from app.services.evaluation_builder import _build_context_for_essay


class TestGradingStandardsIntegration:
    """Test grading standards integration across services."""
    
    def test_format_grading_standard_for_prompt_none(self):
        """Test formatting function with None standard."""
        result = format_grading_standard_for_prompt(None)
        assert result == "没有提供评分标准。"
    
    def test_format_grading_standard_for_prompt_with_standard(self):
        """Test formatting function with mock standard."""
        # Create mock grading standard
        mock_rubric1 = Mock()
        mock_rubric1.level_name = "A"
        mock_rubric1.min_score = 8
        mock_rubric1.max_score = 10
        mock_rubric1.description = "优秀：内容丰富，结构清晰"
        
        mock_rubric2 = Mock()
        mock_rubric2.level_name = "B"
        mock_rubric2.min_score = 6
        mock_rubric2.max_score = 7
        mock_rubric2.description = "良好：内容较丰富，结构基本清晰"
        
        mock_dimension = Mock()
        mock_dimension.id = 1
        mock_dimension.name = "内容与思想"
        mock_dimension.max_score = 10
        mock_dimension.rubrics = [mock_rubric1, mock_rubric2]
        
        mock_standard = Mock()
        mock_standard.title = "五年级作文评分标准"
        mock_standard.total_score = 100
        mock_standard.dimensions = [mock_dimension]
        
        result = format_grading_standard_for_prompt(mock_standard)
        
        # Check that the result contains expected components
        assert "作文题目: 五年级作文评分标准" in result
        assert "总分: 100" in result
        assert "维度: 内容与思想 (满分: 10)" in result
        assert "A (8~10分): 优秀：内容丰富，结构清晰" in result
        assert "B (6~7分): 良好：内容较丰富，结构基本清晰" in result
    
    def test_build_analysis_prompt_with_grading_standard(self):
        """Test that analysis prompt includes grading standards when available."""
        # Create mock grading standard
        mock_rubric = Mock()
        mock_rubric.level_name = "A"
        mock_rubric.min_score = 8
        mock_rubric.max_score = 10
        mock_rubric.description = "优秀：内容丰富，结构清晰"
        
        mock_dimension = Mock()
        mock_dimension.id = 1
        mock_dimension.name = "内容与思想"
        mock_dimension.max_score = 10
        mock_dimension.rubrics = [mock_rubric]
        
        mock_standard = Mock()
        mock_standard.title = "五年级作文评分标准"
        mock_standard.total_score = 100
        mock_standard.dimensions = [mock_dimension]
        
        context = {
            'topic': '我的暑假',
            'grade': '五年级',
            'grading_standard': mock_standard
        }
        
        prompt = _build_analysis_prompt("这是一篇作文。", context)
        
        # Check that grading standard information is included
        assert "评分标准" in prompt
        assert "五年级作文评分标准" in prompt
        assert "总分: 100" in prompt
        assert "内容与思想" in prompt
        assert "请结合上述评分标准中的维度和评分要求进行分析" in prompt
        assert "练习应该针对评分标准中的具体维度进行设计" in prompt
        assert "评价应该基于评分标准的各个维度" in prompt
        assert "问题诊断和改进建议应该与评分标准相对应" in prompt
    
    def test_build_analysis_prompt_without_grading_standard(self):
        """Test that analysis prompt works without grading standards."""
        context = {
            'topic': '我的暑假',
            'grade': '五年级'
        }
        
        prompt = _build_analysis_prompt("这是一篇作文。", context)
        
        # Check that prompt is generated correctly without grading standards
        assert "我的暑假" in prompt
        assert "五年级" in prompt
        # Should not contain grading standard section header
        assert "## 评分标准" not in prompt
        # Should not contain grading standard instructions
        assert "请结合上述评分标准中的维度和评分要求进行分析" not in prompt
    
    def test_build_context_for_essay_includes_grading_standard(self):
        """Test that context building includes grading standard."""
        # Create mock essay with grading standard
        mock_grade_level = Mock()
        mock_grade_level.name = "五年级"
        
        mock_standard = Mock()
        mock_standard.total_score = 100
        mock_standard.grade_level = mock_grade_level
        
        mock_assignment = Mock()
        mock_assignment.title = "暑假作文"
        mock_assignment.grading_standard = mock_standard
        
        mock_essay = Mock()
        mock_essay.id = 1
        mock_essay.assignment = mock_assignment
        mock_essay.grading_standard = None
        mock_essay.enrollment = None
        mock_essay.content = "这是作文内容"
        mock_essay.created_at = None
        
        context = _build_context_for_essay(mock_essay)
        
        # Check that grading standard is included
        assert 'grading_standard' in context
        assert context['grading_standard'] == mock_standard
        assert context['grade'] == "五年级"
        assert context['total_score'] == 100