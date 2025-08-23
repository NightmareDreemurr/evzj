#!/usr/bin/env python3
"""
Test CLI tool with sample data (without database dependency).
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from test_teacher_view_export import create_sample_evaluation
from app.reporting.docx_renderer import render_essay_docx

def test_cli_equivalent():
    """Test CLI equivalent without actual database"""
    print("=== CLI Tool Test (without database) ===")
    
    # Create sample data (same as test_teacher_view_export.py)
    evaluation = create_sample_evaluation()
    
    # Test teacher view rendering (what --teacher-view would do)
    print("Testing teacher view rendering...")
    try:
        output_path = render_essay_docx(evaluation, "/tmp/cli_test_teacher_view.docx", teacher_view=True)
        file_size = os.path.getsize(output_path)
        print(f"✅ Teacher view DOCX generated: {output_path}")
        print(f"✅ File size: {file_size} bytes")
    except Exception as e:
        print(f"❌ Teacher view rendering failed: {e}")
        return False
    
    # Test legacy rendering (what normal mode would do)
    print("Testing legacy rendering...")
    try:
        # Create legacy format evaluation (without teacher view fields)
        from app.schemas.evaluation import EvaluationResult, Meta, TextBlock, Scores, RubricScore
        
        meta = Meta(student="测试学生", topic="测试作业", date="2025-08-23", class_="测试班级", teacher="测试教师")
        rubrics = [RubricScore(name="内容", score=8, max=10, weight=1.0, reason="评分理由")]
        scores = Scores(total=8, rubrics=rubrics)
        text_block = TextBlock(original="原始内容", cleaned="修改后内容")
        
        legacy_eval = EvaluationResult(meta=meta, text=text_block, scores=scores)
        
        output_path = render_essay_docx(legacy_eval, "/tmp/cli_test_legacy.docx", teacher_view=False)
        file_size = os.path.getsize(output_path)
        print(f"✅ Legacy DOCX generated: {output_path}")
        print(f"✅ File size: {file_size} bytes")
    except Exception as e:
        print(f"❌ Legacy rendering failed: {e}")
        return False
    
    print("\n🎉 CLI equivalent tests passed!")
    print("\nTo test with actual CLI (when database is available):")
    print("python tools/gen_report.py --essay-id <ID> --teacher-view --out report.docx")
    return True

if __name__ == "__main__":
    test_cli_equivalent()