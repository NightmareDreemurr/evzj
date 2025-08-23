"""
Tests for enhanced evaluation API endpoints and teacher review workflow.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.extensions import db
from app.models import (
    User, Essay, TeacherProfile, StudentProfile, Enrollment, 
    EssayAssignment, GradingStandard, Classroom, School, GradeLevel
)
from app.schemas.evaluation import EvaluationResult, Meta, Scores, TextBlock


@pytest.fixture
def app():
    """Create test app."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['EVAL_PREBUILD_ENABLED'] = True
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_data(app):
    """Create all test data in one session."""
    with app.app_context():
        # Create school and classroom
        school = School(name="Test School", sort_name="test_school")
        db.session.add(school)
        db.session.flush()
        
        classroom = Classroom(
            school_id=school.id,
            entry_year=2023,
            graduate_year=2029,
            class_number=1,
            class_name="Test Class 1"
        )
        db.session.add(classroom)
        db.session.flush()
        
        # Create teacher user
        teacher_user = User(
            email="teacher@test.com",
            username="teacher",
            full_name="Test Teacher",
            role="teacher",
            password_hash="hashed_password"
        )
        db.session.add(teacher_user)
        db.session.flush()
        
        teacher_profile = TeacherProfile(
            user_id=teacher_user.id,
            school_id=school.id
        )
        db.session.add(teacher_profile)
        db.session.flush()
        
        # Create grade level
        grade_level = GradeLevel(name="五年级", is_enabled=True)
        db.session.add(grade_level)
        db.session.flush()
        
        # Create grading standard
        standard = GradingStandard(
            title="Test Standard",
            total_score=100,
            grade_level_id=grade_level.id,
            creator_id=teacher_user.id
        )
        db.session.add(standard)
        db.session.flush()
        
        # Create assignment
        assignment = EssayAssignment(
            title="Test Assignment",
            teacher_profile_id=teacher_profile.id,
            grading_standard_id=standard.id
        )
        db.session.add(assignment)
        db.session.flush()
        
        # Create student
        student_user = User(
            email="student@test.com",
            username="student",
            full_name="Test Student",
            role="student",
            password_hash="hashed_password"
        )
        db.session.add(student_user)
        db.session.flush()
        
        student_profile = StudentProfile(user_id=student_user.id)
        db.session.add(student_profile)
        db.session.flush()
        
        enrollment = Enrollment(
            student_profile_id=student_profile.id,
            classroom_id=classroom.id
        )
        db.session.add(enrollment)
        db.session.flush()
        
        # Create essay with evaluation data
        essay = Essay(
            enrollment_id=enrollment.id,
            assignment_id=assignment.id,
            content="This is a test essay content.",
            ai_evaluation={
                "meta": {
                    "student": "Test Student",
                    "topic": "Test Essay",
                    "grade": "5",
                    "date": datetime.now().isoformat()
                },
                "scores": {
                    "total": 85,
                    "rubrics": []
                },
                "analysis": {
                    "outline": [
                        {"para": 1, "intent": "Introduction"},
                        {"para": 2, "intent": "Main body"}
                    ]
                },
                "diagnostics": [
                    {
                        "para": 1,
                        "issue": "Weak opening",
                        "evidence": "The introduction lacks a clear thesis",
                        "advice": ["Add a strong thesis statement", "Improve the hook"]
                    }
                ],
                "exercises": [
                    {
                        "type": "writing",
                        "prompt": "Practice writing strong introductions",
                        "hint": ["Start with a question", "Use a quote"],
                        "sample": "Example introduction text"
                    }
                ],
                "diagnosis": {
                    "before": "Essay lacks structure",
                    "comment": "Focus on paragraph organization",
                    "after": "Improved structure will enhance clarity"
                },
                "summary": "Good effort with room for improvement"
            },
            evaluation_status="ai_generated"
        )
        db.session.add(essay)
        db.session.commit()
        
        # Return data structure with all object IDs
        return {
            'teacher_user_id': teacher_user.id,
            'teacher_profile_id': teacher_profile.id,
            'essay_id': essay.id,
            'assignment_id': assignment.id,
            'school_id': school.id,
            'classroom_id': classroom.id
        }


class TestEvaluationAPI:
    """Test cases for evaluation API endpoints."""
    
    def test_get_evaluation_success(self, client, test_data):
        """Test successful retrieval of evaluation data."""        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_data['teacher_user_id'])
            sess['_fresh'] = True
        
        # Get evaluation data
        response = client.get(f'/assignments/api/submissions/{test_data["essay_id"]}/evaluation')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Check structure
        assert 'meta' in data
        assert 'scores' in data
        assert 'analysis' in data
        assert 'diagnostics' in data
        assert 'exercises' in data
        assert 'diagnosis' in data
        assert 'summary' in data
        assert data['evaluation_status'] == 'ai_generated'
    
    def test_get_evaluation_not_found(self, client, test_data):
        """Test retrieval of non-existent evaluation."""        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_data['teacher_user_id'])
            sess['_fresh'] = True
        
        response = client.get('/assignments/api/submissions/99999/evaluation')
        assert response.status_code == 404
    
    def test_update_evaluation_success(self, client, test_data):
        """Test successful update of evaluation data."""
        teacher_user = test_data['teacher_user'] 
        test_essay = test_data['essay']
        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(teacher_user.id)
            sess['_fresh'] = True
        
        # Get current evaluation
        response = client.get(f'/assignments/api/submissions/{test_essay.id}/evaluation')
        current_data = json.loads(response.data)
        
        # Modify diagnostics
        current_data['diagnostics'][0]['issue'] = 'Updated issue description'
        current_data['diagnosis']['comment'] = 'Updated teacher feedback'
        
        # Update evaluation
        response = client.put(
            f'/assignments/api/submissions/{test_essay.id}/evaluation',
            data=json.dumps(current_data),
            content_type='application/json'
        )
        
        assert response.status_code == 200
        result = json.loads(response.data)
        assert result['evaluation_status'] == 'teacher_reviewed'
        
        # Verify changes were saved
        with client.application.app_context():
            updated_essay = db.session.get(Essay, test_essay.id)
            assert updated_essay.evaluation_status == 'teacher_reviewed'
            assert updated_essay.reviewed_by == test_data['teacher_profile'].id
            assert updated_essay.reviewed_at is not None
            
            eval_data = updated_essay.ai_evaluation
            assert eval_data['diagnostics'][0]['issue'] == 'Updated issue description'
            assert eval_data['diagnosis']['comment'] == 'Updated teacher feedback'
    
    def test_update_evaluation_invalid_data(self, client, test_data):
        """Test update with invalid evaluation data."""
        teacher_user = test_data['teacher_user']
        test_essay = test_data['essay']
        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(teacher_user.id)
            sess['_fresh'] = True
        
        # Send invalid data
        invalid_data = {'invalid': 'structure'}
        
        response = client.put(
            f'/assignments/api/submissions/{test_essay.id}/evaluation',
            data=json.dumps(invalid_data),
            content_type='application/json'
        )
        
        assert response.status_code == 500  # Should fail validation
    
    def test_authorization_required(self, client, test_data):
        """Test that endpoints require authentication."""
        test_essay = test_data['essay']
        
        # Try without login
        response = client.get(f'/assignments/api/submissions/{test_essay.id}/evaluation')
        assert response.status_code == 302  # Redirect to login
        
        response = client.put(
            f'/assignments/api/submissions/{test_essay.id}/evaluation',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 302  # Redirect to login


class TestReviewWorkflow:
    """Test cases for the complete review workflow."""
    
    def test_feature_flag_disabled(self, client, test_data):
        """Test that feature can be disabled via config."""
        teacher_user = test_data['teacher_user']
        test_essay = test_data['essay']
        
        # Disable feature
        client.application.config['EVAL_PREBUILD_ENABLED'] = False
        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(teacher_user.id)
            sess['_fresh'] = True
        
        # Visit review page
        response = client.get(f'/assignments/submission/{test_essay.id}/review')
        
        # Should not show enhanced content panel
        assert b'enhanced-content-panel' not in response.data
    
    def test_review_status_progression(self, client, test_data):
        """Test the progression from ai_generated to teacher_reviewed."""
        teacher_user = test_data['teacher_user']
        test_essay = test_data['essay']
        
        # Login as teacher
        with client.session_transaction() as sess:
            sess['_user_id'] = str(teacher_user.id)
            sess['_fresh'] = True
        
        # Initial status should be ai_generated
        with client.application.app_context():
            essay = db.session.get(Essay, test_essay.id)
            assert essay.evaluation_status == 'ai_generated'
            assert essay.reviewed_by is None
            assert essay.reviewed_at is None
        
        # Update evaluation (teacher review)
        eval_response = client.get(f'/assignments/api/submissions/{test_essay.id}/evaluation')
        eval_data = json.loads(eval_response.data)
        eval_data['summary'] = 'Teacher has reviewed this'
        
        response = client.put(
            f'/assignments/api/submissions/{test_essay.id}/evaluation',
            data=json.dumps(eval_data),
            content_type='application/json'
        )
        
        # Status should now be teacher_reviewed
        with client.application.app_context():
            essay = db.session.get(Essay, test_essay.id)
            assert essay.evaluation_status == 'teacher_reviewed'
            assert essay.reviewed_by == test_data['teacher_profile'].id
            assert essay.reviewed_at is not None