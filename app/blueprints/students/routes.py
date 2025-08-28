from flask import render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, desc, func
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (User, StudentProfile, Enrollment, Classroom, 
                        TeacherProfile, Essay, teachers_classrooms_association)
from app.decorators import teacher_required
from . import students_bp
from .forms import StudentForm, StudentSearchForm, DeleteStudentForm
from .transfer_forms import StudentTransferForm


@students_bp.before_request
@login_required
@teacher_required
def before_request():
    """保护此蓝图下的所有路由"""
    pass


def _set_dynamic_queries(form):
    """设置表单的动态查询"""
    if hasattr(current_user, 'teacher_profile') and current_user.teacher_profile:
        classroom_ids = [c.id for c in current_user.teacher_profile.classrooms]
        form.classroom.query = Classroom.query.filter(Classroom.id.in_(classroom_ids))
    else:
        form.classroom.query = Classroom.query.filter_by(id=-1)


def _get_teacher_students_query():
    """获取教师所教学生的查询对象"""
    if not hasattr(current_user, 'teacher_profile') or not current_user.teacher_profile:
        return StudentProfile.query.filter_by(id=-1)
    
    classroom_ids = [c.id for c in current_user.teacher_profile.classrooms]
    
    return StudentProfile.query.join(
        Enrollment, StudentProfile.id == Enrollment.student_profile_id
    ).join(
        Classroom, Enrollment.classroom_id == Classroom.id
    ).filter(
        Classroom.id.in_(classroom_ids)
    ).distinct()


@students_bp.route('/')
def list_students():
    """学生列表页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    classroom_filter = request.args.get('classroom', '', type=str)
    status_filter = request.args.get('status', '', type=str)
    
    # 获取教师所教的学生
    query = _get_teacher_students_query().options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.enrollments).joinedload(Enrollment.classroom)
    )
    
    # 搜索过滤
    if search:
        query = query.join(User, StudentProfile.user_id == User.id).filter(
            or_(
                User.full_name.contains(search),
                User.username.contains(search),
                Enrollment.student_number.contains(search)
            )
        )
    
    # 班级过滤
    if classroom_filter:
        query = query.filter(Enrollment.classroom_id == classroom_filter)
    
    # 状态过滤
    if status_filter:
        query = query.filter(Enrollment.status == status_filter)
    
    students = query.order_by(User.full_name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 获取教师的班级列表用于筛选
    classrooms = current_user.teacher_profile.classrooms if current_user.teacher_profile else []
    
    return render_template('students/list.html', 
                         students=students, 
                         search=search,
                         classroom_filter=classroom_filter,
                         status_filter=status_filter,
                         classrooms=classrooms)


@students_bp.route('/add', methods=['GET', 'POST'])
def add_student():
    """添加新学生"""
    form = StudentForm()
    _set_dynamic_queries(form)
    
    if form.validate_on_submit():
        try:
            # 检查邮箱是否已存在
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                flash('该邮箱已被注册，请使用其他邮箱。', 'danger')
                return render_template('students/add.html', form=form)
            
            # 创建用户账号
            user = User(
                email=form.email.data,
                username=form.email.data,  # 使用邮箱作为用户名
                phone=form.phone.data,
                password_hash=generate_password_hash('123456'),  # 默认密码
                role='student',
                full_name=form.full_name.data
            )
            db.session.add(user)
            db.session.flush()  # 获取user.id
            
            # 创建学生档案
            student_profile = StudentProfile(user_id=user.id)
            db.session.add(student_profile)
            db.session.flush()  # 获取student_profile.id
            
            # 创建入学记录
            enrollment = Enrollment(
                student_profile_id=student_profile.id,
                classroom_id=form.classroom.data.id,
                student_number=form.student_number.data,
                status=form.status.data
            )
            db.session.add(enrollment)
            
            db.session.commit()
            flash(f'学生 {user.full_name} 添加成功！默认密码为：123456', 'success')
            return redirect(url_for('students.list_students'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'添加学生失败：{str(e)}', 'danger')
    
    return render_template('students/add.html', form=form)


@students_bp.route('/<int:student_id>')
def student_detail(student_id):
    """学生详情页面"""
    student = StudentProfile.query.options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.enrollments).joinedload(Enrollment.classroom)
    ).get_or_404(student_id)
    
    # 权限检查：确保学生属于教师所教的班级
    if not _check_student_permission(student):
        abort(403)
    
    # 获取学生的作文统计（包含所有作文）
    total_essays_count = db.session.query(
        func.count(Essay.id)
    ).join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id
    ).scalar() or 0
    
    # 获取已评分作文的统计
    graded_essay_stats = db.session.query(
        func.count(Essay.id).label('graded_essays'),
        func.avg(Essay.final_score).label('average_score'),
        func.max(Essay.final_score).label('highest_score'),
        func.min(Essay.final_score).label('lowest_score')
    ).join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id,
        Essay.status == 'graded',
        Essay.final_score.isnot(None)
    ).first()
    
    # 构建完整的作文统计信息
    essay_stats = {
        'total_essays': total_essays_count,
        'graded_essays': graded_essay_stats.graded_essays if graded_essay_stats else 0,
        'average_score': graded_essay_stats.average_score if graded_essay_stats else None,
        'highest_score': graded_essay_stats.highest_score if graded_essay_stats else None,
        'lowest_score': graded_essay_stats.lowest_score if graded_essay_stats else None
    }
    
    # 获取最近的作文记录
    recent_essays = Essay.query.join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id
    ).order_by(desc(Essay.created_at)).limit(10).all()
    
    return render_template('students/detail.html', 
                         student=student,
                         essay_stats=essay_stats,
                         recent_essays=recent_essays)


@students_bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
def edit_student(student_id):
    """编辑学生信息（仅限查看，不允许修改）"""
    student = StudentProfile.query.options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.enrollments).joinedload(Enrollment.classroom)
    ).get_or_404(student_id)
    
    # 权限检查
    if not _check_student_permission(student):
        abort(403)
    
    # 获取当前的入学记录（假设只有一个活跃的入学记录）
    current_enrollment = next(
        (e for e in student.enrollments if e.status == 'active'), 
        student.enrollments[0] if student.enrollments else None
    )
    
    if not current_enrollment:
        flash('该学生没有有效的入学记录。', 'danger')
        return redirect(url_for('students.list_students'))
    
    # 教师只能查看学生信息，不能修改
    flash('教师只能查看学生信息，如需转移学生班级，请使用班级转移功能。', 'info')
    return redirect(url_for('students.student_detail', student_id=student.id))


@students_bp.route('/<int:student_id>/transfer', methods=['GET', 'POST'])
def transfer_student(student_id):
    """学生班级转移"""
    student = StudentProfile.query.options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.enrollments).joinedload(Enrollment.classroom)
    ).get_or_404(student_id)
    
    # 权限检查
    if not _check_student_permission(student):
        abort(403)
    
    # 获取当前的入学记录
    current_enrollment = next(
        (e for e in student.enrollments if e.status == 'active'), 
        student.enrollments[0] if student.enrollments else None
    )
    
    if not current_enrollment:
        flash('该学生没有有效的入学记录。', 'danger')
        return redirect(url_for('students.list_students'))
    
    form = StudentTransferForm()
    
    # 设置可选择的班级（只能选择教师管辖的班级，且排除当前班级）
    if hasattr(current_user, 'teacher_profile') and current_user.teacher_profile:
        available_classrooms = [
            c for c in current_user.teacher_profile.classrooms 
            if c.id != current_enrollment.classroom_id
        ]
        form.target_classroom.query = Classroom.query.filter(
            Classroom.id.in_([c.id for c in available_classrooms])
        )
    else:
        form.target_classroom.query = Classroom.query.filter_by(id=-1)
    
    if form.validate_on_submit():
        try:
            old_classroom = current_enrollment.classroom.class_name
            new_classroom = form.target_classroom.data.class_name
            
            # 更新学生的班级
            current_enrollment.classroom_id = form.target_classroom.data.id
            
            db.session.commit()
            
            flash_message = f'学生 {student.user.full_name} 已成功从 {old_classroom} 转移到 {new_classroom}'
            if form.reason.data:
                flash_message += f'，转移原因：{form.reason.data}'
            
            flash(flash_message, 'success')
            return redirect(url_for('students.student_detail', student_id=student.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'转移学生失败：{str(e)}', 'danger')
    
    return render_template('students/transfer.html', 
                         form=form, 
                         student=student, 
                         current_enrollment=current_enrollment)


@students_bp.route('/<int:student_id>/delete', methods=['POST'])
def delete_student(student_id):
    """删除学生（软删除）"""
    student = StudentProfile.query.get_or_404(student_id)
    
    # 权限检查
    if not _check_student_permission(student):
        abort(403)
    
    try:
        # 软删除：将所有入学记录状态设为withdrawn
        for enrollment in student.enrollments:
            enrollment.status = 'withdrawn'
        
        db.session.commit()
        flash(f'学生 {student.user.full_name} 已被标记为退学状态。', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'删除学生失败：{str(e)}', 'danger')
    
    return redirect(url_for('students.list_students'))


@students_bp.route('/search')
def search_students():
    """AJAX搜索学生接口"""
    q = request.args.get('q', '', type=str)
    classroom_id = request.args.get('classroom_id', '', type=str)
    status = request.args.get('status', '', type=str)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = _get_teacher_students_query().options(
        joinedload(StudentProfile.user),
        joinedload(StudentProfile.enrollments).joinedload(Enrollment.classroom)
    )
    
    # 搜索过滤
    if q:
        query = query.join(User, StudentProfile.user_id == User.id).filter(
            or_(
                User.full_name.contains(q),
                User.username.contains(q),
                Enrollment.student_number.contains(q)
            )
        )
    
    # 班级过滤
    if classroom_id:
        query = query.filter(Enrollment.classroom_id == classroom_id)
    
    # 状态过滤
    if status:
        query = query.filter(Enrollment.status == status)
    
    students = query.order_by(User.full_name).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # 构建响应数据
    student_data = []
    for student in students.items:
        enrollment = next(
            (e for e in student.enrollments if e.status == 'active'),
            student.enrollments[0] if student.enrollments else None
        )
        
        student_data.append({
            'id': student.id,
            'name': student.user.full_name,
            'student_number': enrollment.student_number if enrollment else '',
            'classroom_name': enrollment.classroom.class_name if enrollment else '',
            'status': enrollment.status if enrollment else '',
            'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d') if enrollment else ''
        })
    
    return jsonify({
        'students': student_data,
        'total': students.total,
        'page': students.page,
        'pages': students.pages
    })


@students_bp.route('/<int:student_id>/essays')
def student_essays(student_id):
    """获取学生作文历史API"""
    student = StudentProfile.query.get_or_404(student_id)
    
    # 权限检查
    if not _check_student_permission(student):
        abort(403)
    
    # 获取学生的作文记录
    essays = Essay.query.join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id
    ).order_by(desc(Essay.created_at)).all()
    
    # 获取统计信息
    essay_stats = db.session.query(
        func.count(Essay.id).label('total_essays'),
        func.avg(Essay.final_score).label('average_score'),
        func.max(Essay.final_score).label('highest_score'),
        func.min(Essay.final_score).label('lowest_score')
    ).join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id,
        Essay.status == 'graded',
        Essay.final_score.isnot(None)
    ).first()
    
    # 构建响应数据
    essay_data = []
    for essay in essays:
        essay_data.append({
            'id': essay.id,
            'assignment_title': essay.assignment.title if essay.assignment else '自主练习',
            'final_score': essay.final_score,
            'status': essay.status,
            'created_at': essay.created_at.isoformat() if essay.created_at else None
        })
    
    statistics = {
        'total_essays': essay_stats.total_essays or 0,
        'average_score': float(essay_stats.average_score) if essay_stats.average_score else 0,
        'highest_score': float(essay_stats.highest_score) if essay_stats.highest_score else 0,
        'lowest_score': float(essay_stats.lowest_score) if essay_stats.lowest_score else 0
    }
    
    return jsonify({
        'essays': essay_data,
        'statistics': statistics
    })


@students_bp.route('/<int:student_id>/essay-scores-chart')
def student_essay_scores_chart(student_id):
    """获取学生作文得分率折线图数据API"""
    student = StudentProfile.query.get_or_404(student_id)
    
    # 权限检查
    if not _check_student_permission(student):
        abort(403)
    
    # 获取学生的已评分作文记录，按时间排序
    essays = Essay.query.join(
        Enrollment, Essay.enrollment_id == Enrollment.id
    ).filter(
        Enrollment.student_profile_id == student.id,
        Essay.status == 'graded',
        Essay.final_score.isnot(None)
    ).order_by(Essay.created_at).all()
    
    # 构建图表数据
    chart_data = {
        'labels': [],
        'scores': [],
        'titles': []
    }
    
    for essay in essays:
        # 格式化日期作为标签
        date_label = essay.created_at.strftime('%m-%d') if essay.created_at else ''
        chart_data['labels'].append(date_label)
        
        # 使用final_score作为得分率（已经包含了教师评分优先的逻辑）
        chart_data['scores'].append(essay.final_score or 0)
        
        # 作文标题用于tooltip
        title = essay.assignment.title if essay.assignment else '自主练习'
        chart_data['titles'].append(title)
    
    return jsonify(chart_data)


def _check_student_permission(student):
    """检查教师是否有权限访问该学生"""
    if not hasattr(current_user, 'teacher_profile') or not current_user.teacher_profile:
        return False
    
    teacher_classroom_ids = [c.id for c in current_user.teacher_profile.classrooms]
    student_classroom_ids = [e.classroom_id for e in student.enrollments]
    
    # 检查是否有交集
    return bool(set(teacher_classroom_ids) & set(student_classroom_ids))