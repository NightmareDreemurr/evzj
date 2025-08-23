"""
DOCX rendering module for evaluation reports.
"""
import os
import tempfile
import logging
from typing import Dict, Any
from pathlib import Path

try:
    from docxtpl import DocxTemplate
    DOCXTPL_AVAILABLE = True
except ImportError:
    DOCXTPL_AVAILABLE = False

from docx import Document
from docx.shared import Inches

from app.schemas.evaluation import EvaluationResult, to_context

logger = logging.getLogger(__name__)


def ensure_template_exists(template_path: str = None) -> str:
    """
    Ensure the DOCX template exists, creating a minimal one if necessary.
    
    Args:
        template_path: Path to template, defaults to templates/word/ReportTemplate.docx
        
    Returns:
        Path to the template file
    """
    if template_path is None:
        # Use project root templates directory
        project_root = Path(__file__).parent.parent.parent
        template_dir = project_root / "templates" / "word"
        template_dir.mkdir(parents=True, exist_ok=True)
        template_path = str(template_dir / "ReportTemplate.docx")
    
    if os.path.exists(template_path):
        logger.info(f"Using existing template: {template_path}")
        return template_path
    
    # Create minimal template
    logger.info(f"Creating minimal template at: {template_path}")
    _create_minimal_template(template_path)
    return template_path


def _create_minimal_template(template_path: str):
    """Create a minimal DOCX template for reports"""
    doc = Document()
    
    # Title
    title = doc.add_heading('{{ meta.topic }} 作文评估报告', 0)
    title.alignment = 1  # Center
    
    # Basic info
    doc.add_heading('基本信息', level=1)
    info_para = doc.add_paragraph()
    info_para.add_run('学生：').bold = True
    info_para.add_run('{{ meta.student }}\n')
    info_para.add_run('班级：').bold = True  
    info_para.add_run('{{ meta.class_ }}\n')
    info_para.add_run('教师：').bold = True
    info_para.add_run('{{ meta.teacher }}\n')
    info_para.add_run('日期：').bold = True
    info_para.add_run('{{ meta.date }}')
    
    # Total score
    doc.add_heading('评分结果', level=1)
    score_para = doc.add_paragraph()
    score_para.add_run('总分：').bold = True
    score_para.add_run('{{ scores.total }}')
    
    # Rubrics
    if DOCXTPL_AVAILABLE:
        doc.add_paragraph('{% for r in scores.rubrics %}{{ r.name }}: {{ r.score }}/{{ r.max }} (权重{{ r.weight }}) - {{ r.reason }}{% endfor %}')
    else:
        doc.add_paragraph('[各维度评分详情]')
    
    # Original text
    doc.add_heading('原文', level=1)
    if DOCXTPL_AVAILABLE:
        doc.add_paragraph('{{ text.original or "" }}')
    else:
        doc.add_paragraph('[原文内容]')
    
    # Cleaned text  
    doc.add_heading('清洗后文本', level=1)
    if DOCXTPL_AVAILABLE:
        doc.add_paragraph('{{ text.cleaned or "" }}')
    else:
        doc.add_paragraph('[清洗后文本内容]')
    
    # Highlights summary
    doc.add_heading('高亮摘要', level=1)
    if DOCXTPL_AVAILABLE:
        doc.add_paragraph("""
{% for type, data in highlight_summary.items() %}
{{ type }}: 低{{ data.low }}个, 中{{ data.medium }}个, 高{{ data.high }}个
示例: {{ data.examples|join(', ') }}
{% endfor %}
        """.strip())
    else:
        doc.add_paragraph('[高亮摘要]')
    
    # Diagnosis
    doc.add_heading('诊断建议', level=1)
    if DOCXTPL_AVAILABLE:
        doc.add_paragraph('{{ diagnosis.before or "" }}')
        doc.add_paragraph('{{ diagnosis.comment or "" }}')
        doc.add_paragraph('{{ diagnosis.after or "" }}')
    else:
        doc.add_paragraph('[诊断建议]')
    
    # Footer
    doc.add_paragraph().add_run('\n' + '='*50)
    footer = doc.add_paragraph()
    footer.add_run('报告生成时间: ').bold = True
    if DOCXTPL_AVAILABLE:
        footer.add_run('{{ now|strftime("%Y-%m-%d %H:%M:%S") }}')
    else:
        footer.add_run('[生成时间]')
    footer.alignment = 1  # Center
    
    doc.save(template_path)
    logger.info(f"Created minimal template: {template_path}")


def render_essay_docx(evaluation: EvaluationResult, output_path: str = None, review_status: str = None) -> str:
    """
    Render a single essay evaluation to DOCX.
    
    Args:
        evaluation: EvaluationResult instance
        output_path: Output file path, auto-generated if None
        review_status: Review status for display (ai_generated, teacher_reviewed, finalized)
        
    Returns:
        Path to generated DOCX file
    """
    if output_path is None:
        # Generate filename from student name and topic
        student = evaluation.meta.student.replace(' ', '_').replace('/', '_')
        topic = str(evaluation.meta.topic).replace(' ', '_').replace('/', '_')
        date_str = str(evaluation.meta.date).replace('-', '').replace('/', '')
        filename = f"{student}_{topic}_{date_str}.docx"
        
        # Use temp directory
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, filename)
    
    if DOCXTPL_AVAILABLE:
        return _render_with_docxtpl(evaluation, output_path, review_status)
    else:
        return _render_with_python_docx(evaluation, output_path, review_status)


def render_assignment_docx(assignment_id: int, evaluations: list = None, output_path: str = None) -> str:
    """
    Render assignment summary DOCX.
    
    Args:
        assignment_id: Assignment ID
        evaluations: List of EvaluationResult instances
        output_path: Output file path
        
    Returns:
        Path to generated DOCX file
        
    Raises:
        FileNotFoundError: If assignment template is missing
        ValueError: If no evaluations available
    """
    # Check if assignment template exists
    project_root = Path(__file__).parent.parent.parent
    assignment_template_path = project_root / "templates" / "word" / "assignment_compiled.docx"
    
    if not assignment_template_path.exists():
        raise FileNotFoundError(
            f"Assignment template not found at {assignment_template_path}. "
            "Assignment summary export requires a dedicated template. "
            "Please create the template or use individual essay export instead."
        )
    
    if not evaluations or len(evaluations) == 0:
        raise ValueError(f"No evaluation data available for assignment {assignment_id}")
    
    logger.info(f"Rendering assignment summary for {len(evaluations)} evaluations")
    
    # For now, use the existing combined rendering logic if available
    # This is a placeholder for proper assignment template implementation
    try:
        return _render_assignment_combined(assignment_id, evaluations, output_path)
    except NotImplementedError:
        # If combined rendering is not implemented, provide clear guidance
        raise NotImplementedError(
            f"Assignment summary rendering not yet fully implemented. "
            f"Available options: 1) Create individual essay reports, "
            f"2) Implement _render_assignment_combined function, "
            f"3) Add assignment template at {assignment_template_path}"
        )


def _render_assignment_combined(assignment_id: int, evaluations: list, output_path: str = None) -> str:
    """
    Render combined assignment DOCX using assignment template.
    
    This is a placeholder implementation - should be enhanced based on actual requirements.
    """
    raise NotImplementedError("Combined assignment rendering not yet implemented")


def _render_with_docxtpl(evaluation: EvaluationResult, output_path: str, review_status: str = None) -> str:
    """Render using docxtpl (template-based)"""
    template_path = ensure_template_exists()
    
    try:
        doc = DocxTemplate(template_path)
        context = to_context(evaluation)
        
        # Add current timestamp and enhance context
        from datetime import datetime
        context['now'] = datetime.now()
        context['current_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add review status information
        context['review_status'] = review_status or 'ai_generated'
        context['is_reviewed'] = review_status in ['teacher_reviewed', 'finalized'] if review_status else False
        context['needs_review_warning'] = review_status not in ['teacher_reviewed', 'finalized'] if review_status else True
        
        # Add fields for future enhancements (P2)
        context.setdefault('paragraphs', [])
        context.setdefault('exercises', [])
        context.setdefault('feedback_summary', '')
        
        # Create Jinja environment with strftime filter (P0)
        from jinja2 import Environment
        env = Environment(autoescape=False)
        
        def strftime_filter(dt, fmt):
            """Custom strftime filter that handles both datetime objects and strings"""
            if dt is None:
                return ''
            if isinstance(dt, str):
                return dt  # If already a string, return as-is
            if hasattr(dt, 'strftime'):
                return dt.strftime(fmt)
            return str(dt)
        
        env.filters['strftime'] = strftime_filter
        
        # Render with custom jinja environment
        doc.render(context, jinja_env=env)
        doc.save(output_path)
        
        logger.info(f"Rendered DOCX using docxtpl: {output_path}")
        return output_path
        
    except FileNotFoundError as e:
        logger.info(f"Template file not found, falling back to python-docx: {e}")
        return _render_with_python_docx(evaluation, output_path)
    except Exception as e:
        # P1: Don't fallback on template syntax errors - raise them clearly
        logger.error(f"Failed to render with docxtpl due to template error: {e}")
        raise RuntimeError(f"DOCX template rendering failed: {e}") from e


def _render_with_python_docx(evaluation: EvaluationResult, output_path: str, review_status: str = None) -> str:
    """Render using python-docx (direct generation)"""
    doc = Document()
    
    # Title
    title = doc.add_heading(f'{evaluation.meta.topic} 作文评估报告', 0)
    title.alignment = 1  # Center
    
    # Add review status warning if needed
    if review_status and review_status != 'teacher_reviewed' and review_status != 'finalized':
        warning = doc.add_paragraph()
        warning.add_run('⚠️ 注意：此报告内容为AI生成，尚未经过教师审核确认').bold = True
        warning.style = 'Intense Quote'
    
    # Basic information
    doc.add_heading('基本信息', level=1)
    basic_info = doc.add_paragraph()
    basic_info.add_run('学生：').bold = True
    basic_info.add_run(f'{evaluation.meta.student}\n')
    basic_info.add_run('班级：').bold = True
    basic_info.add_run(f'{evaluation.meta.class_}\n')
    basic_info.add_run('教师：').bold = True
    basic_info.add_run(f'{evaluation.meta.teacher}\n')
    basic_info.add_run('日期：').bold = True
    basic_info.add_run(f'{evaluation.meta.date}')
    
    # Scores
    doc.add_heading('评分结果', level=1)
    scores_para = doc.add_paragraph()
    scores_para.add_run('总分：').bold = True
    scores_para.add_run(f'{evaluation.scores.total}分\n')
    
    # Rubrics detail
    if evaluation.scores.rubrics:
        doc.add_heading('各维度评分', level=2)
        for rubric in evaluation.scores.rubrics:
            rubric_para = doc.add_paragraph()
            rubric_para.add_run(f'{rubric.name}：').bold = True
            rubric_para.add_run(f'{rubric.score}/{rubric.max}分 (权重{rubric.weight})\n')
            if rubric.reason:
                rubric_para.add_run(f'理由：{rubric.reason}')
    
    # Original text
    if evaluation.text:
        doc.add_heading('原文', level=1)
        doc.add_paragraph(evaluation.text.original or '无原文内容')
        
        # Cleaned text
        if evaluation.text.cleaned and evaluation.text.cleaned != evaluation.text.original:
            doc.add_heading('清洗后文本', level=1)
            doc.add_paragraph(evaluation.text.cleaned)
    
    # Highlights summary
    if evaluation.highlights:
        doc.add_heading('高亮摘要', level=1)
        context = to_context(evaluation)
        if 'highlight_summary' in context:
            for highlight_type, data in context['highlight_summary'].items():
                highlight_para = doc.add_paragraph()
                highlight_para.add_run(f'{highlight_type}：').bold = True
                highlight_para.add_run(f'低{data["low"]}个, 中{data["medium"]}个, 高{data["high"]}个\n')
                if data.get('examples'):
                    highlight_para.add_run('示例：').bold = True
                    highlight_para.add_run(', '.join(data['examples']))
    
    # Diagnosis
    if evaluation.diagnosis:
        doc.add_heading('诊断建议', level=1)
        if evaluation.diagnosis.before:
            doc.add_paragraph(evaluation.diagnosis.before)
        if evaluation.diagnosis.comment:
            doc.add_paragraph(evaluation.diagnosis.comment)
        if evaluation.diagnosis.after:
            doc.add_paragraph(evaluation.diagnosis.after)
    
    # Legacy diagnostics for backward compatibility
    if evaluation.diagnostics:
        doc.add_heading('诊断详情', level=1)
        for diag in evaluation.diagnostics:
            diag_para = doc.add_paragraph()
            para_info = f"第{diag.para}段" if diag.para else "全文"
            diag_para.add_run(f'{para_info} - {diag.issue}：').bold = True
            diag_para.add_run(f'{diag.evidence}\n')
            if diag.advice:
                diag_para.add_run('建议：').bold = True
                diag_para.add_run(', '.join(diag.advice))
    
    # Footer
    doc.add_paragraph().add_run('\n' + '='*50)
    footer = doc.add_paragraph()
    footer.add_run('报告生成时间：').bold = True
    from datetime import datetime
    footer.add_run(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    footer.alignment = 1  # Center
    
    doc.save(output_path)
    logger.info(f"Rendered DOCX using python-docx: {output_path}")
    return output_path