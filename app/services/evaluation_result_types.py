"""
Data types and helper functions for the evaluation pipeline.
Provides structured types for EvaluationResult and mapping functions.
"""
from typing import List, Dict, Any, Optional
from datetime import date
from app.schemas.evaluation import (
    EvaluationResult, Meta, TextBlock, Scores, RubricScore, 
    Diagnosis, DiagnosticItem, ExerciseItem, Analysis, OutlineItem
)


def from_ai_grader_json(ai_score_data: dict, essay_id: int) -> Dict[str, Any]:
    """
    Maps AI grader JSON output to EvaluationResult scores/rubrics structure.
    
    Args:
        ai_score_data: Raw JSON from ai_grader service
        essay_id: Essay ID for context
        
    Returns:
        Dictionary with scores and rubrics data
    """
    if not ai_score_data:
        return {
            "total": 0,
            "rubrics": []
        }
    
    scores_data = {
        "total": ai_score_data.get("total_score", 0),
        "rubrics": []
    }
    
    # Map dimensions to rubrics if available
    if "scores" in ai_score_data and isinstance(ai_score_data["scores"], dict):
        score_obj = ai_score_data["scores"]
        dimensions = ai_score_data.get("dimensions", [])
        
        # Create rubrics from dimension scores
        for field in ["content", "structure", "language", "aesthetics", "norms"]:
            if field in score_obj:
                try:
                    # Find corresponding dimension feedback
                    feedback = ""
                    for dim in dimensions:
                        if dim.get("dimension", "").lower() == field or field in dim.get("dimension", "").lower():
                            feedback = dim.get("feedback", "")
                            break
                    
                    rubric = {
                        "name": {
                            "content": "内容", 
                            "structure": "结构", 
                            "language": "语言",
                            "aesthetics": "文采", 
                            "norms": "规范"
                        }.get(field, field),
                        "score": float(score_obj[field]),
                        "max": 20.0,  # Default max score
                        "weight": 1.0,
                        "reason": feedback or str(score_obj.get("rationale", ""))
                    }
                    scores_data["rubrics"].append(rubric)
                except (ValueError, TypeError):
                    continue
    
    return scores_data


def from_corrector_text(original_text: str, cleaned_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Maps corrector output to TextBlock structure.
    
    Args:
        original_text: Original essay text
        cleaned_text: AI-corrected text (optional)
        
    Returns:
        Dictionary with text data
    """
    return {
        "original": original_text or "",
        "cleaned": cleaned_text or original_text or ""
    }


def create_meta_from_essay(essay_id: int, essay_data: dict) -> Dict[str, Any]:
    """
    Creates Meta structure from essay context.
    
    Args:
        essay_id: Essay ID
        essay_data: Dictionary with essay metadata
        
    Returns:
        Dictionary with meta data
    """
    return {
        "student": essay_data.get("student_name", ""),
        "student_id": str(essay_data.get("student_id", "")),
        "class_": essay_data.get("class_name", ""),
        "teacher": essay_data.get("teacher_name", ""),
        "topic": essay_data.get("topic", ""),
        "date": essay_data.get("date", date.today().isoformat()),
        "grade": essay_data.get("grade", ""),
        "words": essay_data.get("word_count", 0)
    }


def create_empty_evaluation_result(essay_id: int, meta_data: dict) -> EvaluationResult:
    """
    Creates an empty EvaluationResult with basic structure for fallback scenarios.
    
    Args:
        essay_id: Essay ID
        meta_data: Meta information dictionary
        
    Returns:
        EvaluationResult with empty/default values
    """
    meta = Meta(**create_meta_from_essay(essay_id, meta_data))
    scores = Scores(total=0, rubrics=[])
    
    return EvaluationResult(
        meta=meta,
        scores=scores,
        text=None,
        highlights=[],
        diagnosis=None,
        analysis=None,
        diagnostics=[],
        exercises=[],
        summary=""
    )


def validate_pregrader_output(output_data: dict) -> bool:
    """
    Validates that pre-grader output contains required fields.
    
    Args:
        output_data: Dictionary from AI pre-grader
        
    Returns:
        True if valid structure, False otherwise
    """
    required_fields = ["analysis", "diagnostics", "exercises", "summary"]
    
    if not isinstance(output_data, dict):
        return False
    
    for field in required_fields:
        if field not in output_data:
            return False
    
    # Validate analysis.outline structure
    analysis = output_data.get("analysis", {})
    if not isinstance(analysis, dict) or "outline" not in analysis:
        return False
    
    outline = analysis["outline"]
    if not isinstance(outline, list):
        return False
    
    # Validate diagnostics structure
    diagnostics = output_data.get("diagnostics", [])
    if not isinstance(diagnostics, list):
        return False
    
    # Validate exercises structure
    exercises = output_data.get("exercises", [])
    if not isinstance(exercises, list):
        return False
    
    return True