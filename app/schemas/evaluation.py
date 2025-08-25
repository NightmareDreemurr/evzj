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
    level: str = Field(default="", description="评分等级 (A, B, C等)")
    
    # Optional fields for enhanced AI feedback
    example_good_sentence: Optional[List[str]] = Field(default=None, description="优秀句子示例")
    example_improvement_suggestion: Optional[List[Dict[str, str]]] = Field(default=None, description="改进建议示例")


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
    
    # Teacher-view aligned export fields
    assignmentTitle: Optional[str] = Field(None, description="作业标题")
    studentName: Optional[str] = Field(None, description="学生姓名")
    submittedAt: Optional[str] = Field(None, description="提交时间")
    currentEssayContent: Optional[str] = Field(None, description="当前作文内容(教师最终版本)")
    
    # AI enhanced content for export
    outline: List[Dict[str, Any]] = Field(default_factory=list, description="段落大纲分析")
    diagnoses: List[Dict[str, Any]] = Field(default_factory=list, description="诊断建议")
    personalizedPractices: List[Dict[str, Any]] = Field(default_factory=list, description="个性化练习")
    summaryData: Optional[Dict[str, Any]] = Field(None, description="综合诊断总结")
    parentSummary: Optional[str] = Field(None, description="给家长的总结")
    
    # Additional fields for template compatibility
    overall_comment: Optional[str] = Field(None, description="综合评价")
    strengths: List[str] = Field(default_factory=list, description="主要优点")
    improvements: List[str] = Field(default_factory=list, description="改进建议")
    
    # Internal field to preserve original detailed grading data
    original_grading_result: Optional[Dict[str, Any]] = Field(None, description="原始详细评分数据，用于保留维度示例等信息")


class StandardDTO(BaseModel):
    """评分标准数据传输对象"""
    model_config = ConfigDict(from_attributes=True)
    
    title: str
    total_score: int
    grade: str
    genre: Optional[str] = None
    dimensions: List[Dict[str, Any]] = Field(default_factory=list, description="评分维度详情")


def to_context(evaluation: EvaluationResult, doc_template=None) -> Dict[str, Any]:
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
    
    # P2: Add fields for future enhancements
    context.setdefault('paragraphs', [])
    context.setdefault('exercises', [])
    context.setdefault('feedback_summary', '')
    
    # Ensure scores has required structure
    if 'scores' in context:
        context['scores'].setdefault('total', 0.0)
        context['scores'].setdefault('rubrics', [])
    
    # Map teacher-view aligned fields for export compatibility
    # These fields should be populated when creating EvaluationResult for export
    if not context.get('assignmentTitle'):
        context['assignmentTitle'] = meta.get('topic', '未知作业')
    if not context.get('studentName'):
        context['studentName'] = meta.get('student', '未知学生')
    if not context.get('submittedAt'):
        context['submittedAt'] = meta.get('date', '未知时间')
    if not context.get('currentEssayContent'):
        # Try to get from text field if available
        text_block = context.get('text')
        if text_block:
            context['currentEssayContent'] = text_block.get('cleaned') or text_block.get('original', '')
        else:
            context['currentEssayContent'] = ''
    
    # Transform scoring data to match teacher view structure  
    grading_result = {
        'total_score': context.get('scores', {}).get('total', 0),
        'dimensions': [],
        'strengths': context.get('strengths', []),
        'improvements': context.get('improvements', []),
        'overall_comment': context.get('overall_comment', '')
    }
    
    # Map rubrics to dimensions format expected by teacher view
    rubrics = context.get('scores', {}).get('rubrics', [])
    
    # Get original grading result if available for dimension examples
    original_grading_result = getattr(evaluation, 'original_grading_result', {})
    original_dimensions = original_grading_result.get('dimensions', []) if original_grading_result else []
    
    for i, rubric in enumerate(rubrics):
        dimension = {
            'dimension_name': rubric.get('name', ''),
            'score': rubric.get('score', 0),
            'selected_rubric_level': rubric.get('level', ''),
            'feedback': rubric.get('reason', ''),
            'example_good_sentence': [],
            'example_improvement_suggestion': []
        }
        
        # Check if the rubric already has example data (from properly populated RubricScore)
        if hasattr(rubric, 'example_good_sentence') and getattr(rubric, 'example_good_sentence'):
            dimension['example_good_sentence'] = getattr(rubric, 'example_good_sentence')
        elif rubric.get('example_good_sentence'):
            dimension['example_good_sentence'] = rubric.get('example_good_sentence')
            
        if hasattr(rubric, 'example_improvement_suggestion') and getattr(rubric, 'example_improvement_suggestion'):
            dimension['example_improvement_suggestion'] = getattr(rubric, 'example_improvement_suggestion')
        elif rubric.get('example_improvement_suggestion'):
            dimension['example_improvement_suggestion'] = rubric.get('example_improvement_suggestion')

        # Find matching dimension from original data to get examples if not already set
        if not dimension['example_good_sentence'] or not dimension['example_improvement_suggestion']:
            matching_original = None
            for orig_dim in original_dimensions:
                if orig_dim.get('dimension_name') == rubric.get('name'):
                    matching_original = orig_dim
                    break
            
            if matching_original:
                # Populate example_good_sentence if not already set
                if not dimension['example_good_sentence']:
                    good_sentence = matching_original.get('example_good_sentence', '')
                    if good_sentence and good_sentence.strip():
                        dimension['example_good_sentence'] = [good_sentence.strip()]
                
                # Populate example_improvement_suggestion if not already set
                if not dimension['example_improvement_suggestion']:
                    improvement_suggestion = matching_original.get('example_improvement_suggestion', {})
                    if improvement_suggestion and isinstance(improvement_suggestion, dict):
                        original_text = improvement_suggestion.get('original', '')
                        suggested_text = improvement_suggestion.get('suggested', '')
                        if original_text and suggested_text:
                            dimension['example_improvement_suggestion'] = [{
                                'original': original_text.strip(),
                                'suggested': suggested_text.strip()
                            }]
        
        grading_result['dimensions'].append(dimension)
    
    context['gradingResult'] = grading_result
    
    # Map AI enhanced content for export
    context.setdefault('outline', context.get('outline', []))
    context.setdefault('diagnoses', context.get('diagnoses', []))
    context.setdefault('personalizedPractices', context.get('personalizedPractices', []))
    context.setdefault('summaryData', context.get('summaryData'))
    context.setdefault('parentSummary', context.get('parentSummary'))
    
    # Map legacy analysis data if new format is empty
    if not context['outline'] and context.get('analysis') and context['analysis']:
        outline_items = context['analysis'].get('outline', [])
        context['outline'] = [{'index': item.get('para', 0), 'intention': item.get('intent', '')} 
                             for item in outline_items]
    
    if not context['diagnoses'] and context.get('diagnostics'):
        context['diagnoses'] = []
        for i, diag in enumerate(context['diagnostics']):
            diagnosis = {
                'id': i + 1,
                'target': f"第{diag.get('para', 0)}段" if diag.get('para') else "全文",
                'evidence': diag.get('evidence', ''),
                'suggestions': diag.get('advice', [])
            }
            context['diagnoses'].append(diagnosis)
    
    if not context['personalizedPractices'] and context.get('exercises'):
        context['personalizedPractices'] = [
            {
                'title': ex.get('type', ''),
                'requirement': ex.get('prompt', '')
            } for ex in context['exercises']
        ]
    
    # Don't create automatic fallback summary data - let empty modules be hidden
    # if not context['summaryData']:
    #     context['summaryData'] = {
    #         'problemSummary': '本次作文分析发现的主要问题...',
    #         'improvementPlan': '建议从以下方面进行改进...',
    #         'expectedOutcome': '通过有针对性的练习，预期能够...'
    #     }
    
    # Don't create automatic fallback parent summary - let empty modules be hidden  
    # if not context['parentSummary']:
    #     context['parentSummary'] = context.get('summary', '总体而言，该作文具有一定的优点，同时也存在一些需要改进的地方。')
    
    # Add images context with actual essay image data if available
    images_context = {
        'original_image': None,
        'original_image_path': None, 
        'composited_image': None,
        'composited_image_path': None,
        'friendly_message': None  # Will be set if needed
    }
    
    # If essay instance is available, populate image context from essay database fields
    if hasattr(evaluation, '_essay_instance') and evaluation._essay_instance:
        essay = evaluation._essay_instance
        if essay.original_image_path:
            images_context['original_image_path'] = essay.original_image_path
        if essay.annotated_overlay_path:
            images_context['composited_image_path'] = essay.annotated_overlay_path
            
        # Try to create InlineImage objects for docxtpl rendering if paths exist
        if essay.original_image_path or essay.annotated_overlay_path:
            _populate_image_context(images_context, essay, doc_template)
    
    context.setdefault('images', images_context)
    
    return context


def _populate_image_context(images_context: Dict[str, Any], essay, doc_template=None) -> None:
    """
    Populate image context with resolved paths and InlineImage objects for docxtpl rendering.
    
    Handles path resolution and creates InlineImage objects when a DocxTemplate is provided.
    
    Args:
        images_context: Dictionary to populate with image data
        essay: Essay instance with image paths
        doc_template: DocxTemplate instance for creating InlineImage objects (optional)
    """
    import logging
    import os
    from app.utils.path_resolver import resolve_upload_path, get_friendly_image_message
    
    logger = logging.getLogger(__name__)
    
    original_path = essay.original_image_path
    overlay_path = essay.annotated_overlay_path
    
    # Enhanced logging as requested in problem statement
    logger.info(f"Image context population started - Original: {original_path}, Overlay: {overlay_path}")
    
    # Log what we're trying to resolve
    if original_path:
        logger.info(f"Attempting to resolve original image path: {original_path}")
        logger.debug(f"Original image path details - exists: {os.path.exists(original_path) if original_path else False}, type: {type(original_path)}")
    if overlay_path:
        logger.info(f"Attempting to resolve overlay image path: {overlay_path}")
        logger.debug(f"Overlay image path details - exists: {os.path.exists(overlay_path) if overlay_path else False}, type: {type(overlay_path)}")
    
    # Try to resolve paths
    resolved_original = resolve_upload_path(original_path) if original_path else None
    resolved_overlay = resolve_upload_path(overlay_path) if overlay_path else None
    
    # Enhanced logging for resolution results
    if original_path:
        if resolved_original:
            logger.info(f"✅ Successfully resolved original image path: {original_path} -> {resolved_original}")
            logger.debug(f"Resolved original image file size: {os.path.getsize(resolved_original)} bytes")
        else:
            logger.warning(f"❌ Failed to resolve original image path: {original_path}")
            logger.debug(f"Resolution failure details - path exists: {os.path.exists(original_path) if original_path else False}")
    
    if overlay_path:
        if resolved_overlay:
            logger.info(f"✅ Successfully resolved overlay image path: {overlay_path} -> {resolved_overlay}")
            logger.debug(f"Resolved overlay image file size: {os.path.getsize(resolved_overlay)} bytes")
        else:
            logger.warning(f"❌ Failed to resolve overlay image path: {overlay_path}")
            logger.debug(f"Resolution failure details - path exists: {os.path.exists(overlay_path) if overlay_path else False}")
    
    # Store resolved paths for fallback scenarios
    if resolved_original:
        images_context['original_image_path'] = resolved_original
    
    if resolved_overlay:
        images_context['composited_image_path'] = resolved_overlay
    
    # Priority: use overlay (composed) image if available, otherwise original
    primary_image_path = resolved_overlay or resolved_original
    
    if primary_image_path:
        images_context['primary_image_path'] = primary_image_path
        logger.info(f"✅ Primary image path set to: {primary_image_path}")
        
        # If we have a DocxTemplate, create InlineImage objects
        if doc_template:
            logger.debug(f"DocxTemplate provided, creating InlineImage objects")
            try:
                from docxtpl import InlineImage
                from docx.shared import Inches
                
                # Create InlineImage for the primary image
                images_context['primary_image'] = InlineImage(doc_template, primary_image_path, width=Inches(6))
                logger.info(f"✅ Successfully created primary InlineImage for: {primary_image_path}")
                
                # Also create separate images if we have both original and overlay
                if resolved_original and resolved_overlay:
                    images_context['original_image'] = InlineImage(doc_template, resolved_original, width=Inches(6))
                    images_context['composited_image'] = InlineImage(doc_template, resolved_overlay, width=Inches(6))
                    logger.info(f"✅ Created separate original and composited InlineImages")
                elif resolved_original:
                    images_context['original_image'] = images_context['primary_image']
                    logger.debug(f"Using primary image as original image")
                elif resolved_overlay:
                    images_context['composited_image'] = images_context['primary_image']
                    logger.debug(f"Using primary image as composited image")
                    
            except Exception as e:
                logger.error(f"❌ Failed to create InlineImage objects: {e}")
                logger.debug(f"InlineImage creation failure details", exc_info=True)
                images_context['friendly_message'] = get_friendly_image_message()
        else:
            logger.debug(f"No DocxTemplate provided, skipping InlineImage creation")
    else:
        # No images could be resolved
        if original_path or overlay_path:
            logger.warning(f"❌ No images could be resolved. Original: {original_path}, Overlay: {overlay_path}")
            images_context['friendly_message'] = get_friendly_image_message()
        else:
            logger.debug(f"No image paths provided, skipping image processing")
    
    # Final status logging
    logger.info(f"Image context population completed. Available keys: {list(images_context.keys())}")
    logger.debug(f"Image context contents: {images_context}")