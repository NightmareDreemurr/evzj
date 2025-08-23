"""
ViewModel mapping layer for batch DOCX reporting.

This module defines Pydantic models that map evaluation data
to template-friendly structures for batch DOCX generation.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ScoreItemVM(BaseModel):
    """Individual score item view model."""
    key: str = Field(..., description="Score dimension key")
    name: str = Field(..., description="Score dimension name")
    score: float = Field(..., description="Actual score")
    max_score: float = Field(..., description="Maximum possible score")


class ScoreVM(BaseModel):
    """Score summary view model."""
    total: float = Field(..., description="Total score")
    items: List[ScoreItemVM] = Field(default_factory=list, description="Individual score items")


class ParaVM(BaseModel):
    """Paragraph view model for paragraph-level feedback."""
    para_num: int = Field(..., description="Paragraph number")
    original_text: str = Field(..., description="Original paragraph text")
    feedback: str = Field(default="", description="Teacher/AI feedback and suggestions")
    polished_text: str = Field(default="", description="Polished version of the paragraph")
    intent: str = Field(default="", description="Paragraph writing intent")


class ExerciseVM(BaseModel):
    """Exercise view model for personalized writing exercises."""
    type: str = Field(..., description="Exercise type")
    prompt: str = Field(..., description="Exercise prompt/question")
    hints: List[str] = Field(default_factory=list, description="Exercise hints and key points")
    sample: str = Field(default="", description="Sample answer or example")


class StudentReportVM(BaseModel):
    """Student report view model for batch processing."""
    student_id: int = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    student_no: Optional[str] = Field(None, description="Student number")
    essay_id: int = Field(..., description="Essay ID")
    topic: str = Field(..., description="Essay topic")
    words: Optional[int] = Field(None, description="Word count")
    scores: ScoreVM = Field(..., description="Score information")
    feedback: str = Field(default="", description="AI feedback text")
    original_paragraphs: List[str] = Field(default_factory=list, description="Original text paragraphs")
    
    # New fields for enhanced reporting
    paragraphs: List[ParaVM] = Field(default_factory=list, description="Paragraph-level feedback")
    exercises: List[ExerciseVM] = Field(default_factory=list, description="Personalized writing exercises")
    scanned_images: List[str] = Field(default_factory=list, description="Scanned image file paths")
    feedback_summary: str = Field(default="", description="Combined summary and diagnostic feedback")
    
    # Review status tracking
    review_status: str = Field(default="ai_generated", description="Evaluation review status")
    reviewed_by: Optional[int] = Field(None, description="Teacher ID who reviewed")
    reviewed_at: Optional[str] = Field(None, description="Review timestamp")


class AssignmentReportVM(BaseModel):
    """Assignment batch report view model."""
    assignment_id: int = Field(..., description="Assignment ID")
    title: str = Field(..., description="Assignment title")
    classroom: Dict[str, Any] = Field(default_factory=dict, description="Classroom information")
    teacher: Dict[str, Any] = Field(default_factory=dict, description="Teacher information")
    students: List[StudentReportVM] = Field(default_factory=list, description="Student reports")


def safe_get_student_name(evaluation_result) -> str:
    """Safely extract student name with fallback."""
    if hasattr(evaluation_result, 'meta') and evaluation_result.meta:
        return evaluation_result.meta.student or "未知学生"
    return "未知学生"


def safe_get_topic(evaluation_result) -> str:
    """Safely extract topic with fallback."""
    if hasattr(evaluation_result, 'meta') and evaluation_result.meta:
        return evaluation_result.meta.topic or "未知题目"
    return "未知题目"


def safe_get_feedback(evaluation_result) -> str:
    """Safely extract feedback text with fallback."""
    feedback_parts = []
    
    # Try to get diagnosis text
    if hasattr(evaluation_result, 'diagnosis') and evaluation_result.diagnosis:
        if evaluation_result.diagnosis.comment:
            feedback_parts.append(evaluation_result.diagnosis.comment)
        if evaluation_result.diagnosis.before:
            feedback_parts.append(f"改进前建议: {evaluation_result.diagnosis.before}")
        if evaluation_result.diagnosis.after:
            feedback_parts.append(f"改进后建议: {evaluation_result.diagnosis.after}")
    
    # Fall back to summary if available
    if not feedback_parts and hasattr(evaluation_result, 'summary'):
        feedback_parts.append(evaluation_result.summary or "")
    
    return "\n".join(feedback_parts) or "暂无评语"


def safe_get_original_paragraphs(evaluation_result) -> List[str]:
    """Safely extract original text paragraphs with fallback."""
    paragraphs = []
    
    if hasattr(evaluation_result, 'text') and evaluation_result.text:
        original = evaluation_result.text.original
        if original:
            # Split by newlines and filter empty lines
            paragraphs = [p.strip() for p in original.split('\n') if p.strip()]
    
    return paragraphs or ["原文内容不可用"]


def map_paragraphs_to_vm(evaluation_result) -> List[ParaVM]:
    """Map evaluation data to paragraph view models."""
    paragraphs = []
    original_paras = safe_get_original_paragraphs(evaluation_result)
    
    # Get outline information if available
    outline_map = {}
    if hasattr(evaluation_result, 'analysis') and evaluation_result.analysis:
        for outline_item in evaluation_result.analysis.outline or []:
            outline_map[outline_item.para] = outline_item.intent
    
    # Get diagnostics grouped by paragraph
    diagnostics_map = {}
    if hasattr(evaluation_result, 'diagnostics'):
        for diag in evaluation_result.diagnostics or []:
            para_num = diag.para or 0
            if para_num not in diagnostics_map:
                diagnostics_map[para_num] = []
            diagnostics_map[para_num].append(diag)
    
    # Create ParaVM for each paragraph
    for i, original_text in enumerate(original_paras, 1):
        feedback_parts = []
        
        # Add intent from analysis
        intent = outline_map.get(i, "")
        if intent:
            feedback_parts.append(f"写作意图：{intent}")
        
        # Add diagnostics for this paragraph
        para_diagnostics = diagnostics_map.get(i, [])
        for diag in para_diagnostics:
            feedback_parts.append(f"问题：{diag.issue}")
            if diag.evidence:
                feedback_parts.append(f"证据：{diag.evidence}")
            if diag.advice:
                feedback_parts.append(f"建议：{'; '.join(diag.advice)}")
        
        # Create polished text (for now, same as original - can be enhanced later)
        polished_text = original_text
        
        paragraphs.append(ParaVM(
            para_num=i,
            original_text=original_text,
            feedback="\n".join(feedback_parts) if feedback_parts else "无具体反馈",
            polished_text=polished_text,
            intent=intent
        ))
    
    return paragraphs


def map_exercises_to_vm(evaluation_result) -> List[ExerciseVM]:
    """Map evaluation exercises to exercise view models."""
    exercises = []
    
    if hasattr(evaluation_result, 'exercises'):
        for exercise in evaluation_result.exercises or []:
            exercises.append(ExerciseVM(
                type=exercise.type,
                prompt=exercise.prompt,
                hints=exercise.hint or [],
                sample=exercise.sample or ""
            ))
    
    return exercises


def build_feedback_summary(evaluation_result) -> str:
    """Build comprehensive feedback summary from evaluation data."""
    summary_parts = []
    
    # Add main summary
    if hasattr(evaluation_result, 'summary') and evaluation_result.summary:
        summary_parts.append("总体评价：")
        summary_parts.append(evaluation_result.summary)
    
    # Add analysis issues
    if hasattr(evaluation_result, 'analysis') and evaluation_result.analysis:
        if evaluation_result.analysis.issues:
            summary_parts.append("\n主要问题：")
            for issue in evaluation_result.analysis.issues:
                summary_parts.append(f"• {issue}")
    
    # Add general diagnostics (those not tied to specific paragraphs)
    if hasattr(evaluation_result, 'diagnostics'):
        general_diagnostics = [d for d in evaluation_result.diagnostics or [] if not d.para]
        if general_diagnostics:
            summary_parts.append("\n整体建议：")
            for diag in general_diagnostics:
                summary_parts.append(f"• {diag.issue}: {'; '.join(diag.advice) if diag.advice else '需要改进'}")
    
    return "\n".join(summary_parts) if summary_parts else "暂无详细反馈"


def map_scores_to_vm(evaluation_result) -> ScoreVM:
    """Map evaluation scores to ScoreVM."""
    items = []
    total_score = 0.0
    
    if hasattr(evaluation_result, 'scores') and evaluation_result.scores:
        # Handle new format with rubrics
        if hasattr(evaluation_result.scores, 'rubrics') and evaluation_result.scores.rubrics:
            for rubric in evaluation_result.scores.rubrics:
                items.append(ScoreItemVM(
                    key=getattr(rubric, 'name', ''),
                    name=getattr(rubric, 'name', '未知维度'),
                    score=getattr(rubric, 'score', 0.0),
                    max_score=getattr(rubric, 'max', 100.0)
                ))
        
        # Use total score if available
        if hasattr(evaluation_result.scores, 'total'):
            total_score = evaluation_result.scores.total
        else:
            # Calculate from items
            total_score = sum(item.score for item in items)
    
    return ScoreVM(total=total_score, items=items)