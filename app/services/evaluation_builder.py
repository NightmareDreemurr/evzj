"""
Evaluation builder that orchestrates the complete essay evaluation pipeline.
Combines ai_corrector, ai_pregrader, and ai_grader into unified EvaluationResult.
"""
import json
import logging
from datetime import date
from typing import Optional, Dict, Any
from flask import current_app

from app.extensions import db
from app.models import Essay, EssayAssignment, Enrollment
from app.services.ai_corrector import correct_text_with_ai, AIConnectionError
from app.services.ai_pregrader import generate_preanalysis, AIPregraderError  
from app.services.ai_grader import grade_essay_with_ai
from app.services.evaluation_result_types import (
    from_ai_grader_json, from_corrector_text, create_meta_from_essay,
    create_empty_evaluation_result, validate_pregrader_output
)
from app.schemas.evaluation import (
    EvaluationResult, Meta, TextBlock, Scores, RubricScore,
    Diagnosis, Analysis, OutlineItem, DiagnosticItem, ExerciseItem
)
from app.utils.text_stats import count_words_zh

logger = logging.getLogger(__name__)


class EvaluationBuilderError(Exception):
    """Custom exception for evaluation builder errors."""
    pass


def build_and_persist_evaluation(essay_id: int) -> Optional[EvaluationResult]:
    """
    Build complete evaluation result and persist to Essay.ai_evaluation field.
    
    Args:
        essay_id: ID of the essay to evaluate
        
    Returns:
        EvaluationResult object or None if failed
        
    Raises:
        EvaluationBuilderError: If essay not found or critical error occurs
    """
    try:
        # Load essay data
        essay = db.session.get(Essay, essay_id)
        if not essay:
            raise EvaluationBuilderError(f"Essay {essay_id} not found")
        
        logger.info(f"Building evaluation for essay {essay_id}")
        
        # Step 1: Get original text
        original_text = essay.content or ""
        if not original_text.strip():
            logger.warning(f"Essay {essay_id} has no content")
            return None
        
        # Step 2: Get or generate cleaned text
        cleaned_text = None
        try:
            if essay.corrected_content:
                cleaned_text = essay.corrected_content
                logger.debug(f"Using existing corrected content for essay {essay_id}")
            else:
                logger.info(f"Generating cleaned text for essay {essay_id}")
                cleaned_text = correct_text_with_ai(original_text)
                if cleaned_text and cleaned_text != original_text:
                    essay.corrected_content = cleaned_text
                    db.session.commit()
                    logger.debug(f"Saved corrected content for essay {essay_id}")
        except (AIConnectionError, Exception) as e:
            logger.warning(f"Failed to get cleaned text for essay {essay_id}: {e}")
            cleaned_text = original_text
        
        # Step 3: Generate pre-analysis data (if feature enabled)
        preanalysis_data = {}
        if current_app.config.get('EVAL_PREBUILD_ENABLED', True):
            try:
                context = _build_context_for_essay(essay)
                logger.info(f"Generating pre-analysis for essay {essay_id}")
                preanalysis_data = generate_preanalysis(original_text, cleaned_text, context)
                
                if not validate_pregrader_output(preanalysis_data):
                    logger.warning(f"Invalid pre-analysis output for essay {essay_id}, using empty structure")
                    preanalysis_data = {"analysis": {"outline": []}, "diagnostics": [], "exercises": [], "summary": "", "diagnosis": {}}
                    
            except Exception as e:
                logger.error(f"Failed to generate pre-analysis for essay {essay_id}: {e}")
                preanalysis_data = {"analysis": {"outline": []}, "diagnostics": [], "exercises": [], "summary": "", "diagnosis": {}}
        else:
            # Feature disabled, use empty structure
            preanalysis_data = {"analysis": {"outline": []}, "diagnostics": [], "exercises": [], "summary": "", "diagnosis": {}}
        
        # Step 4: Get or generate AI grader scores
        ai_score_data = {}
        try:
            if essay.ai_score:
                ai_score_data = essay.ai_score
                logger.debug(f"Using existing AI score for essay {essay_id}")
            else:
                logger.info(f"Generating AI score for essay {essay_id}")
                # Note: grade_essay_with_ai updates the essay.ai_score field directly
                grade_essay_with_ai(essay_id)
                db.session.refresh(essay)
                ai_score_data = essay.ai_score or {}
        except Exception as e:
            logger.error(f"Failed to get AI score for essay {essay_id}: {e}")
            ai_score_data = {}
        
        # Step 5: Build unified EvaluationResult
        evaluation_result = _build_evaluation_result(essay, original_text, cleaned_text, preanalysis_data, ai_score_data)
        
        # Step 6: Persist to database
        try:
            essay.ai_evaluation = evaluation_result.model_dump()
            essay.evaluation_status = 'ai_generated'  # Set initial status
            db.session.commit()
            logger.info(f"Successfully persisted evaluation for essay {essay_id}")
        except Exception as e:
            logger.error(f"Failed to persist evaluation for essay {essay_id}: {e}")
            db.session.rollback()
            # Don't raise exception - return the result even if persistence failed
        
        return evaluation_result
        
    except EvaluationBuilderError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in build_and_persist_evaluation for essay {essay_id}: {e}", exc_info=True)
        return None


def _build_context_for_essay(essay: Essay) -> Dict[str, Any]:
    """Build context dictionary for pre-analysis."""
    context = {}
    
    try:
        # Get assignment info
        if essay.assignment:
            context['topic'] = essay.assignment.title
            
            # Get grading standard info
            if essay.assignment.grading_standard:
                standard = essay.assignment.grading_standard
                context['grade'] = getattr(standard, 'grade', '')
                context['total_score'] = getattr(standard, 'total_score', 100)
        
        # Get student info
        if essay.enrollment and essay.enrollment.student and essay.enrollment.student.user:
            context['student_name'] = essay.enrollment.student.user.full_name
            context['student_id'] = essay.enrollment.student.id
        
        # Get teacher info
        if essay.assignment and essay.assignment.teacher_profile and essay.assignment.teacher_profile.user:
            context['teacher_name'] = essay.assignment.teacher_profile.user.full_name
        
        # Get class info
        if essay.enrollment and essay.enrollment.classroom:
            context['class_name'] = essay.enrollment.classroom.name
        
        # Word count
        if essay.content:
            context['word_count'] = count_words_zh(essay.content)
        
        # Date
        context['date'] = essay.created_at.date().isoformat() if essay.created_at else date.today().isoformat()
        
    except Exception as e:
        logger.warning(f"Failed to build complete context for essay {essay.id}: {e}")
    
    return context


def _build_evaluation_result(essay: Essay, original_text: str, cleaned_text: Optional[str], 
                           preanalysis_data: Dict[str, Any], ai_score_data: Dict[str, Any]) -> EvaluationResult:
    """Build the unified EvaluationResult from all components."""
    
    # Build meta information
    context = _build_context_for_essay(essay)
    meta_dict = create_meta_from_essay(essay.id, context)
    meta = Meta(**meta_dict)
    
    # Build text block
    text_dict = from_corrector_text(original_text, cleaned_text)
    text = TextBlock(**text_dict)
    
    # Build scores from AI grader
    scores_dict = from_ai_grader_json(ai_score_data, essay.id)
    scores = Scores(**scores_dict)
    
    # Build analysis from pre-grader
    analysis = None
    if preanalysis_data.get("analysis", {}).get("outline"):
        outline_data = preanalysis_data["analysis"]["outline"]
        outline_items = []
        for item in outline_data:
            if isinstance(item, dict) and "para" in item and "intent" in item:
                outline_items.append(OutlineItem(para=item["para"], intent=item["intent"]))
        if outline_items:
            analysis = Analysis(outline=outline_items, issues=[])
    
    # Build diagnostics from pre-grader
    diagnostics = []
    for item in preanalysis_data.get("diagnostics", []):
        if isinstance(item, dict):
            try:
                diagnostic = DiagnosticItem(
                    para=item.get("para"),
                    issue=item.get("issue", ""),
                    evidence=item.get("evidence", ""),
                    advice=item.get("advice", [])
                )
                diagnostics.append(diagnostic)
            except Exception as e:
                logger.warning(f"Failed to create diagnostic item: {e}")
                continue
    
    # Build exercises from pre-grader
    exercises = []
    for item in preanalysis_data.get("exercises", []):
        if isinstance(item, dict):
            try:
                exercise = ExerciseItem(
                    type=item.get("type", ""),
                    prompt=item.get("prompt", ""),
                    hint=item.get("hint", []),
                    sample=item.get("sample")
                )
                exercises.append(exercise)
            except Exception as e:
                logger.warning(f"Failed to create exercise item: {e}")
                continue
    
    # Build diagnosis from pre-grader
    diagnosis = None
    diagnosis_data = preanalysis_data.get("diagnosis", {})
    if diagnosis_data and isinstance(diagnosis_data, dict):
        try:
            diagnosis = Diagnosis(
                before=diagnosis_data.get("before"),
                comment=diagnosis_data.get("comment"),
                after=diagnosis_data.get("after")
            )
        except Exception as e:
            logger.warning(f"Failed to create diagnosis: {e}")
    
    # Get summary
    summary = preanalysis_data.get("summary", "")
    
    # Build final result
    evaluation_result = EvaluationResult(
        meta=meta,
        text=text,
        scores=scores,
        highlights=[],  # Empty for now
        diagnosis=diagnosis,
        analysis=analysis,
        diagnostics=diagnostics,
        exercises=exercises,
        summary=summary
    )
    
    return evaluation_result


def load_evaluation_from_essay(essay_id: int) -> Optional[EvaluationResult]:
    """
    Load existing EvaluationResult from Essay.ai_evaluation field.
    
    Args:
        essay_id: ID of the essay
        
    Returns:
        EvaluationResult object or None if not found/invalid
    """
    try:
        essay = db.session.get(Essay, essay_id)
        if not essay or not essay.ai_evaluation:
            return None
        
        evaluation_data = essay.ai_evaluation
        if isinstance(evaluation_data, str):
            evaluation_data = json.loads(evaluation_data)
        
        return EvaluationResult(**evaluation_data)
        
    except Exception as e:
        logger.error(f"Failed to load evaluation for essay {essay_id}: {e}")
        return None