#!/usr/bin/env python3
"""
Test script to reproduce the issue where sections show "（本项暂无数据）" 
when they should have actual data.
"""
import os
import sys
import tempfile
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from app.schemas.evaluation import EvaluationResult, Meta, TextBlock, Scores, RubricScore
from app.reporting.docx_renderer import render_essay_docx


def create_evaluation_with_empty_fields() -> EvaluationResult:
    """Create evaluation data that might trigger the no data issue"""
    
    meta = Meta(
        student="测试学生",
        topic="测试作文题目",
        date="2025-01-23",
        class_="测试班级", 
        teacher="测试老师"
    )
    
    scores = Scores(total=30, rubrics=[])
    
    text_block = TextBlock(
        original="这是原始的作文内容...",
        cleaned="这是经过处理的作文内容..."
    )
    
    # Create evaluation with empty strengths and improvements to test the issue
    return EvaluationResult(
        meta=meta,
        text=text_block,
        scores=scores,
        highlights=[],
        diagnosis=None,
        
        # Teacher-view aligned fields
        assignmentTitle="测试作文题目",
        studentName="测试学生",
        submittedAt="2025-01-23 09:16:36",
        currentEssayContent="这是一篇测试作文的内容。",
        
        # AI enhanced content - mostly empty to trigger the issue
        outline=[],
        diagnoses=[],
        personalizedPractices=[],
        summaryData=None,
        parentSummary=None,
        
        # Additional fields - empty to trigger the issue
        overall_comment="",  # Empty comment
        strengths=[],        # Empty strengths list
        improvements=[]      # Empty improvements list
    )


def test_empty_data_issue():
    """Test if empty data correctly shows fallback messages"""
    print("创建空数据测试...")
    evaluation = create_evaluation_with_empty_fields()
    
    print(f"Overall comment: '{evaluation.overall_comment}'")
    print(f"Strengths: {evaluation.strengths}")
    print(f"Improvements: {evaluation.improvements}")
    
    print("开始渲染DOCX...")
    try:
        output_path = render_essay_docx(evaluation)
        print(f"✅ DOCX渲染成功: {output_path}")
        
        # Check file exists and has content
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ 文件大小: {file_size} bytes")
            return output_path
        else:
            print("❌ 文件未生成")
            return None
            
    except Exception as e:
        print(f"❌ 渲染失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=== 测试空数据问题 ===")
    result = test_empty_data_issue()
    if result:
        print(f"\n📄 可以查看生成的文档: {result}")
    else:
        print("\n❌ 测试失败")