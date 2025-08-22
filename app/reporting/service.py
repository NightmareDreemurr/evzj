"""
Service layer for batch DOCX reporting.

This module provides business logic for building ViewModels and rendering
batch DOCX reports for assignments.
"""
import io
import tempfile
import logging
from typing import List, Optional, Literal, Union
from pathlib import Path

import zipstream
from app.extensions import db
from app.models import (
    EssayAssignment, Classroom, TeacherProfile, StudentProfile, 
    Essay, Enrollment
)
from app.dao.evaluation_dao import load_evaluation_by_essay
from app.reporting.viewmodels import (
    StudentReportVM, AssignmentReportVM, ScoreVM,
    map_scores_to_vm, safe_get_student_name, safe_get_topic,
    safe_get_feedback, safe_get_original_paragraphs
)
from app.reporting.docx_renderer import render_essay_docx

logger = logging.getLogger(__name__)


def build_student_vm(essay_id: int) -> Optional[StudentReportVM]:
    """
    Build StudentReportVM from essay evaluation data.
    
    Args:
        essay_id: Essay ID
        
    Returns:
        StudentReportVM instance or None if not found
    """
    try:
        # Load evaluation result
        evaluation = load_evaluation_by_essay(essay_id)
        if not evaluation:
            logger.warning(f"No evaluation found for essay {essay_id}")
            return None
        
        # Get essay for additional context
        essay = db.session.get(Essay, essay_id)
        if not essay:
            logger.warning(f"Essay {essay_id} not found")
            return None
        
        # Extract student information
        student_id = 0
        student_name = safe_get_student_name(evaluation)
        student_no = None
        
        if essay.enrollment and essay.enrollment.student:
            student_profile = essay.enrollment.student
            student_id = student_profile.id
            if student_profile.user:
                student_name = student_profile.user.full_name or student_profile.user.username
            # Get student number from enrollment
            student_no = essay.enrollment.student_number
        
        # Extract other information
        topic = safe_get_topic(evaluation)
        words = getattr(evaluation.meta, 'words', None) if hasattr(evaluation, 'meta') else None
        scores = map_scores_to_vm(evaluation)
        feedback = safe_get_feedback(evaluation)
        original_paragraphs = safe_get_original_paragraphs(evaluation)
        
        return StudentReportVM(
            student_id=student_id,
            student_name=student_name,
            student_no=student_no,
            essay_id=essay_id,
            topic=topic,
            words=words,
            scores=scores,
            feedback=feedback,
            original_paragraphs=original_paragraphs
        )
        
    except Exception as e:
        logger.error(f"Failed to build student VM for essay {essay_id}: {e}")
        return None


def build_assignment_vm(assignment_id: int) -> Optional[AssignmentReportVM]:
    """
    Build AssignmentReportVM with all student data.
    
    Args:
        assignment_id: Assignment ID
        
    Returns:
        AssignmentReportVM instance or None if not found
    """
    try:
        # Get assignment with related data in single query to avoid N+1
        assignment = db.session.query(EssayAssignment)\
            .filter(EssayAssignment.id == assignment_id)\
            .first()
        
        if not assignment:
            logger.warning(f"Assignment {assignment_id} not found")
            return None
        
        # Get classroom and teacher info
        classroom_info = {"name": "未知班级", "id": None}
        teacher_info = {"name": "未知教师", "id": None}
        
        if assignment.teacher:
            teacher_profile = assignment.teacher
            if teacher_profile.user:
                teacher_info = {
                    "name": teacher_profile.user.full_name or teacher_profile.user.username,
                    "id": teacher_profile.id
                }
            
            # Get primary classroom (first classroom if multiple)
            if teacher_profile.classrooms:
                classroom = teacher_profile.classrooms[0]
                classroom_info = {
                    "name": classroom.class_name,
                    "id": classroom.id
                }
        
        # Get all essays for this assignment
        essays = db.session.query(Essay)\
            .filter(Essay.assignment_id == assignment_id)\
            .all()
        
        logger.info(f"Found {len(essays)} essays for assignment {assignment_id}")
        
        # Build student VMs
        students = []
        for essay in essays:
            student_vm = build_student_vm(essay.id)
            if student_vm:
                students.append(student_vm)
        
        logger.info(f"Built {len(students)} student VMs for assignment {assignment_id}")
        
        return AssignmentReportVM(
            assignment_id=assignment_id,
            title=assignment.title,
            classroom=classroom_info,
            teacher=teacher_info,
            students=students
        )
        
    except Exception as e:
        logger.error(f"Failed to build assignment VM for assignment {assignment_id}: {e}")
        return None


def render_student_docx(essay_id: int) -> bytes:
    """
    Render single student DOCX report.
    
    Args:
        essay_id: Essay ID
        
    Returns:
        DOCX file content as bytes
    """
    from app.dao.evaluation_dao import load_evaluation_by_essay
    
    evaluation = load_evaluation_by_essay(essay_id)
    if not evaluation:
        raise ValueError(f"No evaluation found for essay {essay_id}")
    
    # Use existing renderer
    output_path = render_essay_docx(evaluation)
    
    # Read file and return bytes
    with open(output_path, 'rb') as f:
        return f.read()


def render_assignment_docx(assignment_id: int, mode: Literal["combined", "zip"] = "combined") -> Union[bytes, zipstream.ZipStream]:
    """
    Render assignment batch DOCX report.
    
    Args:
        assignment_id: Assignment ID
        mode: "combined" for single merged DOCX, "zip" for ZIP of individual files
        
    Returns:
        Bytes for combined mode, ZipFile for zip mode
    """
    assignment_vm = build_assignment_vm(assignment_id)
    if not assignment_vm:
        raise ValueError(f"No data found for assignment {assignment_id}")
    
    if not assignment_vm.students:
        raise ValueError(f"No student data found for assignment {assignment_id}")
    
    if mode == "zip":
        return _render_assignment_zip(assignment_vm)
    else:
        return _render_assignment_combined(assignment_vm)


def _render_assignment_combined(assignment_vm: AssignmentReportVM) -> bytes:
    """
    Render combined DOCX using docxtpl with subdocuments.
    
    Args:
        assignment_vm: Assignment data
        
    Returns:
        Combined DOCX as bytes
    """
    try:
        return _render_with_docxtpl_combined(assignment_vm)
    except Exception as e:
        logger.warning(f"docxtpl rendering failed: {e}, falling back to docxcompose")
        return _render_with_docxcompose(assignment_vm)


def _render_with_docxtpl_combined(assignment_vm: AssignmentReportVM) -> bytes:
    """Render using docxtpl with subdocuments."""
    from docxtpl import DocxTemplate
    from app.reporting.docx_renderer import ensure_template_exists
    
    # For now, use existing template and render as single document
    # TODO: Implement proper assignment template with subdocuments
    template_path = ensure_template_exists()
    
    # Create a combined context with all student data
    combined_context = {
        'assignment': {
            'title': assignment_vm.title,
            'classroom': assignment_vm.classroom,
            'teacher': assignment_vm.teacher
        },
        'students': []
    }
    
    # Add student contexts
    for student in assignment_vm.students:
        from app.dao.evaluation_dao import load_evaluation_by_essay
        evaluation = load_evaluation_by_essay(student.essay_id)
        if evaluation:
            from app.schemas.evaluation import to_context
            student_context = to_context(evaluation)
            student_context['student_name'] = student.student_name
            combined_context['students'].append(student_context)
    
    # Render template
    doc = DocxTemplate(template_path)
    
    # For now, render first student as representative
    if combined_context['students']:
        context = combined_context['students'][0]
        doc.render(context)
    
    # Save to bytes
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def _render_with_docxcompose(assignment_vm: AssignmentReportVM) -> bytes:
    """Render using docxcompose to combine individual documents."""
    from docx import Document
    from docxcompose.composer import Composer
    
    # Generate individual documents
    temp_files = []
    try:
        for i, student in enumerate(assignment_vm.students):
            student_bytes = render_student_docx(student.essay_id)
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
            temp_file.write(student_bytes)
            temp_file.close()
            temp_files.append(temp_file.name)
        
        if not temp_files:
            raise ValueError("No documents to combine")
        
        # Compose documents
        master = Document(temp_files[0])
        composer = Composer(master)
        
        for path in temp_files[1:]:
            composer.append(Document(path))
        
        # Save to bytes
        output = io.BytesIO()
        master.save(output)
        return output.getvalue()
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                Path(temp_file).unlink()
            except:
                pass


def _render_assignment_zip(assignment_vm: AssignmentReportVM) -> zipstream.ZipStream:
    """
    Render assignment as ZIP of individual DOCX files.
    
    Args:
        assignment_vm: Assignment data
        
    Returns:
        ZipStream generator
    """
    z = zipstream.ZipStream(mode='w', compression=zipstream.ZIP_DEFLATED)
    
    for student in assignment_vm.students:
        try:
            student_bytes = render_student_docx(student.essay_id)
            filename = f"{student.student_name}_{student.topic}_{student.essay_id}.docx"
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in "._-")
            z.writestr(filename, student_bytes)
        except Exception as e:
            logger.error(f"Failed to render student {student.student_name}: {e}")
            continue
    
    return z