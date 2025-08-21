"""
Meta resolver service for essay evaluation.

This service resolves essay metadata from database records,
including grade from student/enrollment and genre from assignment standards.
"""
import logging
from typing import Dict, Optional
from app.models import Essay, Enrollment, StudentProfile, EssayAssignment, GradingStandard, GradeLevel
from app.extensions import db

logger = logging.getLogger(__name__)


def resolve_meta(essay_id: int) -> Dict[str, any]:
    """
    Resolve essay metadata from database records.
    
    Args:
        essay_id: The essay ID to resolve metadata for
        
    Returns:
        Dictionary containing resolved metadata:
        - student_id: str
        - grade: str (from enrollment/student data)
        - genre: str (from assignment grading standard, fallback to 'narrative')
        - topic: str (from assignment title)
        - words: int (to be calculated by caller with proper word counting)
    """
    try:
        # Get the essay with all related data
        essay = db.session.query(Essay)\
            .join(Enrollment, Essay.enrollment_id == Enrollment.id)\
            .join(StudentProfile, Enrollment.student_profile_id == StudentProfile.id)\
            .join(EssayAssignment, Essay.assignment_id == EssayAssignment.id)\
            .outerjoin(GradingStandard, EssayAssignment.grading_standard_id == GradingStandard.id)\
            .outerjoin(GradeLevel, GradingStandard.grade_level_id == GradeLevel.id)\
            .filter(Essay.id == essay_id)\
            .first()
        
        if not essay:
            logger.error(f"Essay {essay_id} not found")
            return _get_fallback_meta()
        
        # Get student_id
        student_id = str(essay.enrollment.student.id)
        
        # Get grade from GradeLevel through assignment's grading standard
        grade = None
        if (essay.assignment and 
            essay.assignment.grading_standard and 
            essay.assignment.grading_standard.grade_level):
            grade = essay.assignment.grading_standard.grade_level.name
        
        # Fallback: If no grade from assignment, use a default
        if not grade:
            grade = "五年级"  # Default fallback
            logger.warning(f"No grade found for essay {essay_id}, using fallback: {grade}")
        
        # Get genre from grading standard or YAML mapping
        genre = _resolve_genre_from_standard(essay.assignment.grading_standard if essay.assignment else None)
        
        # Get topic from assignment
        topic = essay.assignment.title if essay.assignment else "未知题目"
        
        meta = {
            'student_id': student_id,
            'grade': grade,
            'genre': genre,
            'topic': topic,
            'words': 0  # To be filled by caller with proper word counting
        }
        
        logger.info(f"Resolved meta for essay {essay_id}: grade={grade}, genre={genre}")
        return meta
        
    except Exception as e:
        logger.error(f"Error resolving meta for essay {essay_id}: {e}")
        return _get_fallback_meta()


def _resolve_genre_from_standard(grading_standard: Optional[GradingStandard]) -> str:
    """
    Resolve genre from grading standard or fallback to YAML mapping.
    
    Args:
        grading_standard: The grading standard to check
        
    Returns:
        Genre string (e.g., 'narrative', 'expository')
    """
    # First check if the grading standard has any genre indicators
    if grading_standard and grading_standard.title:
        title_lower = grading_standard.title.lower()
        if "记叙文" in title_lower or "narrative" in title_lower:
            return "narrative"
        elif "说明文" in title_lower or "expository" in title_lower:
            return "expository"
        elif "议论文" in title_lower or "argumentative" in title_lower:
            return "argumentative"
    
    # Fallback to YAML mapping by grade (you could extend this mapping)
    genre_mapping = {
        "一年级": "narrative",
        "二年级": "narrative", 
        "三年级": "narrative",
        "四年级": "narrative",
        "五年级": "narrative",
        "六年级": "narrative",
        # Add more mappings as needed
    }
    
    # For now, default to narrative as it's the most common for elementary grades
    return "narrative"


def _get_fallback_meta() -> Dict[str, any]:
    """
    Get fallback metadata when resolution fails.
    
    Returns:
        Default metadata dictionary
    """
    return {
        'student_id': 'unknown',
        'grade': '五年级',
        'genre': 'narrative', 
        'topic': '未知题目',
        'words': 0
    }