"""
DAO layer for evaluation data loading and normalization.
"""
from typing import List, Optional
import logging
from datetime import datetime

from app.extensions import db
from app.models import Essay, EssayAssignment, StudentProfile, TeacherProfile, User
from app.schemas.evaluation import EvaluationResult, Meta, Scores, RubricScore, TextBlock
from app.services.eval_pipeline import evaluate_essay
from app.services.meta_resolver import resolve_meta

logger = logging.getLogger(__name__)


def load_evaluation_by_essay(essay_id: int) -> Optional[EvaluationResult]:
    """
    Load evaluation result for a single essay.
    
    Args:
        essay_id: Essay ID
        
    Returns:
        EvaluationResult instance or None if not found
    """
    essay = db.session.get(Essay, essay_id)
    if not essay:
        logger.warning(f"Essay {essay_id} not found")
        return None
    
    # Try to load from ai_score first
    if essay.ai_score:
        try:
            # Try to parse as new format
            evaluation = EvaluationResult.model_validate(essay.ai_score)
            logger.info(f"Loaded evaluation for essay {essay_id} from ai_score (new format)")
            return evaluation
        except Exception as e:
            logger.warning(f"Failed to parse ai_score as new format for EvaluationResult {essay_id}: {e}")
            # Try to normalize legacy format
            try:
                normalized_data = _normalize_legacy_ai_score(essay.ai_score, essay)
                evaluation = EvaluationResult.model_validate(normalized_data)
                logger.info(f"Loaded evaluation for essay {essay_id} from ai_score (legacy format, auto-converted)")
                return evaluation
            except Exception as e:
                logger.error(f"Failed to normalize legacy ai_score for essay {essay_id}: {e}")
    
    # Fall back to generating evaluation on-the-fly (non-persistent)
    try:
        logger.info(f"Generating evaluation on-the-fly for essay {essay_id}")
        meta = resolve_meta(essay_id)
        result = evaluate_essay(essay.content or "", meta)
        return result
    except Exception as e:
        logger.error(f"Failed to generate evaluation for essay {essay_id}: {e}")
        return None


def load_evaluations_by_assignment(assignment_id: int) -> List[EvaluationResult]:
    """
    Load evaluation results for all essays in an assignment.
    
    Args:
        assignment_id: Assignment ID
        
    Returns:
        List of EvaluationResult instances
    """
    # Get all essays for this assignment that have been graded
    essays = db.session.query(Essay).filter(
        Essay.assignment_id == assignment_id,
        Essay.status == 'graded'
    ).all()
    
    evaluations = []
    for essay in essays:
        evaluation = load_evaluation_by_essay(essay.id)
        if evaluation:
            evaluations.append(evaluation)
    
    logger.info(f"Loaded {len(evaluations)} evaluations for assignment {assignment_id}")
    return evaluations


def _normalize_legacy_ai_score(ai_score_data: dict, essay: Essay) -> dict:
    """
    Normalize legacy ai_score format to new EvaluationResult format.
    
    Args:
        ai_score_data: Raw ai_score JSON data
        essay: Essay instance for context
        
    Returns:
        Normalized data dict
    """
    # Resolve metadata
    try:
        # Get student info
        student_name = "未知学生"
        class_name = "未知班级"
        teacher_name = "未知教师"
        
        if essay.enrollment and essay.enrollment.student:
            student_profile = essay.enrollment.student
            if student_profile.user:
                student_name = student_profile.user.full_name or student_profile.user.username
            
            if essay.enrollment.classroom:
                class_name = essay.enrollment.classroom.class_name
                
                # Get teacher from classroom
                if essay.enrollment.classroom.teachers:
                    teacher_profile = essay.enrollment.classroom.teachers[0]
                    if teacher_profile.user:
                        teacher_name = teacher_profile.user.full_name or teacher_profile.user.username
        
        # Get assignment info
        topic = "未知题目"
        if essay.assignment:
            topic = essay.assignment.title
        
        meta = {
            "student": student_name,
            "class": class_name,
            "teacher": teacher_name,
            "topic": topic,
            "date": essay.created_at.strftime('%Y-%m-%d') if essay.created_at else datetime.now().strftime('%Y-%m-%d'),
            "student_id": str(essay.enrollment.student.id) if essay.enrollment and essay.enrollment.student else None,
            "grade": "五年级",  # Default
            "words": len(essay.content or "")
        }
    except Exception as e:
        logger.warning(f"Failed to resolve metadata for essay {essay.id}: {e}")
        meta = {
            "student": "未知学生",
            "class": "未知班级", 
            "teacher": "未知教师",
            "topic": "未知题目",
            "date": datetime.now().strftime('%Y-%m-%d'),
            "grade": "五年级",
            "words": len(essay.content or "")
        }
    
    # Handle different legacy score formats
    scores_data = {"total": 0.0, "rubrics": []}
    
    if "total_score" in ai_score_data:
        scores_data["total"] = float(ai_score_data["total_score"])
    elif "total" in ai_score_data:
        scores_data["total"] = float(ai_score_data["total"])
    elif "scores" in ai_score_data and "total" in ai_score_data["scores"]:
        scores_data["total"] = float(ai_score_data["scores"]["total"])
    
    # Convert dimensions to rubrics
    if "dimensions" in ai_score_data:
        for dim in ai_score_data["dimensions"]:
            if isinstance(dim, dict) and "name" in dim and "score" in dim:
                rubric = {
                    "name": dim["name"],
                    "score": float(dim.get("score", 0)),
                    "max": float(dim.get("max_score", 100)),
                    "weight": float(dim.get("weight", 1.0)),
                    "reason": dim.get("reason", "")
                }
                scores_data["rubrics"].append(rubric)
    elif "scores" in ai_score_data:
        # Convert individual score fields to rubrics
        score_obj = ai_score_data["scores"]
        for field in ["content", "structure", "language", "aesthetics", "norms"]:
            if field in score_obj:
                rubric = {
                    "name": {"content": "内容", "structure": "结构", "language": "语言", 
                           "aesthetics": "文采", "norms": "规范"}.get(field, field),
                    "score": float(score_obj[field]),
                    "max": 20.0,  # Default max
                    "weight": 1.0,
                    "reason": score_obj.get("rationale", "")
                }
                scores_data["rubrics"].append(rubric)
    
    # Add legacy score fields for compatibility
    if "scores" in ai_score_data:
        legacy_scores = ai_score_data["scores"]
        for field in ["content", "structure", "language", "aesthetics", "norms", "rationale"]:
            if field in legacy_scores:
                scores_data[field] = legacy_scores[field]
    
    # Create text block
    text_data = {
        "original": essay.content or "",
        "cleaned": essay.teacher_corrected_text or essay.content or ""
    }
    
    # Create normalized data with enhanced fields for P2 & P4
    normalized = {
        "meta": meta,
        "text": text_data,
        "scores": scores_data,
        "highlights": [],  # Empty for legacy data
        "diagnosis": None,  # Will try to extract from legacy fields
        "analysis": ai_score_data.get("analysis"),
        "diagnostics": ai_score_data.get("diagnostics", []),
        "exercises": ai_score_data.get("exercises", []),
        "summary": ai_score_data.get("summary", ""),
        # P2: Add new fields for enhanced reporting (even if empty)
        "paragraphs": [],
        "feedback_summary": ai_score_data.get("summary", "")  # Use summary as feedback_summary fallback
    }
    
    # Try to extract diagnosis from legacy fields
    diagnosis_data = {}
    if "issue" in ai_score_data:
        diagnosis_data["before"] = ai_score_data.get("issue", "")
    if "evidence" in ai_score_data:
        diagnosis_data["comment"] = ai_score_data.get("evidence", "")
    if "advice" in ai_score_data:
        diagnosis_data["after"] = ", ".join(ai_score_data["advice"]) if isinstance(ai_score_data["advice"], list) else str(ai_score_data["advice"])
    
    if diagnosis_data:
        normalized["diagnosis"] = diagnosis_data
    
    return normalized


def get_assignment_with_students(assignment_id: int):
    """
    Get assignment with related students, classrooms, and teacher data.
    
    Args:
        assignment_id: Assignment ID
        
    Returns:
        Tuple of (EssayAssignment, Classroom, TeacherProfile, List[StudentProfile])
    """
    from sqlalchemy.orm import joinedload
    from app.models import Enrollment
    
    # Load assignment with eager loading
    assignment = db.session.query(EssayAssignment)\
        .options(
            joinedload(EssayAssignment.teacher),
            joinedload(EssayAssignment.classrooms),
            joinedload(EssayAssignment.students)
        )\
        .filter(EssayAssignment.id == assignment_id)\
        .first()
    
    if not assignment:
        return None, None, None, []
    
    teacher = assignment.teacher
    classroom = assignment.classrooms[0] if assignment.classrooms else None
    
    # Get students from both direct assignment and classroom enrollments
    students = list(assignment.students)  # Directly assigned students
    
    # Add students from assigned classrooms
    for classroom_obj in assignment.classrooms:
        classroom_students = db.session.query(StudentProfile)\
            .join(Enrollment, StudentProfile.id == Enrollment.student_profile_id)\
            .filter(
                Enrollment.classroom_id == classroom_obj.id,
                Enrollment.status == 'active'
            )\
            .all()
        
        # Add classroom students if not already in direct assignments
        for student in classroom_students:
            if student not in students:
                students.append(student)
    
    return assignment, classroom, teacher, students


def get_essays_by_assignment(assignment_id: int):
    """
    Get all essays for an assignment.
    
    Args:
        assignment_id: Assignment ID
        
    Returns:
        List of Essay instances
    """
    return db.session.query(Essay)\
        .filter(Essay.assignment_id == assignment_id)\
        .all()