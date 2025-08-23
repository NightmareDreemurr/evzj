#!/usr/bin/env python3
"""
Unit tests for teacher view aligned DOCX export.
"""
import unittest
import os
import tempfile
from pathlib import Path

from app.schemas.evaluation import EvaluationResult, Meta, TextBlock, Scores, RubricScore
from app.reporting.docx_renderer import render_essay_docx


class TestTeacherViewExport(unittest.TestCase):
    """Test cases for teacher view aligned DOCX export"""
    
    def create_sample_evaluation(self, teacher_view=True):
        """Create sample evaluation data for testing"""
        meta = Meta(
            student="测试学生",
            topic="测试作业",
            date="2025-08-23",
            class_="测试班级",
            teacher="测试教师"
        )
        
        rubrics = [
            RubricScore(name="内容", score=8, max=10, weight=1.0, reason="内容充实"),
            RubricScore(name="结构", score=7, max=10, weight=1.0, reason="结构清晰"),
        ]
        
        scores = Scores(total=15, rubrics=rubrics)
        text_block = TextBlock(original="原始内容", cleaned="修改后内容")
        
        if teacher_view:
            return EvaluationResult(
                meta=meta,
                text=text_block,
                scores=scores,
                assignmentTitle="测试作业题目",
                studentName="测试学生姓名",
                submittedAt="2025-08-23 10:00:00",
                currentEssayContent="这是教师修改后的作文内容，没有任何diff标记。",
                outline=[{"index": 1, "intention": "开头段落"}],
                diagnoses=[{"id": 1, "target": "第1段", "evidence": "问题描述", "suggestions": ["建议1"]}],
                personalizedPractices=[{"title": "练习1", "requirement": "练习要求"}],
                summaryData={
                    "problemSummary": "问题总结",
                    "improvementPlan": "改进计划", 
                    "expectedOutcome": "预期效果"
                },
                parentSummary="给家长的总结",
                overall_comment="综合评价",
                strengths=["优点1", "优点2"],
                improvements=["改进1", "改进2"]
            )
        else:
            return EvaluationResult(meta=meta, text=text_block, scores=scores)
    
    def test_teacher_view_rendering(self):
        """Test teacher view aligned rendering"""
        evaluation = self.create_sample_evaluation(teacher_view=True)
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            output_path = render_essay_docx(evaluation, tmp.name, teacher_view=True)
            
            # Check file was created and has content
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 1000)  # Should be substantial
            
            # Cleanup
            os.unlink(output_path)
    
    def test_legacy_rendering(self):
        """Test legacy format rendering still works"""
        evaluation = self.create_sample_evaluation(teacher_view=False)
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            output_path = render_essay_docx(evaluation, tmp.name, teacher_view=False)
            
            # Check file was created and has content
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 1000)
            
            # Cleanup
            os.unlink(output_path)
    
    def test_auto_detection(self):
        """Test automatic detection of teacher view format"""
        evaluation = self.create_sample_evaluation(teacher_view=True)
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            # Should auto-detect teacher view based on fields present
            output_path = render_essay_docx(evaluation, tmp.name)
            
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 1000)
            
            # Cleanup
            os.unlink(output_path)
    
    def test_empty_data_handling(self):
        """Test handling of missing/empty data fields"""
        meta = Meta(student="测试", topic="测试", date="2025-08-23")
        scores = Scores(total=0, rubrics=[])
        
        evaluation = EvaluationResult(
            meta=meta,
            scores=scores,
            assignmentTitle="测试作业",
            currentEssayContent="",  # Empty content
            outline=[],  # Empty lists
            diagnoses=[],
            personalizedPractices=[],
            summaryData=None,  # None values
            parentSummary=None
        )
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            output_path = render_essay_docx(evaluation, tmp.name)
            
            # Should handle empty data gracefully
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 500)
            
            # Cleanup
            os.unlink(output_path)


if __name__ == '__main__':
    unittest.main()