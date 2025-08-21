"""
Tests for JSON storage consistency of ai_score field.
"""
import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Essay, Enrollment, StudentProfile, User
from app.schemas.evaluation import EvaluationResult


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


def test_ai_score_json_round_trip(app_context):
    """Test ai_score JSON storage and retrieval consistency"""
    # Create test data
    user = User(
        email="test@example.com",
        username="testuser", 
        password_hash="dummy",
        role="student",
        full_name="Test Student"
    )
    db.session.add(user)
    db.session.commit()

    student_profile = StudentProfile(user_id=user.id)
    db.session.add(student_profile)
    db.session.commit()

    enrollment = Enrollment(
        student_profile_id=student_profile.id,
        classroom_id=1,  # Mock classroom
        status='active'
    )
    db.session.add(enrollment)
    db.session.commit()

    # Create sample EvaluationResult
    evaluation_dict = {
        "meta": {
            "student_id": "test_123",
            "grade": "五年级",
            "topic": "测试作文",
            "words": 100
        },
        "analysis": {
            "outline": [
                {"para": 1, "intent": "开头"}
            ],
            "issues": ["测试问题"]
        },
        "scores": {
            "content": 25.0,
            "structure": 18.0,
            "language": 20.0,
            "aesthetics": 12.0,
            "norms": 9.0,
            "total": 84.0,
            "rationale": "测试评分"
        },
        "diagnostics": [],
        "exercises": [],
        "summary": "测试总结"
    }
    
    # Create EvaluationResult from dict
    evaluation = EvaluationResult.model_validate(evaluation_dict)
    
    # Store in Essay.ai_score using model_dump()
    essay = Essay(
        enrollment_id=enrollment.id,
        content="测试内容",
        ai_score=evaluation.model_dump(),
        status='graded'
    )
    db.session.add(essay)
    db.session.commit()
    
    # Retrieve essay and validate ai_score can be loaded back
    retrieved_essay = db.session.get(Essay, essay.id)
    assert retrieved_essay.ai_score is not None
    
    # Test round-trip: dict -> EvaluationResult -> dict -> EvaluationResult
    retrieved_evaluation = EvaluationResult.model_validate(retrieved_essay.ai_score)
    
    # Verify all fields are preserved
    assert retrieved_evaluation.meta.student_id == "test_123"
    assert retrieved_evaluation.meta.grade == "五年级"
    assert retrieved_evaluation.meta.words == 100
    assert retrieved_evaluation.scores.total == 84.0
    assert retrieved_evaluation.scores.content == 25.0
    assert len(retrieved_evaluation.analysis.outline) == 1
    assert retrieved_evaluation.analysis.outline[0].intent == "开头"
    assert retrieved_evaluation.summary == "测试总结"


def test_ai_score_field_type_consistency(app_context):
    """Test that ai_score field handles different input types consistently"""
    user = User(
        email="test2@example.com",
        username="testuser2",
        password_hash="dummy",
        role="student", 
        full_name="Test Student 2"
    )
    db.session.add(user)
    db.session.commit()

    student_profile = StudentProfile(user_id=user.id)
    db.session.add(student_profile)
    db.session.commit()

    enrollment = Enrollment(
        student_profile_id=student_profile.id,
        classroom_id=1,
        status='active'
    )
    db.session.add(enrollment)
    db.session.commit()

    # Test storing None
    essay1 = Essay(
        enrollment_id=enrollment.id,
        content="测试内容1",
        ai_score=None,
        status='pending'
    )
    db.session.add(essay1)
    
    # Test storing empty dict
    essay2 = Essay(
        enrollment_id=enrollment.id,
        content="测试内容2", 
        ai_score={},
        status='pending'
    )
    db.session.add(essay2)
    
    # Test storing valid EvaluationResult dict
    valid_dict = {
        "meta": {"student_id": "test", "grade": "五年级", "topic": "测试", "words": 50},
        "analysis": {"outline": [], "issues": []},
        "scores": {"content": 0, "structure": 0, "language": 0, "aesthetics": 0, "norms": 0, "total": 0, "rationale": ""},
        "diagnostics": [],
        "exercises": [],
        "summary": ""
    }
    essay3 = Essay(
        enrollment_id=enrollment.id,
        content="测试内容3",
        ai_score=valid_dict,
        status='graded'
    )
    db.session.add(essay3)
    
    db.session.commit()
    
    # Retrieve and verify
    retrieved1 = db.session.get(Essay, essay1.id)
    retrieved2 = db.session.get(Essay, essay2.id)
    retrieved3 = db.session.get(Essay, essay3.id)
    
    assert retrieved1.ai_score is None
    assert retrieved2.ai_score == {}
    
    # Should be able to load valid EvaluationResult
    assert retrieved3.ai_score is not None
    evaluation = EvaluationResult.model_validate(retrieved3.ai_score)
    assert evaluation.meta.student_id == "test"
    assert evaluation.scores.total == 0