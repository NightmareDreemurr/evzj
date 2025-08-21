"""
Test for regenerate_report.py functionality.
"""
import os
import sys
import pytest
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Essay, Enrollment, StudentProfile, User
from app.schemas.evaluation import EvaluationResult, Meta, Analysis, Scores, OutlineItem
from regenerate_report import generate_word_report_from_evaluation, generate_report_content


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app('testing')
    return app


@pytest.fixture
def app_context(app):
    """Create application context for testing"""
    with app.app_context():
        # Create the database tables
        db.create_all()
        yield app
        db.drop_all()


def test_generate_report_content():
    """Test generating report content from EvaluationResult"""
    # Create a sample evaluation result
    evaluation = EvaluationResult(
        meta=Meta(
            student_id="test_123",
            grade="五年级",
            topic="我的妈妈",
            words=150
        ),
        analysis=Analysis(
            outline=[
                OutlineItem(para=1, intent="开头介绍"),
                OutlineItem(para=2, intent="具体描述")
            ],
            issues=["缺乏细节", "结尾草率"]
        ),
        scores=Scores(
            content=25.0,
            structure=18.0,
            language=20.0,
            aesthetics=12.0,
            norms=9.0,
            total=84.0,
            rationale="整体表现良好"
        ),
        diagnostics=[],
        exercises=[],
        summary="这是一篇表现良好的作文"
    )
    
    # Mock essay object
    class MockEssay:
        pass
    
    essay = MockEssay()
    
    # Generate content
    content = generate_report_content(evaluation, essay)
    
    # Verify content
    assert "作文评估报告" in content
    assert "学生ID: test_123" in content
    assert "年级: 五年级" in content
    assert "总分: 84.0分" in content
    assert "内容: 25.0分" in content
    assert "第1段: 开头介绍" in content
    assert "第2段: 具体描述" in content
    assert "缺乏细节" in content
    assert "结尾草率" in content
    assert "整体表现良好" in content
    assert "这是一篇表现良好的作文" in content


def test_generate_word_report_with_mock_data(app_context):
    """Test generating Word report with mock database data"""
    # Create test data
    user = User(
        email="test@example.com",
        username="testuser",
        password_hash="dummy",
        role="student",
        full_name="Test Student"
    )
    db.session.add(user)
    db.session.commit()  # Commit to get ID
    
    student_profile = StudentProfile(user_id=user.id)
    db.session.add(student_profile)
    db.session.commit()  # Commit to get ID
    
    enrollment = Enrollment(
        student_profile_id=student_profile.id,
        classroom_id=1,  # Mock classroom
        status='active'
    )
    db.session.add(enrollment)
    db.session.commit()  # Commit to get ID
    
    # Create evaluation result in new format
    evaluation_data = {
        "meta": {
            "student_id": "test_123",
            "grade": "五年级",
            "topic": "我的妈妈",
            "words": 150
        },
        "analysis": {
            "outline": [
                {"para": 1, "intent": "开头介绍"},
                {"para": 2, "intent": "具体描述"}
            ],
            "issues": ["缺乏细节", "结尾草率"]
        },
        "scores": {
            "content": 25.0,
            "structure": 18.0,
            "language": 20.0,
            "aesthetics": 12.0,
            "norms": 9.0,
            "total": 84.0,
            "rationale": "整体表现良好"
        },
        "diagnostics": [],
        "exercises": [],
        "summary": "这是一篇表现良好的作文"
    }
    
    essay = Essay(
        enrollment_id=enrollment.id,
        content="测试作文内容",
        ai_score=evaluation_data,
        status='graded'
    )
    db.session.add(essay)
    db.session.commit()
    
    # Generate report to a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.docx', delete=False) as f:
        temp_path = f.name

    try:
        result_path = generate_word_report_from_evaluation(essay.id, temp_path, app=app_context)

        # Verify report was generated (should be .docx file)
        assert result_path.endswith('.docx')
        assert os.path.exists(result_path)
        
        # For DOCX files, just verify the file exists and has content
        # (detailed content verification would require reading the DOCX structure)
        assert os.path.getsize(result_path) > 0
        
    finally:
        # Clean up
        if os.path.exists(result_path):
            os.unlink(result_path)