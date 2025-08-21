import os
import json
import logging
from collections import Counter
from datetime import datetime
import threading
import time

from flask import (render_template, request, flash, redirect, url_for, 
                   current_app, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (EssayAssignment, GradingStandard, Classroom, StudentProfile, 
                        Enrollment, Essay, PendingSubmission,
                        assignment_classrooms_association, 
                        assignment_student_profiles_association)
from app.services.ai_grader import grade_essay_with_ai
from app.services.eval_pipeline import evaluate_essay
from app.services.ocr_service import (recognize_text_from_image_stream, OCRError)
from app.services.ai_corrector import (correct_text_with_ai, AIConnectionError)

from . import assignments_bp
from .forms import EssayAssignmentForm, SubmissionForm

logger = logging.getLogger(__name__)


@assignments_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create_assignment():
    if current_user.role != 'teacher':
        flash('只有教师才能布置作业。', 'warning')
        return redirect(url_for('main.index'))

    form = EssayAssignmentForm()
    
    # Dynamically set queries for the select fields
    _set_dynamic_queries(form)

    if form.validate_on_submit():
        if not form.classrooms.data and not form.students.data:
            flash('请至少选择一个班级或一名学生。', 'danger')
            return render_template('assignments/create_assignment.html', form=form, form_action_url=url_for('assignments.create_assignment'))

        if form.due_date.data and form.due_date.data < datetime.utcnow():
            flash('截止日期不能早于当前时间。', 'danger')
            return render_template('assignments/create_assignment.html', form=form, form_action_url=url_for('assignments.create_assignment'))

        try:
            assignment = EssayAssignment(
                title=form.title.data,
                description=form.description.data,
                due_date=form.due_date.data,
                teacher_profile_id=current_user.teacher_profile.id,
                grading_standard_id=form.grading_standard.data.id,
                prompt_style_template_id=form.prompt_style_template.data.id if form.prompt_style_template.data else None
            )
            assignment.classrooms = form.classrooms.data
            assignment.students = form.students.data
            
            db.session.add(assignment)
            db.session.commit()
            flash('作业已成功发布！', 'success')
            return redirect(url_for('assignments.list_assignments')) 
        except Exception as e:
            db.session.rollback()
            flash(f'发布作业时发生错误: {e}', 'danger')

    return render_template('assignments/create_assignment.html', form=form, form_action_url=url_for('assignments.create_assignment'))


@assignments_bp.route('/edit/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def edit_assignment(assignment_id):
    assignment = EssayAssignment.query.get_or_404(assignment_id)
    
    # Permission check
    if current_user.role != 'teacher' or (hasattr(current_user, 'teacher_profile') and assignment.teacher_profile_id != current_user.teacher_profile.id):
        flash("您没有权限编辑此作业。", "danger")
        return redirect(url_for('assignments.list_assignments'))

    form = EssayAssignmentForm(obj=assignment)
    form.submit.label.text = '更新作业'
    
    _set_dynamic_queries(form)

    if form.validate_on_submit():
        if not form.classrooms.data and not form.students.data:
            flash('请至少选择一个班级或一名学生。', 'danger')
            return render_template('assignments/edit_assignment.html', form=form, form_action_url=url_for('assignments.edit_assignment', assignment_id=assignment.id))

        try:
            assignment.title = form.title.data
            assignment.description = form.description.data
            assignment.due_date = form.due_date.data
            assignment.grading_standard_id = form.grading_standard.data.id
            assignment.prompt_style_template_id = form.prompt_style_template.data.id if form.prompt_style_template.data else None
            assignment.classrooms = form.classrooms.data
            assignment.students = form.students.data
            
            db.session.commit()
            flash('作业已成功更新！', 'success')
            return redirect(url_for('assignments.list_assignments'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新作业时发生错误: {e}', 'danger')

    return render_template('assignments/edit_assignment.html', form=form, form_action_url=url_for('assignments.edit_assignment', assignment_id=assignment.id))


def _set_dynamic_queries(form):
    """Helper function to set dynamic queries on the assignment form."""
    form.grading_standard.query = GradingStandard.query.filter(
        (GradingStandard.creator_id == current_user.id) | (GradingStandard.creator_id == None),
        GradingStandard.is_active == True
    )

    if hasattr(current_user, 'teacher_profile') and current_user.teacher_profile:
        classroom_ids = [c.id for c in current_user.teacher_profile.classrooms]
        form.classrooms.query = Classroom.query.filter(Classroom.id.in_(classroom_ids))
        
        student_profiles = StudentProfile.query.join(Enrollment, StudentProfile.id == Enrollment.student_profile_id).filter(Enrollment.classroom_id.in_(classroom_ids))
        form.students.query = student_profiles
    else:
        form.classrooms.query = Classroom.query.filter_by(id=-1)
        form.students.query = StudentProfile.query.filter_by(id=-1)


# Placeholder for assignment list
@assignments_bp.route('/')
@login_required
def list_assignments():
    if current_user.role not in ['admin', 'teacher', 'student']:
        flash("您没有权限查看此页面。", "warning")
        return redirect(url_for('main.index'))

    query = EssayAssignment.query
    if current_user.role == 'teacher':
        if not hasattr(current_user, 'teacher_profile') or not current_user.teacher_profile:
            flash("您的教师资料不完整，无法查看作业。", "warning")
            return render_template('assignments/list_assignments.html', assignments=[])
        query = query.filter_by(teacher_profile_id=current_user.teacher_profile.id)
    elif current_user.role == 'student':
        if not hasattr(current_user, 'student_profile') or not current_user.student_profile:
            flash("您的学生资料不完整，无法查看作业。", "warning")
            return render_template('assignments/list_assignments.html', assignments=[])
        
        student_profile = current_user.student_profile
        # Find classrooms the student is enrolled in
        enrolled_classroom_ids = [enrollment.classroom_id for enrollment in student_profile.enrollments if enrollment.status == 'active']
        
        # Query for assignments assigned to the student directly
        q1 = EssayAssignment.query.join(
            assignment_student_profiles_association,
            EssayAssignment.id == assignment_student_profiles_association.c.assignment_id
        ).filter(
            assignment_student_profiles_association.c.student_profile_id == student_profile.id
        )

        # Query for assignments assigned to the student's classrooms
        q2 = EssayAssignment.query.join(
            assignment_classrooms_association,
            EssayAssignment.id == assignment_classrooms_association.c.assignment_id
        ).filter(
            assignment_classrooms_association.c.classroom_id.in_(enrolled_classroom_ids)
        )
        
        # Combine and remove duplicates
        query = q1.union(q2)

    assignments = query.order_by(EssayAssignment.created_at.desc()).all()
    return render_template('assignments/list_assignments.html', assignments=assignments)


@assignments_bp.route('/<int:assignment_id>', methods=['GET', 'POST'])
@login_required
def assignment_detail(assignment_id):
    assignment = EssayAssignment.query.get_or_404(assignment_id)
    now = datetime.utcnow()
    form = SubmissionForm()

    if current_user.role == 'student':
        if form.validate_on_submit():
            final_content = None
            original_ocr_text = None
            is_from_ocr = False
            image_path = None

            try:
                # Handle image upload and OCR
                if form.image.data:
                    image_file = form.image.data
                    filename = secure_filename(f"{current_user.id}_{datetime.utcnow().timestamp()}_{image_file.filename}")
                    
                    upload_folder = current_app.config['UPLOAD_FOLDER']
                    os.makedirs(upload_folder, exist_ok=True)
                    image_path = os.path.join(upload_folder, filename)
                    
                    image_file.save(image_path)
                    
                    with open(image_path, 'rb') as f:
                        raw_ocr_text = recognize_text_from_image_stream(f)
                    
                    if not raw_ocr_text or not raw_ocr_text.strip():
                        flash('图片中未能识别出任何文字，请检查图片或直接输入文字。', 'warning')
                        return redirect(url_for('assignments.assignment_detail', assignment_id=assignment.id))

                    # NEW: Correct the OCR text with AI
                    flash('OCR识别完成，正在进行AI校对，请稍候...', 'info')
                    final_content = correct_text_with_ai(raw_ocr_text)
                    original_ocr_text = raw_ocr_text
                    is_from_ocr = True

                else:
                    final_content = form.content.data

            except OCRError as e:
                flash(f'OCR识别失败: {e}', 'danger')
                return redirect(url_for('assignments.assignment_detail', assignment_id=assignment.id))
            except AIConnectionError as e:
                flash(f'AI校对失败: {e}', 'danger')
                return redirect(url_for('assignments.assignment_detail', assignment_id=assignment.id))
            except Exception as e:
                flash(f'处理提交时发生未知错误: {e}', 'danger')
                return redirect(url_for('assignments.assignment_detail', assignment_id=assignment.id))

            # Find an active enrollment for the student
            enrollment = Enrollment.query.filter_by(
                student_profile_id=current_user.student_profile.id,
                status='active'
            ).first()

            if not enrollment:
                flash('您没有有效的班级注册信息，无法提交作业。', 'danger')
                return redirect(url_for('assignments.list_assignments'))

            try:
                new_essay = Essay(
                    enrollment_id=enrollment.id,
                    assignment_id=assignment.id,
                    content=final_content,
                    original_ocr_text=original_ocr_text,
                    is_from_ocr=is_from_ocr,
                    original_image_path=image_path,
                    status='submitted'
                )
                db.session.add(new_essay)
                db.session.commit()

                # Trigger AI grading task using new structured pipeline
                # NOTE: This is a synchronous call for demonstration.
                # In production, this should be offloaded to a background worker (e.g., Celery).
                try:
                    # Prepare metadata for the evaluation pipeline
                    meta = {
                        'student_id': str(current_user.student_profile.id),
                        'grade': '五年级',  # TODO: Get from enrollment or assignment
                        'topic': assignment.title,
                        'words': len(final_content.strip()),
                        'genre': 'narrative'  # TODO: Get from assignment
                    }
                    
                    # Run the structured evaluation pipeline
                    result = evaluate_essay(final_content, meta)
                    
                    # Store the structured result in the Essay.ai_score field
                    new_essay.ai_score = result.model_dump()
                    new_essay.final_score = result.scores.total
                    new_essay.status = 'graded'
                    
                    db.session.commit()
                    
                except Exception as e:
                    # Fall back to original grading on pipeline failure
                    logger.error(f"Evaluation pipeline failed for essay {new_essay.id}: {e}")
                    grade_essay_with_ai(new_essay.id)
                
                flash('作业提交成功！AI正在批改中，请稍后刷新查看结果。', 'success')
                return redirect(url_for('assignments.assignment_detail', assignment_id=assignment.id))
            except Exception as e:
                db.session.rollback()
                flash(f'提交作业时发生错误: {e}', 'danger')
        
        # Get student's previous submissions
        student_submissions = Essay.query.filter_by(
            assignment_id=assignment.id, 
            enrollment_id=current_user.student_profile.enrollments[0].id if current_user.student_profile.enrollments else None
        ).order_by(Essay.created_at.desc()).all()
        
        # --- Chart Data ---
        all_submissions = Essay.query.filter_by(assignment_id=assignment.id).all()
        graded_submissions = [s for s in all_submissions if s.status == 'graded' and s.ai_score]

        # 1. Submission Status Overview
        status_counts = Counter(s.status for s in all_submissions)
        status_chart_data = {
            "labels": list(status_counts.keys()),
            "values": list(status_counts.values())
        }

        # 2. Overall Score Distribution
        score_chart_data = None
        if graded_submissions and assignment.grading_standard:
            total_score_possible = assignment.grading_standard.total_score
            if total_score_possible > 0:
                scores = [s.ai_score.get('total_score', 0) for s in graded_submissions]
                score_chart_data = {
                    "scores": scores,
                    "max_score": total_score_possible
                }

        # 3. Average Score Rate per Dimension
        dimension_chart_data = None
        if graded_submissions and assignment.grading_standard:
            dim_scores = {}
            dim_max_scores = {dim.name: dim.max_score for dim in assignment.grading_standard.dimensions}
            
            for sub in graded_submissions:
                if 'dimensions' in sub.ai_score:
                    for dim_result in sub.ai_score['dimensions']:
                        dim_name = dim_result.get('dimension_name')
                        dim_score = dim_result.get('score')
                        if dim_name and dim_score is not None:
                            if dim_name not in dim_scores:
                                dim_scores[dim_name] = []
                            dim_scores[dim_name].append(dim_score)
            
            dim_avg_rate = {}
            for name, scores in dim_scores.items():
                max_score = dim_max_scores.get(name)
                if max_score and max_score > 0 and scores:
                    avg_score = sum(scores) / len(scores)
                    dim_avg_rate[name] = round((avg_score / max_score) * 100, 2)
            
            if dim_avg_rate:
                dimension_chart_data = {
                    "labels": list(dim_avg_rate.keys()),
                    "values": list(dim_avg_rate.values())
                }

        return render_template(
            'assignments/assignment_detail.html',
            assignment=assignment,
            form=form,
            submissions=student_submissions,
            now=now,
            status_chart_data_json=json.dumps(status_chart_data),
            score_chart_data_json=json.dumps(score_chart_data),
            dimension_chart_data_json=json.dumps(dimension_chart_data)
        )

    elif current_user.role in ['admin', 'teacher']:
        page = request.args.get('page', 1, type=int)
        
        status_map = {
            'graded': '已批改',
            'grading': '批改中',
            'submitted': '已提交',
            'pending': '待处理',
            'not_submitted': '未提交',
            'error_api': 'API错误',
            'error_parsing': '解析错误',
            'error_no_text': '无文本内容',
            'error_no_standard': '无评分标准',
            'error_unknown': '未知错误'
        }
        
        # Count pending submissions that need confirmation
        pending_submissions_count = PendingSubmission.query.filter_by(
            assignment_id=assignment.id
        ).count()
        
        # Use joinedload to prevent N+1 query problem for student names
        submissions_query = Essay.query.options(
            joinedload(Essay.enrollment).joinedload(Enrollment.student).joinedload(StudentProfile.user)
        ).filter_by(assignment_id=assignment.id)
        
        status_filter = request.args.get('status_filter')
        if status_filter and status_filter != 'all':
            submissions_pagination = submissions_query.filter_by(status=status_filter).order_by(Essay.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
        else:
            submissions_pagination = submissions_query.order_by(Essay.created_at.desc()).paginate(page=page, per_page=10, error_out=False)

        all_submissions = submissions_query.all()
        graded_submissions = [s for s in all_submissions if s.status == 'graded' and s.ai_score]

        # 1. Submission Status Overview
        # Create a dictionary to hold status and the list of students in that status
        status_student_map = {status: [] for status in status_map.keys()}
        
        # --- CORRECTED LOGIC to get ALL assigned students ---
        all_assigned_student_profiles = set()
        # Add students assigned individually
        for student_profile in assignment.students:
            all_assigned_student_profiles.add(student_profile)
        # Add students from assigned classrooms
        for classroom in assignment.classrooms:
            for enrollment in classroom.enrollments:
                if enrollment.status == 'active': # Assuming we only count active students
                    all_assigned_student_profiles.add(enrollment.student)
        
        # Map submitted students to their latest status
        # A student can have multiple submissions, we should consider the latest one's status
        latest_submissions = {}
        for sub in sorted(all_submissions, key=lambda s: s.created_at):
            # 防御性编程：检查 enrollment 是否存在，避免 NoneType 错误
            if sub.enrollment and sub.enrollment.student_profile_id:
                latest_submissions[sub.enrollment.student_profile_id] = sub
        
        for student_profile_id, sub in latest_submissions.items():
             # Find the full_name from the pre-loaded relationships
            student_user = next((p.user for p in all_assigned_student_profiles if p.id == student_profile_id), None)
            if student_user:
                status_student_map[sub.status].append(student_user.full_name)

        # Populate not_submitted students
        submitted_student_profile_ids = {s.enrollment.student_profile_id for s in all_submissions if s.enrollment and s.enrollment.student_profile_id}
        if all_assigned_student_profiles:
            for student_profile in all_assigned_student_profiles:
                if student_profile.id not in submitted_student_profile_ids:
                    status_student_map['not_submitted'].append(student_profile.user.full_name)

        # Re-create status_counts for the template's filter pills
        status_counts = {status: len(students) for status, students in status_student_map.items()}

        # Prepare data for the chart, filtering out empty statuses
        status_chart_data = []
        for status, students in status_student_map.items():
            if students:
                status_chart_data.append({
                    "name": status_map[status],
                    "value": len(students),
                    "students": students
                })

        return render_template(
            'assignments/assignment_detail.html',
            assignment=assignment,
            submissions_pagination=submissions_pagination,
            status_counts=status_counts,
            status_filter=status_filter,
            status_map=status_map,
            pending_submissions_count=pending_submissions_count,
            status_chart_data_json=json.dumps(status_chart_data),
            now=now
        )


@assignments_bp.route('/<int:assignment_id>/problem-details/<problem_type>')
@login_required
def get_problem_details(assignment_id, problem_type):
    """获取特定问题类型的详细信息"""
    if current_user.role != 'teacher':
        return jsonify({'error': '只有教师才能查看详细信息'}), 403
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    # 检查权限
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'error': '您没有权限查看此作业详情'}), 403
    
    try:
        # 获取作业报告
        from app.models import AssignmentReport
        report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
        
        if not report or not report.report_data:
            return jsonify({'error': '报告数据不存在，请先生成作业报告'}), 404
        
        # 解析报告数据
        report_data = json.loads(report.report_data)
        
        # 查找匹配的问题类型
        problem_essays = []
        if 'common_issues' in report_data:
            for issue in report_data['common_issues']:
                if issue.get('type') == problem_type and 'detailed_examples' in issue:
                    for example in issue['detailed_examples']:
                        problem_essays.append({
                            'id': example.get('essay_id'),
                            'student_name': example.get('student_name'),
                            'score': _get_essay_score(example.get('essay_id')),
                            'problem_sentence': example.get('problem_sentence'),
                            'problem_location': example.get('sentence_position'),
                            'problem_explanation': example.get('problem_explanation')
                        })
                    break
        
        return jsonify({
            'essays': problem_essays,
            'total': len(problem_essays)
        })
        
    except Exception as e:
        current_app.logger.error(f"获取问题详情失败: {e}")
        return jsonify({'error': '获取详情失败'}), 500


@assignments_bp.route('/<int:assignment_id>/feature-details/<feature_type>')
@login_required
def get_feature_details(assignment_id, feature_type):
    """获取特定优秀特点的详细信息"""
    if current_user.role != 'teacher':
        return jsonify({'error': '只有教师才能查看详细信息'}), 403
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    # 检查权限
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'error': '您没有权限查看此作业详情'}), 403
    
    try:
        # 获取作业报告
        from app.models import AssignmentReport
        report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
        
        if not report or not report.report_data:
            return jsonify({'error': '报告数据不存在，请先生成作业报告'}), 404
        
        # 解析报告数据
        report_data = json.loads(report.report_data)
        
        # 查找匹配的优秀特点
        feature_essays = []
        if 'excellent_features' in report_data:
            for feature in report_data['excellent_features']:
                if feature.get('type') == feature_type and 'detailed_examples' in feature:
                    for example in feature['detailed_examples']:
                        feature_essays.append({
                            'id': example.get('essay_id'),
                            'student_name': example.get('student_name'),
                            'score': _get_essay_score(example.get('essay_id')),
                            'excellent_sentence': example.get('excellent_sentence'),
                            'sentence_location': example.get('sentence_position'),
                            'feature_explanation': example.get('feature_explanation')
                        })
                    break
        
        return jsonify({
            'essays': feature_essays,
            'total': len(feature_essays)
        })
        
    except Exception as e:
        current_app.logger.error(f"获取优秀特点详情失败: {e}")
        return jsonify({'error': '获取详情失败'}), 500


@assignments_bp.route('/<int:assignment_id>/search-example', methods=['POST'])
@login_required
def search_example(assignment_id):
    """根据示例文本搜索作文"""
    if current_user.role != 'teacher':
        return jsonify({'error': '只有教师才能搜索示例'}), 403
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    # 检查权限
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'error': '您没有权限搜索此作业'}), 403
    
    try:
        data = request.get_json()
        example_text = data.get('example', '').strip()
        
        if not example_text:
            return jsonify({'error': '示例文本不能为空'}), 400
        
        # 获取作业报告
        from app.models import AssignmentReport
        report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
        
        if not report or not report.report_data:
            return jsonify({'error': '报告数据不存在，请先生成作业报告'}), 404
        
        # 解析报告数据
        report_data = json.loads(report.report_data)
        
        # 在AI分析结果中搜索
        matching_essays = []
        
        # 搜索共性问题中的示例
        if 'common_issues' in report_data:
            for issue in report_data['common_issues']:
                if 'detailed_examples' in issue:
                    for example in issue['detailed_examples']:
                        if (example_text.lower() in example.get('problem_sentence', '').lower() or
                            example_text.lower() in example.get('student_name', '').lower()):
                            matching_essays.append({
                                'id': example.get('essay_id'),
                                'student_name': example.get('student_name'),
                                'score': _get_essay_score(example.get('essay_id')),
                                'matched_sentence': example.get('problem_sentence'),
                                'sentence_position': example.get('sentence_position'),
                                'match_type': '问题示例',
                                'category': issue.get('type')
                            })
        
        # 搜索优秀特点中的示例
        if 'excellent_features' in report_data:
            for feature in report_data['excellent_features']:
                if 'detailed_examples' in feature:
                    for example in feature['detailed_examples']:
                        if (example_text.lower() in example.get('excellent_sentence', '').lower() or
                            example_text.lower() in example.get('student_name', '').lower()):
                            matching_essays.append({
                                'id': example.get('essay_id'),
                                'student_name': example.get('student_name'),
                                'score': _get_essay_score(example.get('essay_id')),
                                'matched_sentence': example.get('excellent_sentence'),
                                'sentence_position': example.get('sentence_position'),
                                'match_type': '优秀示例',
                                'category': feature.get('type')
                            })
        
        # 去重（基于essay_id和句子内容）
        seen = set()
        unique_essays = []
        for essay in matching_essays:
            key = (essay['id'], essay['matched_sentence'])
            if key not in seen:
                seen.add(key)
                unique_essays.append(essay)
        
        return jsonify({
            'essays': unique_essays,
            'total': len(unique_essays)
        })
        
    except Exception as e:
        current_app.logger.error(f'搜索示例失败: {e}')
        return jsonify({'error': '搜索失败'}), 500


def _get_essay_score(essay_id):
    """获取作文分数"""
    if not essay_id:
        return None
    
    try:
        from app.models import Essay
        essay = db.session.get(Essay, essay_id)
        if essay:
            return essay.final_score or essay.ai_score
        return None
    except Exception:
        return None


@assignments_bp.route('/<int:assignment_id>/report')
@login_required
def assignment_report(assignment_id):
    """显示作业报告页面"""
    if current_user.role != 'teacher':
        flash('只有教师才能查看作业报告。', 'warning')
        return redirect(url_for('main.index'))
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        flash('作业不存在。', 'danger')
        return redirect(url_for('assignments.list_assignments'))
    
    # 检查是否有权限查看此作业
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        flash('您没有权限查看此作业报告。', 'warning')
        return redirect(url_for('assignments.list_assignments'))
    
    # 获取或生成报告
    from app.models import AssignmentReport
    report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
    
    if not report:
        # 如果没有报告，重定向到生成报告页面
        return redirect(url_for('assignments.generate_report', assignment_id=assignment_id))
    
    # 解析报告数据
    report_data = json.loads(report.report_data) if report.report_data else {}
    
    return render_template(
        'assignments/assignment_report.html',
        assignment=assignment,
        report=report,
        report_data=report_data
    )


@assignments_bp.route('/<int:assignment_id>/generate-report', methods=['GET', 'POST'])
@login_required
def generate_report(assignment_id):
    """生成作业报告"""
    if current_user.role != 'teacher':
        flash('只有教师才能生成作业报告。', 'warning')
        return redirect(url_for('main.index'))
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        flash('作业不存在。', 'danger')
        return redirect(url_for('assignments.list_assignments'))
    
    # 检查权限
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        flash('您没有权限生成此作业报告。', 'warning')
        return redirect(url_for('assignments.list_assignments'))
    
    if request.method == 'POST':
        try:
            from app.services.ai_report_analyzer import analyze_assignment_with_ai
            from app.models import AssignmentReport
            
            # 检查是否已有报告，如果有则删除旧报告
            existing_report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
            if existing_report:
                db.session.delete(existing_report)
            
            # 生成新报告
            report_data = analyze_assignment_with_ai(assignment_id)
            
            # 保存报告到数据库
            new_report = AssignmentReport(
                assignment_id=assignment_id,
                report_data=json.dumps(report_data, ensure_ascii=False),
                generated_by=user_id
            )
            
            db.session.add(new_report)
            db.session.commit()
            
            flash('作业报告生成成功！', 'success')
            return redirect(url_for('assignments.assignment_report', assignment_id=assignment_id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"生成作业报告失败: {e}")
            flash(f'生成报告失败: {str(e)}', 'danger')
            # 返回到生成页面，并添加错误参数以便前端恢复状态
            return redirect(url_for('assignments.generate_report', assignment_id=assignment_id, error=1))
    
    # 获取作业统计信息用于显示（包括AI评分和教师评分）
    essays_count = db.session.query(Essay).filter(
        Essay.assignment_id == assignment_id,
        db.or_(
            Essay.ai_score.isnot(None),
            Essay.final_score.isnot(None)
        )
    ).count()
    
    return render_template(
        'assignments/generate_report.html',
        assignment=assignment,
        essays_count=essays_count
    )


# 全局变量跟踪报告生成任务状态
report_generation_tasks = {}


@assignments_bp.route('/<int:assignment_id>/generate-report-async', methods=['POST'])
@login_required
def generate_report_async(assignment_id):
    """异步生成作业报告"""
    if current_user.role != 'teacher':
        return jsonify({'error': '只有教师才能生成作业报告'}), 403
    
    assignment = db.session.get(EssayAssignment, assignment_id)
    if not assignment:
        return jsonify({'error': '作业不存在'}), 404
    
    # 检查权限
    if assignment.teacher_profile_id != current_user.teacher_profile.id:
        return jsonify({'error': '您没有权限生成此作业报告'}), 403
    
    # 生成任务键
    task_key = f"{current_user.id}_{assignment_id}"
    
    # 检查是否已有任务在进行，如果有则清理旧任务
    if task_key in report_generation_tasks:
        if report_generation_tasks[task_key]['status'] == 'running':
            return jsonify({'error': '报告正在生成中，请稍候'}), 400
        else:
            # 清理已完成或失败的任务
            del report_generation_tasks[task_key]
    
    # 初始化任务状态
    report_generation_tasks[task_key] = {
        'status': 'running',
        'progress': 0,
        'message': '开始生成报告...',
        'error': None,
        'result': None
    }
    
    # 启动后台线程生成报告
    app = current_app._get_current_object()  # 获取应用实例
    thread = threading.Thread(target=_generate_report_background, args=(app, assignment_id, task_key, current_user.id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'task_key': task_key,
        'message': '报告生成任务已启动'
    })


@assignments_bp.route('/<int:assignment_id>/report-status/<task_key>')
@login_required
def get_report_status(assignment_id, task_key):
    """获取报告生成状态"""
    # 验证任务键格式
    expected_task_key = f"{current_user.id}_{assignment_id}"
    if task_key != expected_task_key:
        return jsonify({'error': '无效的任务键'}), 403
    
    if task_key not in report_generation_tasks:
        return jsonify({'error': '任务不存在'}), 404
    
    task_info = report_generation_tasks[task_key]
    
    response = {
        'status': task_info['status'],
        'progress': task_info['progress'],
        'message': task_info['message']
    }
    
    if task_info['status'] == 'completed':
        response['redirect_url'] = url_for('assignments.assignment_report', assignment_id=assignment_id)
        # 清理已完成的任务
        del report_generation_tasks[task_key]
    elif task_info['status'] == 'failed':
        response['error'] = task_info['error']
        # 清理失败的任务
        del report_generation_tasks[task_key]
    
    return jsonify(response)


def _generate_report_background(app, assignment_id, task_key, user_id):
    """后台生成报告的函数"""
    from app.services.ai_report_analyzer import analyze_assignment_with_ai
    from app.models import AssignmentReport
    
    # 将整个函数包装在应用上下文中
    with app.app_context():
        try:
            current_app.logger.info(f"开始后台生成报告，任务ID: {task_key}, 作业ID: {assignment_id}")
            
            # 更新进度：开始分析
            report_generation_tasks[task_key].update({
                'progress': 10,
                'message': '正在收集作业数据...'
            })
            current_app.logger.info(f"任务 {task_key} 进度更新到 10%")
            time.sleep(0.5)  # 模拟处理时间
            
            # 更新进度：AI分析
            report_generation_tasks[task_key].update({
                'progress': 30,
                'message': '正在进行AI分析...'
            })
            current_app.logger.info(f"任务 {task_key} 进度更新到 30%")
            
            # 检查是否已有报告，如果有则删除旧报告
            existing_report = AssignmentReport.query.filter_by(assignment_id=assignment_id).first()
            if existing_report:
                current_app.logger.info(f"删除作业 {assignment_id} 的旧报告")
                db.session.delete(existing_report)
            
            # 更新进度：生成报告数据
            report_generation_tasks[task_key].update({
                'progress': 60,
                'message': '正在生成报告数据...'
            })
            current_app.logger.info(f"任务 {task_key} 进度更新到 60%，开始调用AI分析")
            
            # 生成新报告
            report_data = analyze_assignment_with_ai(assignment_id)
            current_app.logger.info(f"任务 {task_key} AI分析完成，获得报告数据")
            
            # 更新进度：保存报告
            report_generation_tasks[task_key].update({
                'progress': 90,
                'message': '正在保存报告...'
            })
            
            # 保存报告到数据库
            new_report = AssignmentReport(
                assignment_id=assignment_id,
                report_data=json.dumps(report_data, ensure_ascii=False),
                generated_by=user_id
            )
            
            db.session.add(new_report)
            db.session.commit()
            
            # 完成
            report_generation_tasks[task_key].update({
                'status': 'completed',
                'progress': 100,
                'message': '报告生成完成！'
            })
            
        except Exception as e:
            # 在应用上下文中记录错误
            current_app.logger.error(f"后台生成作业报告失败: {e}")
            # 回滚数据库事务
            try:
                db.session.rollback()
            except:
                pass
            # 更新任务状态
            report_generation_tasks[task_key].update({
                'status': 'failed',
                'progress': 0,
                'message': '报告生成失败',
                'error': str(e)
            })