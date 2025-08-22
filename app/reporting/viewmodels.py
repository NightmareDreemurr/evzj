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