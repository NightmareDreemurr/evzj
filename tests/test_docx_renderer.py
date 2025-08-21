"""
Tests for DOCX renderer functionality.
"""
import os
import tempfile
import pytest
from datetime import datetime

from app.schemas.evaluation import (
    EvaluationResult, Meta, Scores, RubricScore, TextBlock, Highlight, Span, Diagnosis
)
from app.reporting.docx_renderer import render_essay_docx, ensure_template_exists


def test_ensure_template_creation():
    """Test that template is created if missing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        template_path = os.path.join(temp_dir, "test_template.docx")
        
        # Template shouldn't exist initially
        assert not os.path.exists(template_path)
        
        # Call ensure_template_exists
        result_path = ensure_template_exists(template_path)
        
        # Template should now exist
        assert os.path.exists(result_path)
        assert result_path == template_path


def test_render_essay_docx_basic():
    """Test basic DOCX rendering with minimal EvaluationResult"""
    # Create minimal evaluation result
    evaluation = EvaluationResult(
        meta=Meta(
            student="张三",
            class_="五年级1班",
            teacher="李老师", 
            topic="我的暑假",
            date="2024-08-21"
        ),
        scores=Scores(
            total=85.0,
            rubrics=[
                RubricScore(name="内容", score=18.0, max=20.0, weight=1.0, reason="内容丰富"),
                RubricScore(name="结构", score=17.0, max=20.0, weight=1.0, reason="结构清晰")
            ]
        ),
        text=TextBlock(
            original="这是我的暑假作文。我在暑假里做了很多有趣的事情。",
            cleaned="这是我的暑假作文。我在暑假里做了很多有趣的事情。"
        )
    )
    
    # Render to temporary file
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "test_output.docx")
        result_path = render_essay_docx(evaluation, output_path)
        
        # Check file was created
        assert os.path.exists(result_path)
        assert result_path == output_path
        
        # Check file is not empty
        assert os.path.getsize(result_path) > 0


def test_render_essay_docx_with_highlights():
    """Test DOCX rendering with highlights"""
    evaluation = EvaluationResult(
        meta=Meta(
            student="王五",
            class_="六年级2班", 
            teacher="张老师",
            topic="环保作文",
            date="2024-08-21"
        ),
        scores=Scores(
            total=78.0,
            rubrics=[
                RubricScore(name="内容", score=16.0, max=20.0, weight=1.0, reason="主题突出")
            ]
        ),
        text=TextBlock(
            original="保护环境很重要。我们应该节约用水。",
            cleaned="保护环境很重要。我们应该节约用水。"
        ),
        highlights=[
            Highlight(
                type="grammar",
                span=Span(start=0, end=5, text="保护环境"),
                message="词汇使用恰当",
                severity="low"
            ),
            Highlight(
                type="style", 
                span=Span(start=10, end=16, text="节约用水"),
                message="表达简洁",
                severity="medium"
            )
        ]
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = render_essay_docx(evaluation)
        
        # Check file was created
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0


def test_render_essay_docx_with_diagnosis():
    """Test DOCX rendering with diagnosis"""
    evaluation = EvaluationResult(
        meta=Meta(
            student="赵六",
            class_="四年级3班",
            teacher="刘老师", 
            topic="春天来了",
            date="2024-08-21"
        ),
        scores=Scores(
            total=92.0,
            rubrics=[
                RubricScore(name="内容", score=19.0, max=20.0, weight=1.0, reason="描述生动")
            ]
        ),
        text=TextBlock(
            original="春天来了，花儿开了。",
            cleaned="春天来了，花儿开了。"
        ),
        diagnosis=Diagnosis(
            before="整体表现良好",
            comment="文章描述生动，但可以增加更多细节",
            after="建议多观察生活，丰富写作素材"
        )
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = render_essay_docx(evaluation)
        
        # Check file was created  
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0


def test_render_essay_docx_auto_filename():
    """Test automatic filename generation"""
    evaluation = EvaluationResult(
        meta=Meta(
            student="李 四",  # Name with space 
            class_="五年级1班",
            teacher="王老师",
            topic="我的/家乡",  # Topic with slash
            date="2024-08-21"
        ),
        scores=Scores(total=80.0, rubrics=[])
    )
    
    # Don't specify output path - should auto-generate
    result_path = render_essay_docx(evaluation)
    
    # Check file was created
    assert os.path.exists(result_path)
    assert os.path.getsize(result_path) > 0
    
    # Check filename doesn't contain problematic characters
    filename = os.path.basename(result_path)
    assert ' ' not in filename
    assert '/' not in filename
    assert filename.endswith('.docx')


def test_docx_content_validation():
    """Test that generated DOCX contains expected content"""
    evaluation = EvaluationResult(
        meta=Meta(
            student="测试学生",
            class_="测试班级",
            teacher="测试老师",
            topic="测试作文",
            date="2024-08-21"
        ),
        scores=Scores(
            total=90.0,
            rubrics=[
                RubricScore(name="测试维度", score=18.0, max=20.0, weight=1.0, reason="测试理由")
            ]
        ),
        text=TextBlock(
            original="这是测试文本内容。",
            cleaned="这是测试文本内容。"
        )
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        result_path = render_essay_docx(evaluation)
        
        # Try to read the document content using python-docx
        try:
            from docx import Document
            doc = Document(result_path)
            
            # Extract all text content
            full_text = ""
            for paragraph in doc.paragraphs:
                full_text += paragraph.text + "\n"
            
            # Check key content is present
            assert "测试学生" in full_text
            assert "测试班级" in full_text  
            assert "测试老师" in full_text
            assert "测试作文" in full_text
            assert "90.0" in full_text or "90" in full_text
            assert "这是测试文本内容" in full_text
            
        except ImportError:
            # If we can't read the document, just check file exists and isn't empty
            assert os.path.exists(result_path)
            assert os.path.getsize(result_path) > 1000  # Should be reasonably sized