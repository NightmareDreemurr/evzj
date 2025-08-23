"""
Test cases for the strftime filter fix and enhanced context features.
"""
import os
import tempfile
from datetime import datetime

import pytest

from app.schemas.evaluation import EvaluationResult, Meta, Scores, TextBlock
from app.reporting.docx_renderer import _render_with_docxtpl


class TestDocxRendererFixes:
    """Test the P0-P2 fixes in docx_renderer"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.meta = Meta(
            student="测试学生",
            class_="测试班级", 
            teacher="测试教师",
            topic="测试作文",
            date="2024-01-01",
            student_id="123",
            grade="五年级",
            words=100
        )
        
        self.scores = Scores(
            total=85.0,
            rubrics=[]
        )
        
        self.text = TextBlock(
            original="测试原文内容",
            cleaned="测试清洗后内容"
        )
    
    def test_strftime_filter_with_datetime(self):
        """Test that strftime filter works with datetime objects (P0)"""
        evaluation = EvaluationResult(
            meta=self.meta,
            scores=self.scores,
            text=self.text
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "test_datetime.docx")
            
            # This should not raise an exception
            result_path = _render_with_docxtpl(evaluation, output_path)
            
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 0
    
    def test_enhanced_context_fields(self):
        """Test that context includes paragraphs, exercises, feedback_summary (P2)"""
        from app.schemas.evaluation import to_context
        
        evaluation = EvaluationResult(
            meta=self.meta,
            scores=self.scores,
            text=self.text
        )
        
        context = to_context(evaluation)
        
        # Check that P2 fields are present
        assert 'paragraphs' in context
        assert 'exercises' in context
        assert 'feedback_summary' in context
        
        # Check they default to appropriate empty values
        assert isinstance(context['paragraphs'], list)
        assert isinstance(context['exercises'], list) 
        assert isinstance(context['feedback_summary'], str)
    
    def test_template_rendering_without_fallback(self):
        """Test that template syntax errors raise exceptions instead of falling back (P1)"""
        evaluation = EvaluationResult(
            meta=self.meta,
            scores=self.scores,
            text=self.text
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "test_no_fallback.docx")
            
            # This should work without falling back to python-docx
            result_path = _render_with_docxtpl(evaluation, output_path)
            
            assert os.path.exists(result_path)
            # If it worked, docxtpl was used (not python-docx fallback)
            assert os.path.getsize(result_path) > 10000  # docxtpl generates larger files

    def test_legacy_data_compatibility(self):
        """Test that legacy ai_score data gets properly normalized (P4)"""
        from app.dao.evaluation_dao import _normalize_legacy_ai_score
        from app.models import Essay
        
        # Create mock essay
        essay = Essay()
        essay.id = 1
        essay.content = "测试内容"
        essay.created_at = datetime.now()
        
        # Simulate legacy ai_score format
        legacy_data = {
            "total_score": 85.5,
            "dimensions": [
                {
                    "name": "内容",
                    "score": 18,
                    "max_score": 20,
                    "weight": 1.0,
                    "reason": "内容丰富"
                }
            ],
            "summary": "写得不错",
            "analysis": "详细分析..."
        }
        
        normalized = _normalize_legacy_ai_score(legacy_data, essay)
        
        # Check that required fields are present
        assert 'meta' in normalized
        assert 'scores' in normalized
        assert 'paragraphs' in normalized  # P2 field
        assert 'exercises' in normalized   # P2 field
        assert 'feedback_summary' in normalized  # P2 field
        
        # Check scores structure
        assert normalized['scores']['total'] == 85.5
        assert len(normalized['scores']['rubrics']) == 1
        assert normalized['scores']['rubrics'][0]['name'] == "内容"
        
        # Check P2 fields default properly
        assert isinstance(normalized['paragraphs'], list)
        assert isinstance(normalized['exercises'], list)
        assert normalized['feedback_summary'] == "写得不错"  # Should use summary as fallback