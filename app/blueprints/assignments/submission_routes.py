import os
import uuid
import threading
import json
from concurrent.futures import ThreadPoolExecutor

from flask import (render_template, request, flash, redirect, url_for, 
                   current_app, jsonify)
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.dialects import sqlite
from werkzeug.utils import secure_filename
from dictdiffer import patch

from app.extensions import db
from app.models import (EssayAssignment, StudentProfile, Enrollment, Essay, 
                        PendingSubmission, GradingStandard, Dimension, Rubric)
from app.services.ai_grader import grade_essay_with_ai
from app.services.ocr_service import process_submissions_for_assignment
from app.services.ai_corrector import correct_essay_with_ai
from app.services.ai_matcher import match_students_for_assignment

from . import assignments_bp
from .forms import BatchConfirmationForm

from PIL import Image
from io import BytesIO
import base64


@assignments_bp.route('/<int:assignment_id>/submissions')
@login_required
def submissions(assignment_id):
    assignment = EssayAssignment.query.get_or_404(assignment_id)
    sort_by = request.args.get('sort_by', 'name_asc') # Default sort

    # Permission check
    if current_user.role == 'teacher':
        if not hasattr(current_user, 'teacher_profile') or assignment.teacher_profile_id != current_user.teacher_profile.id:
            flash("您没有权限查看此作业的提交情况。", "danger")
            return redirect(url_for('assignments.list_assignments'))

    # 1. Get all students who were assigned this essay
    assigned_students = set(assignment.students)
    assigned_classroom_ids = {c.id for c in assignment.classrooms}
    for classroom in assignment.classrooms:
        for enrollment in classroom.enrollments:
            if enrollment.status == 'active':
                assigned_students.add(enrollment.student)

    # 2. Group all submissions and enrollments by student profile id
    submissions_by_student = {}
    enrollments_by_student = {}
    essays_in_processing = set()
    processing_statuses = ['pending', 'correcting', 'grading']

    # Pre-fetch enrollments for all assigned students in the relevant classrooms
    all_enrollments = Enrollment.query.filter(
        Enrollment.student_profile_id.in_([s.id for s in assigned_students]),
        Enrollment.classroom_id.in_(assigned_classroom_ids)
    ).all()
    for enrollment in all_enrollments:
        enrollments_by_student[enrollment.student_profile_id] = enrollment

    for essay in assignment.essays:
        student_id = essay.enrollment.student_profile_id
        if student_id not in submissions_by_student:
            submissions_by_student[student_id] = []
        submissions_by_student[student_id].append(essay)
        if essay.status in processing_statuses:
            essays_in_processing.add(student_id)

    # 3. Create a list of submission statuses for the template
    submission_statuses = []
    summary_counts = {'submitted': 0, 'not_submitted': 0, 'processing': 0}

    for student_profile in assigned_students:
        student_submissions = submissions_by_student.get(student_profile.id, [])
        student_submissions.sort(key=lambda e: e.created_at, reverse=True)
        submission_count = len(student_submissions)

        latest_submission = student_submissions[0] if submission_count > 0 else None
        latest_score = None
        if latest_submission and latest_submission.status == 'graded' and latest_submission.ai_score:
            latest_score = latest_submission.ai_score.get('total_score')

        is_processing = student_profile.id in essays_in_processing
        status_key = 'not_submitted'
        if is_processing:
            status_key = 'processing'
            summary_counts['processing'] += 1
        elif submission_count > 0:
            status_key = 'submitted'
            summary_counts['submitted'] += 1
        else:
            summary_counts['not_submitted'] += 1
        
        enrollment = enrollments_by_student.get(student_profile.id)
        student_number = enrollment.student_number if enrollment else None

        submission_statuses.append({
            'student_name': student_profile.user.full_name,
            'student_id': student_profile.id,
            'student_number': student_number,
            'submissions': student_submissions,
            'submission_count': submission_count,
            'is_processing': is_processing,
            'status_key': status_key,
            'latest_score': latest_score,
            'latest_submitted_at': latest_submission.created_at if latest_submission else None
        })

    # 4. Sort the list based on query parameter
    sort_key, sort_order = sort_by.rsplit('_', 1)
    reverse = (sort_order == 'desc')
    
    def sort_func(item):
        val = item.get(sort_key)
        if val is None:
            return -1 if reverse else float('inf') # Push None to the end
        if isinstance(val, str):
            return val.lower() # Case-insensitive sort for strings
        return val

    submission_statuses.sort(key=sort_func, reverse=reverse)
    
    # For pinyin sorting, we would need a library like pypinyin, doing a simple sort for now.
    if sort_key == 'name':
       submission_statuses.sort(key=lambda x: x['student_name'], reverse=reverse)


    return render_template(
        'assignments/submissions.html',
        assignment=assignment,
        submissions=submission_statuses,
        sort_by=sort_by,
        summary_counts_json=json.dumps(summary_counts)
    )

@assignments_bp.route('/<int:assignment_id>/batch_upload', methods=['POST'])
@login_required
def batch_upload_submissions(assignment_id):
    """
    Handles batch uploading of submission images by a teacher.
    """
    if not hasattr(current_user, 'teacher_profile'):
        flash('只有教师才能批量上传作业。', 'danger')
        return redirect(url_for('main.index'))

    assignment = EssayAssignment.query.get_or_404(assignment_id)
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        flash('您没有权限为该作业上传图片。', 'danger')
        return redirect(url_for('assignments.list_assignments'))

    uploaded_files = request.files.getlist('submission_images')
    if not uploaded_files or uploaded_files[0].filename == '':
        flash('没有选择任何文件。', 'warning')
        return redirect(url_for('assignments.assignment_detail', assignment_id=assignment_id))

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    
    pending_submissions = []
    for image_file in uploaded_files:
        if image_file: # and allowed_file(image_file.filename)
            original_filename = secure_filename(image_file.filename)
            # Create a unique filename to prevent overwrites
            unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
            file_path = os.path.join(upload_folder, unique_filename)
            image_file.save(file_path)

            pending_sub = PendingSubmission(
                assignment_id=assignment.id,
                uploader_id=current_user.teacher_profile.id,
                original_filename=original_filename,
                file_path=file_path,
                status='uploaded'
            )
            pending_submissions.append(pending_sub)

    if pending_submissions:
        db.session.add_all(pending_submissions)
        db.session.commit()
        
        app = current_app._get_current_object()
        # Start background processing in a new thread
        def background_task(app, assignment_id_to_process):
            with app.app_context():
                try:
                    current_app.logger.info(f"Background OCR/Match task started for assignment {assignment_id_to_process}")
                    # Step 1: OCR Processing
                    process_submissions_for_assignment(assignment_id_to_process)
                    # Step 2: AI Matching
                    match_students_for_assignment(assignment_id_to_process)
                    current_app.logger.info(f"Background OCR/Match task finished for assignment {assignment_id_to_process}")
                except Exception as e:
                    current_app.logger.error(f"Background task failed for assignment {assignment_id_to_process}: {e}", exc_info=True)
                finally:
                    # Crucial for returning the connection to the pool and ensuring data is visible across threads.
                    db.session.remove()

        thread = threading.Thread(target=background_task, args=(app, assignment.id))
        thread.start()

        flash(f'成功上传 {len(pending_submissions)} 张图片。系统正在后台自动识别和匹配，请稍后刷新查看结果。', 'success')
    
    # Redirect to the confirmation page (which we will build next)
    return redirect(url_for('assignments.confirm_submissions', assignment_id=assignment_id))


@assignments_bp.route('/<int:assignment_id>/confirm_submissions', methods=['GET', 'POST'])
@login_required
def confirm_submissions(assignment_id):
    """
    GET: Displays the page for a teacher to confirm/correct AI-matched submissions.
    POST: Processes the confirmed matches and creates final Essay submissions.
    """
    if not hasattr(current_user, 'teacher_profile'):
        flash('只有教师才能访问此页面。', 'danger')
        return redirect(url_for('main.index'))

    assignment = EssayAssignment.query.get_or_404(assignment_id)
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        flash('您没有权限访问此页面。', 'danger')
        return redirect(url_for('assignments.list_assignments'))

    form = BatchConfirmationForm()
    
    # POST request logic
    if form.validate_on_submit():
        newly_created_essays = []
        submissions_to_delete = []

        for key, student_profile_id in request.form.items():
            if key.startswith('submission_') and student_profile_id:
                try:
                    pending_submission_id = int(key.split('_')[1])
                    student_profile_id = int(student_profile_id)

                    pending_sub = db.session.get(PendingSubmission, pending_submission_id)
                    student_profile = db.session.get(StudentProfile, student_profile_id)

                    if not pending_sub or not student_profile:
                        continue
                    
                    # Find an active enrollment for the student in one of the assignment's classrooms
                    assigned_classroom_ids = [c.id for c in assignment.classrooms]
                    enrollment = Enrollment.query.filter(
                        Enrollment.student_profile_id == student_profile.id,
                        Enrollment.classroom_id.in_(assigned_classroom_ids),
                        Enrollment.status == 'active'
                    ).first()

                    if not enrollment:
                        flash(f'未能为学生 {student_profile.user.full_name} 找到有效的班级注册信息，跳过创建作业。', 'warning')
                        continue

                    # Create the final Essay object
                    new_essay = Essay(
                        enrollment_id=enrollment.id,
                        assignment_id=assignment.id,
                        content=pending_sub.ocr_text, # Placeholder, will be updated by AI corrector
                        original_ocr_text=pending_sub.ocr_text,
                        is_from_ocr=True,
                        original_image_path=pending_sub.file_path,
                        status='pending' # Initial status for our queue
                    )
                    db.session.add(new_essay)
                    newly_created_essays.append(new_essay)
                    submissions_to_delete.append(pending_sub)

                except (ValueError, IndexError) as e:
                    current_app.logger.warning(f"Could not parse form data for key {key}: {e}")
                    continue
        
        if newly_created_essays:
            db.session.flush() # Flush to get IDs for the new essays
            essay_ids = [e.id for e in newly_created_essays]

            # Clean up pending submissions from DB
            for sub in submissions_to_delete:
                db.session.delete(sub)
            
            db.session.commit()
            
            app = current_app._get_current_object()

            # --- Parallel AI Processing Task ---

            def _process_single_essay(essay_id_to_process, app):
                """
                Processes a single essay within its own app context.
                1. Corrects the text.
                2. Grades the essay.
                Each step is self-contained and handles its own DB transactions.
                """
                with app.app_context():
                    essay = None
                    try:
                        current_app.logger.info(f"Processing essay {essay_id_to_process} in a worker thread.")
                        
                        # Use a direct query to ensure we are working with the latest data
                        essay = db.session.query(Essay).filter_by(id=essay_id_to_process).with_for_update().first()
                        
                        if not essay:
                            current_app.logger.warning(f"Essay {essay_id_to_process} not found for processing.")
                            return

                        # Step 1: Correct text.
                        essay.status = 'correcting'
                        db.session.commit()
                        
                        correct_essay_with_ai(essay_id_to_process)
                        
                        # Refresh to see changes from the service, e.g., if it failed
                        db.session.refresh(essay)
                        if essay.status.startswith('error'):
                            current_app.logger.error(f"Failed to correct essay {essay_id_to_process}. Status: {essay.status}")
                            # Error status and message are already set by the service
                            return
                        
                        # Step 2: Grade essay.
                        # The service itself will set the status to 'grading' then 'graded' or 'error_*'
                        grade_essay_with_ai(essay_id_to_process)
                        
                        current_app.logger.info(f"Successfully finished processing essay {essay_id_to_process}.")

                    except Exception as e:
                        current_app.logger.error(f"An unexpected error occurred in the processing orchestrator for essay {essay_id_to_process}: {e}", exc_info=True)
                        if essay:
                            try:
                                # Final fallback error state
                                db.session.refresh(essay) # Get latest state before overwriting
                                essay.status = 'error_unknown'
                                essay.error_message = f"后台处理任务发生未知错误: {str(e)[:250]}"
                                db.session.commit()
                            except Exception as db_err:
                                current_app.logger.error(f"Failed to update essay status on error: {db_err}", exc_info=True)
                                db.session.rollback()
                    finally:
                        # Crucial for returning the connection to the pool in a threaded context
                        db.session.remove()


            def ai_processing_task(app, essay_ids_to_process):
                with app.app_context():
                    current_app.logger.info(f"Parallel AI processing task started for {len(essay_ids_to_process)} essays.")
                    
                    MAX_WORKERS = 50 # Adjust as needed
                    
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        # Pass the main app object to each worker.
                        # Each worker will create its own app context.
                        executor.map(lambda eid: _process_single_essay(eid, app), essay_ids_to_process)

                    current_app.logger.info(f"Parallel AI processing task finished for all {len(essay_ids_to_process)} essays.")

            thread = threading.Thread(target=ai_processing_task, args=(app, essay_ids))
            thread.start()

            flash(f'成功确认 {len(newly_created_essays)} 份作业的匹配。系统正在后台进行AI校对和评分...', 'success')
        else:
            flash('没有需要确认的有效匹配。', 'info')

        return redirect(url_for('assignments.submissions', assignment_id=assignment_id))

    # GET request logic
    current_app.logger.info(f"--- CONFIRM_SUBMISSIONS (GET) for assignment_id={assignment_id} ---")
    
    try:
        query = PendingSubmission.query.filter_by(assignment_id=assignment_id)
        
        # Log the generated SQL for debugging
        sql_query = str(query.statement.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
        current_app.logger.info(f"Generated SQL: {sql_query}")

        submissions = query.order_by(PendingSubmission.created_at).all()
        current_app.logger.info(f"Query returned {len(submissions)} submissions from the database.")
    except Exception as e:
        current_app.logger.error(f"An error occurred during DB query in confirm_submissions: {e}", exc_info=True)
        submissions = []

    # --- REVISED ROSTER CREATION LOGIC ---
    # Create the student roster for the dropdown, ensuring we get the correct student number from the enrollment.
    roster = []
    roster_ids = set()  # To handle duplicates and prevent multiple entries for the same student

    # 1. Get students assigned via classrooms and their class-specific student numbers
    assigned_classroom_ids = [c.id for c in assignment.classrooms]
    enrollments = Enrollment.query.filter(
        Enrollment.classroom_id.in_(assigned_classroom_ids)
    ).options(
        joinedload(Enrollment.student).joinedload(StudentProfile.user)
    ).all()

    for enrollment in enrollments:
        if enrollment.student.id not in roster_ids:
            roster.append({
                'id': enrollment.student.id,
                'full_name': enrollment.student.user.full_name,
                'student_number': enrollment.student_number  # Get the number from the enrollment
            })
            roster_ids.add(enrollment.student.id)

    # 2. Get students assigned individually (if they weren't already added via classroom)
    individually_assigned_ids = [s.id for s in assignment.students]
    individual_profiles_to_add_ids = [sid for sid in individually_assigned_ids if sid not in roster_ids]
    
    if individual_profiles_to_add_ids:
        # For students added individually, we don't have a classroom context here.
        # So we can't get a class-specific student number. We will mark it as such.
        student_profiles = StudentProfile.query.filter(StudentProfile.id.in_(individual_profiles_to_add_ids)).options(joinedload(StudentProfile.user)).all()
        for profile in student_profiles:
            roster.append({
                'id': profile.id,
                'full_name': profile.user.full_name,
                'student_number': None  # No enrollment context, so no student number available
            })

    # 3. Sort the final roster alphabetically by name for better UX
    roster.sort(key=lambda x: x.get('full_name', ''))

    return render_template(
        'assignments/confirm_submissions.html', 
        assignment=assignment, 
        submissions=submissions, 
        roster=roster,
        form=form
    )


@assignments_bp.route('/submission/<int:submission_id>/review', methods=['GET', 'POST'])
@login_required
def review_submission(submission_id):
    """
    Displays the detailed review page for a single submission.
    Teachers can edit the essay text and adjust scores.
    """
    submission = db.session.get(Essay, submission_id)
    if not submission:
        flash("未找到指定的提交记录。", "danger")
        return redirect(url_for('assignments.list_assignments'))

    # Permission check
    assignment = submission.assignment
    if current_user.role == 'teacher':
        if not hasattr(current_user, 'teacher_profile') or assignment.teacher_profile_id != current_user.teacher_profile.id:
            flash("您没有权限批阅此作业。", "danger")
            return redirect(url_for('assignments.list_assignments'))

    # Logic to get the grading result to display
    grading_result = submission.ai_score or {}
    if submission.teacher_feedback_overrides:
        try:
            # Apply the stored patches to the original AI score
            grading_result = patch(submission.teacher_feedback_overrides, grading_result)
        except Exception as e:
            current_app.logger.error(f"Failed to patch teacher feedback for submission {submission.id}: {e}", exc_info=True)
            flash("应用教师修改时发生错误，将显示原始AI评分。", "warning")
            # Fallback to original ai_score if patching fails
            grading_result = submission.ai_score

    image_filename = os.path.basename(submission.original_image_path) if submission.original_image_path else None
    overlay_filename = os.path.basename(submission.annotated_overlay_path) if submission.annotated_overlay_path else None

    # Fetch rubrics and standard info for the grading panel
    standard = submission.assignment.grading_standard
    total_max_score = standard.total_score if standard else 0
    
    rubrics_by_dimension = {}
    criteria_max_scores = {}
    if standard:
        # Eager load dimensions and rubrics for better performance and template access
        dimensions = db.session.query(Dimension).options(
            joinedload(Dimension.rubrics)
        ).filter(Dimension.standard_id == standard.id).all()
        
        # Attach dimensions to the standard for template access
        standard.dimensions = dimensions
        
        for dim in dimensions:
            criteria_max_scores[dim.name] = dim.max_score
            rubrics_by_dimension[dim.name] = [
                {'level': r.level_name, 'min': r.min_score, 'max': r.max_score}
                for r in dim.rubrics
            ]
    cnm = True
    if cnm:
        current_app.logger.debug(f"Debug: Original OCR text for submission {submission.id}: {submission.original_ocr_text or 'None'}")
        current_app.logger.debug(f"Debug: Corrected content for submission {submission.id}: {submission.content or 'None'}")
        current_app.logger.debug(f"Debug: Teacher corrected text for submission {submission.id}: {submission.teacher_corrected_text or 'None'}")

    # Pre-calculate content variables in backend to avoid template issues
    original_content = submission.content or submission.original_ocr_text or ''
    content_source = submission.teacher_corrected_text if submission.teacher_corrected_text else original_content
    current_app.logger.debug(f'Passing original_content (AI version) to template: {original_content[:100]}...')  # Log first 100 chars for debug
    current_app.logger.debug(f'Passing content_source (Teacher version if exists) to template: {content_source[:100]}...')

    return render_template('assignments/review_submission.html',
                           submission=submission,
                           assignment=assignment,
                           image_filename=image_filename,
                           overlay_filename=overlay_filename,
                           grading_result=grading_result,
                           original_ai_score=submission.ai_score or {},
                           rubrics_data=rubrics_by_dimension,
                           criteria_max_scores=criteria_max_scores,
                           total_max_score=total_max_score,
                           original_content=original_content,
                           content_source=content_source)


@assignments_bp.route('/submission/<int:submission_id>/manual_annotate', methods=['GET', 'POST'])
@login_required
def manual_annotate(submission_id):
    submission = db.session.get(Essay, submission_id)
    if not submission:
        flash("未找到指定的提交记录。", "danger")
        return redirect(url_for('assignments.list_assignments'))

    if request.method == 'POST':
        data = request.get_json()
        image_data = data['image']
        img_data = base64.b64decode(image_data.split(',')[1])
        img = Image.open(BytesIO(img_data))
        filename = f"annotation_{submission.id}_{uuid.uuid4().hex}.png"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)
        img.save(file_path, 'PNG')
        submission.annotated_overlay_path = file_path
        db.session.commit()
        return jsonify({'message': 'Annotation saved successfully'})

    image_filename = os.path.basename(submission.original_image_path) if submission.original_image_path else None
    overlay_filename = os.path.basename(submission.annotated_overlay_path) if submission.annotated_overlay_path else None
    return render_template('assignments/manual_annotate.html', submission=submission, image_filename=image_filename, overlay_filename=overlay_filename)