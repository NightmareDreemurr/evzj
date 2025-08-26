import os
from datetime import datetime, timedelta
from collections import defaultdict

from flask import jsonify, request, current_app
from flask_login import login_required, current_user
from dictdiffer import diff

from app.extensions import db
from app.models import Essay, PendingSubmission, EssayAssignment
from app.decorators import teacher_required
from app.services.evaluation_builder import load_evaluation_from_essay
from app.schemas.evaluation import EvaluationResult

from . import assignments_bp


# Rate limiting storage (in production, use Redis or similar)
_rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # 60 seconds
MAX_REQUESTS_PER_WINDOW = 30  # Max 30 requests per minute per user

def is_rate_limited(user_id):
    """Check if user is rate limited for API requests"""
    now = datetime.utcnow()
    user_requests = _rate_limit_store[user_id]
    
    # Remove requests older than the window
    cutoff_time = now - timedelta(seconds=RATE_LIMIT_WINDOW)
    _rate_limit_store[user_id] = [req_time for req_time in user_requests if req_time > cutoff_time]
    
    # Check if under limit
    if len(_rate_limit_store[user_id]) >= MAX_REQUESTS_PER_WINDOW:
        return True
    
    # Add current request
    _rate_limit_store[user_id].append(now)
    return False


ESSAY_STATUS_PROGRESS_MAP = {
    'pending': {'progress': 10, 'text': '排队等待处理...'},
    'correcting': {'progress': 40, 'text': 'AI校对中...'},
    'grading': {'progress': 80, 'text': 'AI评分中...'},
    'graded': {'progress': 100, 'text': '处理完成'},
    'error_correction': {'progress': 100, 'text': '处理失败'},
    'error_api': {'progress': 100, 'text': '处理失败'},
    'error_parsing': {'progress': 100, 'text': '处理失败'},
    'error_no_text': {'progress': 100, 'text': '处理失败'},
    'error_no_standard': {'progress': 100, 'text': '处理失败'},
    'error_unknown': {'progress': 100, 'text': '处理失败'},
}


@assignments_bp.route('/api/essays/status')
@login_required
@teacher_required
def get_essay_statuses():
    """
    API endpoint to get the status of multiple essays.
    Expects a comma-separated list of essay IDs in the 'ids' query parameter.
    Includes rate limiting to prevent excessive polling.
    """
    # Rate limiting check
    if is_rate_limited(current_user.id):
        return jsonify({
            "error": "Rate limit exceeded. Please wait before making more requests.",
            "retry_after": RATE_LIMIT_WINDOW
        }), 429
    
    essay_ids_str = request.args.get('ids')
    if not essay_ids_str:
        return jsonify({"error": "No essay IDs provided"}), 400

    essay_ids = [int(id) for id in essay_ids_str.split(',') if id.isdigit()]
    
    # Query the database directly for the status of the essays
    essays = db.session.query(Essay.id, Essay.status, Essay.error_message).filter(Essay.id.in_(essay_ids)).all()
    
    status_map = {}
    for essay_id, status, error_message in essays:
        is_finished = status in ['graded', 'error_api', 'error_parsing', 'error_unknown', 'error_no_text', 'error_no_standard']
        
        # Define progress based on status
        progress_map = {
            'pending': 10,
            'pending_ai_processing': 10,
            'correcting': 40,
            'grading': 75,
            'graded': 100
        }
        progress = progress_map.get(status, 100 if is_finished else 0)
        
        # Define text based on status
        text_map = {
            'pending': '排队等待AI处理...',
            'pending_ai_processing': '排队等待AI处理...',
            'correcting': 'AI正在进行文本校对...',
            'grading': 'AI正在进行评分...',
            'graded': '处理完成',
            'error_api': f'处理失败: {error_message}',
            'error_parsing': f'处理失败: {error_message}',
            'error_unknown': f'处理失败: {error_message}',
            'error_no_text': '处理失败: 作文内容为空',
            'error_no_standard': '处理失败: 未找到评分标准'
        }
        text = text_map.get(status, '未知状态')

        status_map[essay_id] = {
            'is_finished': is_finished,
            'progress': progress,
            'text': text
        }
        
    return jsonify(status_map)


STATUS_PROGRESS_MAP = {
    'uploaded': {'progress': 10, 'text': '已上传，等待处理...'},
    'preprocessing': {'progress': 25, 'text': '预处理中...'},
    'ocr_processing': {'progress': 50, 'text': '文字识别（OCR）中...'},
    'ocr_completed': {'progress': 75, 'text': '文字识别完成，等待匹配...'},
    'matching': {'progress': 90, 'text': '正在智能匹配学生...'},
    'match_completed': {'progress': 100, 'text': '处理完成'},
    'failed': {'progress': 100, 'text': '处理失败'},
}


@assignments_bp.route('/api/pending_submissions/status')
@login_required
@teacher_required
def get_pending_submissions_status():
    """
    API endpoint to get the status of multiple pending submissions.
    Expects a comma-separated list of pending submission IDs in the 'ids' query parameter.
    Includes rate limiting to prevent excessive polling.
    """
    # Rate limiting check
    if is_rate_limited(current_user.id):
        return jsonify({
            "error": "Rate limit exceeded. Please wait before making more requests.",
            "retry_after": RATE_LIMIT_WINDOW
        }), 429
    
    submission_ids_str = request.args.get('ids')
    if not submission_ids_str:
        return jsonify({"error": "No submission IDs provided"}), 400

    submission_ids = [int(id) for id in submission_ids_str.split(',') if id.isdigit()]
    
    # Query the database for the status of the pending submissions
    submissions = db.session.query(PendingSubmission.id, PendingSubmission.status, PendingSubmission.error_message, PendingSubmission.assignment_id).filter(PendingSubmission.id.in_(submission_ids)).all()
    
    # Permission check - ensure teacher owns all these assignments
    assignment_ids = list(set([sub[3] for sub in submissions]))
    teacher_assignments = db.session.query(EssayAssignment.id).filter(
        EssayAssignment.id.in_(assignment_ids),
        EssayAssignment.teacher_profile_id == current_user.teacher_profile.id
    ).all()
    
    if len(teacher_assignments) != len(assignment_ids):
        return jsonify({'error': 'Permission denied'}), 403
    
    status_map = {}
    for submission_id, status, error_message, assignment_id in submissions:
        is_finished = status in ['match_completed', 'failed']
        
        status_info = STATUS_PROGRESS_MAP.get(status, {'progress': 0, 'text': '未知状态'})
        
        status_map[submission_id] = {
            'is_finished': is_finished,
            'progress': status_info['progress'],
            'text': status_info['text'],
            'status': status
        }
        
    return jsonify(status_map)


    """
    API endpoint to get the real-time status of a pending submission.
    """
    submission = db.session.get(PendingSubmission, pending_submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    # Permission check
    assignment = submission.assignment
    if current_user.role == 'teacher' and (not hasattr(current_user, 'teacher_profile') or assignment.teacher_profile_id != current_user.teacher_profile.id):
        return jsonify({'error': 'Permission denied'}), 403

    status_info = STATUS_PROGRESS_MAP.get(submission.status, {'progress': 0, 'text': '未知状态'})
    
    response = {
        'id': submission.id,
        'status': submission.status,
        'progress': status_info['progress'],
        'text': status_info['text'],
        'error_message': submission.error_message,
        'matched_student_id': submission.matched_student_id,
        'ocr_text': submission.ocr_text,
    }

    if submission.status == 'match_completed' and submission.matched_student:
        response['matched_student_name'] = submission.matched_student.user.full_name
    
    return jsonify(response)


@assignments_bp.route('/pending_submission/<int:pending_submission_id>', methods=['DELETE'])
@login_required
def delete_pending_submission(pending_submission_id):
    """
    Deletes a PendingSubmission object and its associated file.
    """
    if not hasattr(current_user, 'teacher_profile'):
        return jsonify({'error': 'Permission denied'}), 403

    submission = db.session.get(PendingSubmission, pending_submission_id)
    if not submission:
        return jsonify({'error': 'Submission not found'}), 404

    # Security check: ensure the current user owns the assignment
    assignment = submission.assignment
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'error': 'Permission denied'}), 403

    try:
        # Delete the associated image file from the filesystem
        if submission.file_path and os.path.exists(submission.file_path):
            os.remove(submission.file_path)
        
        db.session.delete(submission)
        db.session.commit()
        
        current_app.logger.info(f"Deleted pending submission {pending_submission_id} by user {current_user.id}")
        return jsonify({'success': True, 'message': '已成功删除该待处理提交。'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting pending submission {pending_submission_id}: {e}", exc_info=True)
        return jsonify({'error': '删除过程中发生内部错误。'}), 500


@assignments_bp.route('/api/submission/<int:submission_id>/update_teacher_feedback', methods=['POST'])
@login_required
@teacher_required
def update_teacher_feedback(submission_id):
    submission = db.session.get(Essay, submission_id)
    if not submission or submission.assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'message': 'Submission not found or not authorized'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'message': 'Invalid data'}), 400

    teacher_scores = data.get('teacher_scores')
    teacher_corrected_text = data.get('teacher_corrected_text')
    full_feedback = data.get('full_feedback')

    # 1. Update teacher-corrected text
    if teacher_corrected_text is not None:
        submission.teacher_corrected_text = teacher_corrected_text

    # 2. Update scores and calculate total
    if teacher_scores:
        submission.teacher_score = teacher_scores
        total_score = sum(teacher_scores.values())
        submission.final_score = total_score
    
    # 3. Calculate and save feedback overrides
    if full_feedback and submission.ai_score:
        # Use dictdiffer to find the difference between the original AI feedback and teacher's version
        # The result is an iterator of tuples, e.g., ('change', 'key.path', (old_value, new_value))
        overrides = list(diff(submission.ai_score, full_feedback))
        if overrides:
            # We store the list of differences.
            # When rendering, we'll need a function to apply these patches.
            submission.teacher_feedback_overrides = overrides
        else:
            # If there are no differences, ensure the field is null
            submission.teacher_feedback_overrides = None

    db.session.commit()

    return jsonify({'message': 'Feedback updated successfully', 'final_score': submission.final_score})


@assignments_bp.route('/api/submissions/<int:submission_id>/evaluation', methods=['GET'])
@login_required
@teacher_required
def get_submission_evaluation(submission_id):
    """
    GET endpoint to retrieve the unified EvaluationResult for a submission.
    Returns both AI-generated and teacher-reviewed data.
    """
    submission = db.session.get(Essay, submission_id)
    if not submission or submission.assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'message': 'Submission not found or not authorized'}), 404
    
    # Try to load existing evaluation data
    evaluation = load_evaluation_from_essay(submission_id)
    if not evaluation:
        return jsonify({'message': 'No evaluation data found for this submission'}), 404
    
    # Add status information
    response_data = evaluation.model_dump()
    response_data['evaluation_status'] = submission.evaluation_status or 'ai_generated'
    response_data['reviewed_by'] = submission.reviewed_by
    response_data['reviewed_at'] = submission.reviewed_at.isoformat() if submission.reviewed_at else None
    
    return jsonify(response_data)


@assignments_bp.route('/api/submissions/<int:submission_id>/evaluation', methods=['PUT'])
@login_required
@teacher_required
def update_submission_evaluation(submission_id):
    """
    PUT endpoint to update the EvaluationResult after teacher review.
    Accepts full EvaluationResult data and updates the submission.
    """
    submission = db.session.get(Essay, submission_id)
    if not submission or submission.assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'message': 'Submission not found or not authorized'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'message': 'Invalid data'}), 400
    
    try:
        # Validate the data structure by creating an EvaluationResult instance
        evaluation = EvaluationResult(**data)
        
        # Update the submission with the new evaluation data
        submission.ai_evaluation = evaluation.model_dump()
        submission.evaluation_status = 'teacher_reviewed'
        submission.reviewed_by = current_user.teacher_profile.id
        submission.reviewed_at = datetime.utcnow()
        
        db.session.commit()
        
        current_app.logger.info(f"Teacher {current_user.teacher_profile.id} reviewed evaluation for submission {submission_id}")
        
        return jsonify({
            'message': 'Evaluation updated successfully',
            'evaluation_status': submission.evaluation_status,
            'reviewed_at': submission.reviewed_at.isoformat()
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating evaluation for submission {submission_id}: {e}", exc_info=True)
        return jsonify({'message': 'Failed to update evaluation', 'error': str(e)}), 500
