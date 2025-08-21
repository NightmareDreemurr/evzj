"""
Structured LLM evaluation pipeline.

This module implements the main pipeline: analyze → load_standard → score → moderate → assemble
"""
import json
import logging
from typing import Dict, Any

from app.llm.provider import get_llm_provider, LLMConnectionError
from app.llm.prompts import PROMPT_ANALYZE, PROMPT_SCORE
from app.dao.standards import get_grading_standard
from app.schemas.evaluation import (
    EvaluationResult, Meta, Analysis, Scores, DiagnosticItem, 
    ExerciseItem, StandardDTO, OutlineItem
)

logger = logging.getLogger(__name__)


def evaluate_essay(essay_text: str, meta: dict) -> EvaluationResult:
    """
    Main evaluation pipeline entry point.
    
    Args:
        essay_text: The essay content to evaluate
        meta: Dictionary containing essay metadata (student_id, grade, topic, etc.)
        
    Returns:
        EvaluationResult: Structured evaluation results
        
    Raises:
        Exception: If pipeline fails at any step
    """
    logger.info(f"Starting evaluation pipeline for student {meta.get('student_id', 'unknown')}")
    
    try:
        # Step 1: Structure analysis
        analysis_result = analyze(essay_text, meta)
        logger.info("Analysis step completed")
        
        # Step 2: Load grading standard
        standard = load_standard(meta)
        if not standard:
            raise Exception(f"Failed to load grading standard for grade {meta.get('grade', 'unknown')}")
        logger.info(f"Loaded standard: {standard.title}")
        
        # Step 3: Score the essay
        scores_result = score(essay_text, standard, analysis_result)
        logger.info("Scoring step completed")
        
        # Step 4: Moderate content (placeholder for now)
        moderated_data = moderate({
            'analysis': analysis_result,
            'scores': scores_result,
            'meta': meta
        })
        logger.info("Moderation step completed")
        
        # Step 5: Assemble final result
        result = assemble(
            meta=meta,
            analysis=moderated_data['analysis'],
            scores=moderated_data['scores'],
            diagnostics=[],  # TODO: Generate diagnostics
            exercises=[],    # TODO: Generate exercises
            summary=""       # TODO: Generate summary
        )
        logger.info("Assembly step completed")
        
        return result
        
    except Exception as e:
        logger.error(f"Evaluation pipeline failed: {e}")
        raise


def analyze(essay_text: str, meta: dict) -> dict:
    """
    Analyze essay structure and identify issues.
    
    Args:
        essay_text: Essay content
        meta: Essay metadata
        
    Returns:
        Dictionary with outline and issues
    """
    try:
        llm = get_llm_provider()
        
        prompt = PROMPT_ANALYZE.format(
            essay_text=essay_text,
            grade=meta.get('grade', '五年级'),
            genre=meta.get('genre', '记叙文')
        )
        
        result = llm.call_llm(prompt, require_json=True)
        
        # Validate structure
        if 'outline' not in result:
            result['outline'] = []
        if 'issues' not in result:
            result['issues'] = []
            
        return result
        
    except Exception as e:
        logger.error(f"Analysis step failed: {e}")
        # Return default structure on failure
        return {
            'outline': [{'para': 1, 'intent': '分析失败，使用默认结构'}],
            'issues': ['AI分析失败']
        }


def load_standard(meta: dict) -> StandardDTO:
    """
    Load grading standard based on metadata.
    
    Args:
        meta: Essay metadata containing grade and genre
        
    Returns:
        StandardDTO or None if not found
    """
    grade = meta.get('grade', '五年级')
    genre = meta.get('genre', 'narrative')
    
    return get_grading_standard(grade, genre)


def score(essay_text: str, standard: StandardDTO, analysis: dict) -> dict:
    """
    Score essay using standard and analysis.
    
    Args:
        essay_text: Essay content
        standard: Grading standard
        analysis: Analysis results from analyze()
        
    Returns:
        Dictionary with scoring results
    """
    try:
        llm = get_llm_provider()
        
        # Format standard for prompt
        standard_text = _format_standard_for_prompt(standard)
        analysis_json = json.dumps(analysis, ensure_ascii=False, indent=2)
        
        prompt = PROMPT_SCORE.format(
            standard_text=standard_text,
            analysis_json=analysis_json,
            essay_text=essay_text
        )
        
        result = llm.call_llm(prompt, require_json=True)
        
        # Validate scoring structure
        required_fields = ['content', 'structure', 'language', 'aesthetics', 'norms', 'total', 'rationale']
        for field in required_fields:
            if field not in result:
                if field == 'rationale':
                    result[field] = '评分完成'
                else:
                    result[field] = 0.0
                    
        return result
        
    except Exception as e:
        logger.error(f"Scoring step failed: {e}")
        # Return default scores on failure
        return {
            'content': 0.0,
            'structure': 0.0,
            'language': 0.0,
            'aesthetics': 0.0,
            'norms': 0.0,
            'total': 0.0,
            'rationale': f'评分失败: {str(e)}'
        }


def moderate(payload: dict) -> dict:
    """
    Moderate content for compliance and safety.
    
    Args:
        payload: Dictionary containing analysis and scores
        
    Returns:
        Moderated payload
    """
    # Placeholder implementation - just pass through for now
    # In production, this would implement content filtering and safety checks
    return payload


def assemble(meta: dict, analysis: dict, scores: dict, 
             diagnostics: list, exercises: list, summary: str) -> EvaluationResult:
    """
    Assemble final evaluation result.
    
    Args:
        meta: Essay metadata
        analysis: Analysis results
        scores: Scoring results  
        diagnostics: Diagnostic items
        exercises: Exercise suggestions
        summary: Summary for parents
        
    Returns:
        EvaluationResult instance
    """
    # Create Meta object
    meta_obj = Meta(
        student_id=meta.get('student_id'),
        grade=meta.get('grade', '五年级'),
        topic=meta.get('topic'),
        words=meta.get('words', 0)
    )
    
    # Create Analysis object
    outline_items = []
    for item in analysis.get('outline', []):
        outline_items.append(OutlineItem(
            para=item.get('para', 1),
            intent=item.get('intent', '')
        ))
    
    analysis_obj = Analysis(
        outline=outline_items,
        issues=analysis.get('issues', [])
    )
    
    # Create Scores object
    scores_obj = Scores(
        content=scores.get('content', 0.0),
        structure=scores.get('structure', 0.0),
        language=scores.get('language', 0.0),
        aesthetics=scores.get('aesthetics', 0.0),
        norms=scores.get('norms', 0.0),
        total=scores.get('total', 0.0),
        rationale=scores.get('rationale', '')
    )
    
    return EvaluationResult(
        meta=meta_obj,
        analysis=analysis_obj,
        scores=scores_obj,
        diagnostics=diagnostics,
        exercises=exercises,
        summary=summary
    )


def _format_standard_for_prompt(standard: StandardDTO) -> str:
    """Format grading standard for LLM prompt"""
    lines = [f"评分标准：{standard.title}", f"总分：{standard.total_score}分", ""]
    
    for dim in standard.dimensions:
        lines.append(f"**{dim['name']}** (满分：{dim['max_score']}分)")
        
        for rubric in dim.get('rubrics', []):
            lines.append(f"- {rubric['level_name']} ({rubric['min_score']}-{rubric['max_score']}分): {rubric['description']}")
        
        lines.append("")
    
    return "\n".join(lines)