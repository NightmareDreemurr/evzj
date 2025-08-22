"""
Evaluation schemas for the structured LLM evaluation pipeline.
"""
from typing import List, Dict, Any, Optional, Literal, Union
from datetime import date
from pydantic import BaseModel, Field, ConfigDict


# New models for DOCX export
class RubricScore(BaseModel):
    """Individual rubric score"""
    name: str = Field(..., description="评分维度名称")
    score: float = Field(..., description="得分")
    max: float = Field(..., description="满分")
    weight: float = Field(default=1.0, description="权重")
    reason: str = Field(default="", description="评分理由")


class Span(BaseModel):
    """Text span for highlights"""
    start: int = Field(..., description="起始位置")
    end: int = Field(..., description="结束位置")
    text: str = Field(..., description="文本内容")


class Highlight(BaseModel):
    """Text highlight/annotation"""
    type: Literal["grammar", "spelling", "style", "logic", "vocabulary"] = Field(..., description="高亮类型")
    span: Span = Field(..., description="文本位置")
    message: str = Field(..., description="说明信息")
    severity: Literal["low", "medium", "high"] = Field(..., description="严重程度")


class Diagnosis(BaseModel):
    """Diagnostic feedback"""
    before: Optional[str] = Field(None, description="诊断前言")
    comment: Optional[str] = Field(None, description="诊断评语")
    after: Optional[str] = Field(None, description="诊断后语")


class Meta(BaseModel):
    """Essay metadata for DOCX export"""
    # New required fields for DOCX export
    student: Optional[str] = Field(None, description="学生姓名")
    class_: Optional[str] = Field(None, alias="class", description="班级")
    teacher: Optional[str] = Field(None, description="教师姓名")
    topic: Optional[str] = Field(None, description="作文题目")
    date: Optional[str] = Field(None, description="日期")
    
    # Legacy fields for compatibility with existing pipeline
    student_id: Optional[str] = None
    grade: Optional[str] = Field(None, description="年级, e.g., '五年级'")
    words: int = Field(default=0, description="字数统计")
    
    model_config = ConfigDict(populate_by_name=True)


class TextBlock(BaseModel):
    """Essay text content"""
    original: str = Field(..., description="原始文本")
    cleaned: Optional[str] = Field(None, description="清洗后文本")


class Scores(BaseModel):
    """Evaluation scores with rubrics"""
    total: float = Field(..., description="总分")
    rubrics: List[RubricScore] = Field(default_factory=list, description="各维度评分")
    
    # Legacy fields for compatibility  
    content: Optional[float] = Field(None, description="内容分")
    structure: Optional[float] = Field(None, description="结构分")
    language: Optional[float] = Field(None, description="语言分")
    aesthetics: Optional[float] = Field(None, description="文采分")
    norms: Optional[float] = Field(None, description="规范分")
    rationale: Optional[str] = Field(None, description="评分理由")


# Legacy models for backward compatibility
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


class Analysis(BaseModel):
    """文本分析结果"""
    outline: List[OutlineItem] = Field(default_factory=list, description="段落意图分析")
    issues: List[str] = Field(default_factory=list, description="问题清单")


class EvaluationResult(BaseModel):
    """统一的评估结果"""
    meta: Meta
    text: Optional[TextBlock] = None  # For DOCX export
    scores: Scores
    highlights: List[Highlight] = Field(default_factory=list, description="高亮标注")
    diagnosis: Optional[Diagnosis] = None  # For DOCX export
    
    # Legacy fields for backward compatibility
    analysis: Optional[Analysis] = None
    diagnostics: List[DiagnosticItem] = Field(default_factory=list, description="诊断建议")
    exercises: List[ExerciseItem] = Field(default_factory=list, description="练习建议")
    summary: str = Field(default="", description="给家长可读的总结")


class StandardDTO(BaseModel):
    """评分标准数据传输对象"""
    model_config = ConfigDict(from_attributes=True)
    
    title: str
    total_score: int
    grade: str
    genre: Optional[str] = None
    dimensions: List[Dict[str, Any]] = Field(default_factory=list, description="评分维度详情")


def to_context(evaluation: EvaluationResult) -> Dict[str, Any]:
    """Convert EvaluationResult to template context for docxtpl rendering"""
    context = evaluation.model_dump()
    
    # Ensure required fields are present for DOCX export
    meta = context.get('meta', {})
    if not meta.get('student'):
        meta['student'] = meta.get('student_id', '未知学生')
    if not meta.get('class_'):
        meta['class_'] = '未知班级'
    if not meta.get('teacher'):
        meta['teacher'] = '未知教师'
    if not meta.get('topic'):
        meta['topic'] = '未知题目'
    if not meta.get('date'):
        meta['date'] = '未知日期'
    
    # Convert date to string if needed
    if hasattr(context.get('meta', {}).get('date'), 'strftime'):
        context['meta']['date'] = context['meta']['date'].strftime('%Y-%m-%d')
    
    # Group highlights by type and severity for easy template rendering
    highlight_summary = {}
    if context.get('highlights'):
        for highlight in context['highlights']:
            highlight_type = highlight['type']
            severity = highlight['severity']
            
            if highlight_type not in highlight_summary:
                highlight_summary[highlight_type] = {'low': 0, 'medium': 0, 'high': 0, 'examples': []}
            
            highlight_summary[highlight_type][severity] += 1
            if len(highlight_summary[highlight_type]['examples']) < 3:  # Limit examples
                highlight_summary[highlight_type]['examples'].append(highlight['span']['text'])
    
    context['highlight_summary'] = highlight_summary
    
    return context