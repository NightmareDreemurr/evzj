"""
Evaluation schemas for the structured LLM evaluation pipeline.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Essay metadata"""
    student_id: Optional[str] = None
    grade: str = Field(..., description="年级, e.g., '五年级'")
    topic: Optional[str] = None
    words: int = Field(default=0, description="字数统计")


class OutlineItem(BaseModel):
    """段落意图分析项"""
    para: int = Field(..., description="段落编号")
    intent: str = Field(..., description="段落意图描述")


class DiagnosticItem(BaseModel):
    """诊断问题项"""
    para: Optional[int] = Field(None, description="段落编号，若为全文问题则为null")
    issue: str = Field(..., description="问题类型")
    evidence: str = Field(..., description="问题证据")
    advice: List[str] = Field(default_factory=list, description="改进建议")


class ExerciseItem(BaseModel):
    """练习建议项"""
    type: str = Field(..., description="练习类型")
    prompt: str = Field(..., description="练习提示")
    hint: List[str] = Field(default_factory=list, description="练习要点")
    sample: Optional[str] = Field(None, description="示例")


class Scores(BaseModel):
    """评分结果"""
    content: float = Field(default=0, description="内容分")
    structure: float = Field(default=0, description="结构分")
    language: float = Field(default=0, description="语言分")
    aesthetics: float = Field(default=0, description="文采分")
    norms: float = Field(default=0, description="规范分")
    total: float = Field(default=0, description="总分")
    rationale: str = Field(default="", description="评分理由")


class Analysis(BaseModel):
    """文本分析结果"""
    outline: List[OutlineItem] = Field(default_factory=list, description="段落意图分析")
    issues: List[str] = Field(default_factory=list, description="问题清单")


class EvaluationResult(BaseModel):
    """统一的评估结果"""
    meta: Meta
    analysis: Analysis
    scores: Scores
    diagnostics: List[DiagnosticItem] = Field(default_factory=list, description="诊断建议")
    exercises: List[ExerciseItem] = Field(default_factory=list, description="练习建议")
    summary: str = Field(default="", description="给家长可读的总结")


class StandardDTO(BaseModel):
    """评分标准数据传输对象"""
    title: str
    total_score: int
    grade: str
    genre: Optional[str] = None
    dimensions: List[Dict[str, Any]] = Field(default_factory=list, description="评分维度详情")
    
    class Config:
        from_attributes = True