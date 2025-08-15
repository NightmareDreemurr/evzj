from datetime import datetime, date, time
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required
from . import admin_bp
from app.decorators import admin_required
from app.models import (PromptStyleTemplate, GradeLevel, PromptStyleGradeLevelDefault, 
                       User, AdminProfile, TeacherProfile, StudentProfile, 
                       School, Classroom, Enrollment, EssayAssignment, Essay, 
                       GradingStandard, db)
from .forms import PromptStyleForm, GradeLevelForm, UserForm, SchoolForm, ClassroomForm
from werkzeug.security import generate_password_hash
from sqlalchemy import func, desc

# 应用装饰器到整个蓝图
@admin_bp.before_request
@login_required
@admin_required
def before_request():
    """保护此蓝图下的所有路由"""
    pass

@admin_bp.route('/dashboard')
def dashboard():
    # 获取统计数据
    stats = {
        'total_users': User.query.count(),
        'total_teachers': TeacherProfile.query.count(),
        'total_students': StudentProfile.query.count(),
        'total_schools': School.query.count(),
        'total_classrooms': Classroom.query.count(),
        'total_assignments': EssayAssignment.query.count(),
        'total_essays': Essay.query.count(),
        'recent_users': User.query.order_by(desc(User.created_at)).limit(5).all()
    }
    return render_template('admin/dashboard.html', stats=stats)

@admin_bp.route('/standards')
def manage_standards():
    # This now redirects to the new standards blueprint
    return redirect(url_for('standards.manage_standards'))

# --- Prompt Style Template CRUD ---

@admin_bp.route('/prompt-styles', methods=['GET'])
@login_required
@admin_required
def manage_prompt_styles():
    """List all prompt style templates."""
    # Query to only get templates that have at least one enabled grade level associated with them.
    templates = PromptStyleTemplate.query.join(
        PromptStyleTemplate.grade_level_associations
    ).join(
        PromptStyleGradeLevelDefault.grade_level
    ).filter(
        GradeLevel.is_enabled == True
    ).distinct().order_by(PromptStyleTemplate.name).all()
    
    return render_template('admin/prompt_styles.html', templates=templates)

@admin_bp.route('/prompt-styles/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_prompt_style():
    form = PromptStyleForm()
    all_grade_levels = GradeLevel.query.filter_by(is_enabled=True).order_by(GradeLevel.id).all()
    form.set_grade_levels(all_grade_levels)

    if form.validate_on_submit():
        new_template = PromptStyleTemplate(
            name=form.name.data,
            style_instructions=form.style_instructions.data
        )
        
        for grade_id in form.grade_levels.data:
            is_default = request.form.get(f'default_for_{grade_id}') == 'true'
            
            if is_default:
                PromptStyleGradeLevelDefault.query.filter_by(
                    grade_level_id=grade_id, is_default=True
                ).update({"is_default": False})

            assoc = PromptStyleGradeLevelDefault(grade_level_id=grade_id, is_default=is_default)
            new_template.grade_level_associations.append(assoc)
            
        db.session.add(new_template)
        db.session.commit()
        flash('新的评语风格模板已成功创建。', 'success')
        return redirect(url_for('admin.manage_prompt_styles'))
        
    return render_template('admin/create_prompt_style.html', form=form, title='创建评语风格模板')


@admin_bp.route('/prompt-styles/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_prompt_style(template_id):
    template = PromptStyleTemplate.query.get_or_404(template_id)
    form = PromptStyleForm(obj=template)
    all_grade_levels = GradeLevel.query.filter_by(is_enabled=True).order_by(GradeLevel.id).all()
    form.set_grade_levels(all_grade_levels)

    if form.validate_on_submit():
        template.name = form.name.data
        template.style_instructions = form.style_instructions.data
        
        # --- Sync Grade Level Associations ---
        selected_grade_ids = set(form.grade_levels.data)
        current_associations = {assoc.grade_level_id: assoc for assoc in template.grade_level_associations}
        
        # Remove unchecked
        for grade_id in current_associations:
            if grade_id not in selected_grade_ids:
                db.session.delete(current_associations[grade_id])

        # Add new or update existing
        for grade_id in selected_grade_ids:
            is_default = request.form.get(f'default_for_{grade_id}') == 'true'
            
            if is_default:
                PromptStyleGradeLevelDefault.query.filter(
                    PromptStyleGradeLevelDefault.grade_level_id == grade_id,
                    PromptStyleGradeLevelDefault.prompt_style_template_id != template.id
                ).update({"is_default": False})

            if grade_id in current_associations:
                current_associations[grade_id].is_default = is_default
            else:
                new_assoc = PromptStyleGradeLevelDefault(prompt_style_template_id=template.id, grade_level_id=grade_id, is_default=is_default)
                db.session.add(new_assoc)
        
        db.session.commit()
        flash('评语风格模板已更新。', 'success')
        return redirect(url_for('admin.manage_prompt_styles'))

    # --- Pre-populate form for GET request ---
    form.grade_levels.data = [assoc.grade_level_id for assoc in template.grade_level_associations]
    default_grade_ids = {assoc.grade_level_id for assoc in template.grade_level_associations if assoc.is_default}

    return render_template('admin/edit_prompt_style.html', 
                           form=form, 
                           template=template, 
                           title='编辑评语风格模板',
                           default_grade_ids=default_grade_ids)

@admin_bp.route('/grade-levels', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_grade_levels():
    """Route to manage grade levels (add, delete, enable/disable)."""
    form = GradeLevelForm()
    if form.validate_on_submit():
        new_grade = GradeLevel(name=form.name.data, is_enabled=True) # New grades are enabled by default
        db.session.add(new_grade)
        try:
            db.session.commit()
            flash(f"年级 '{new_grade.name}' 已成功添加。", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"添加年级时出错: {e}", "danger")
        return redirect(url_for('admin.manage_grade_levels'))
    
    # 获取所有年级数据
    grades = GradeLevel.query.order_by(GradeLevel.id).all()
    
    return render_template('admin/grade_levels.html', form=form, grades=grades)

# --- 用户管理 ---

@admin_bp.route('/users')
def users():
    """用户管理页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    role_filter = request.args.get('role', '', type=str)
    
    query = User.query
    
    # 搜索过滤
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.full_name.contains(search),
                User.phone.contains(search)
            )
        )
    
    # 角色过滤
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    users = query.order_by(desc(User.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html', 
                         users=users, 
                         search=search, 
                         role_filter=role_filter)

@admin_bp.route('/users/create', methods=['GET', 'POST'])
def create_user():
    """创建用户"""
    form = UserForm()
    if form.validate_on_submit():
        try:
            # 创建用户
            user = User(
                email=form.email.data,
                username=form.username.data,
                phone=form.phone.data,
                password_hash=generate_password_hash(form.password.data),
                role=form.role.data,
                full_name=form.full_name.data,
                nickname=form.nickname.data
            )
            db.session.add(user)
            db.session.flush()  # 获取user.id
            
            # 根据角色创建对应的profile
            if user.role == 'admin':
                profile = AdminProfile(user_id=user.id)
                db.session.add(profile)
            elif user.role == 'teacher':
                profile = TeacherProfile(
                    user_id=user.id,
                    school_id=form.school_id.data if form.school_id.data else None
                )
                db.session.add(profile)
            elif user.role == 'student':
                profile = StudentProfile(user_id=user.id)
                db.session.add(profile)
            
            db.session.commit()
            flash(f'用户 {user.username} 创建成功！', 'success')
            return redirect(url_for('admin.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建用户失败：{str(e)}', 'error')
    
    return render_template('admin/create_user.html', form=form)

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    """编辑用户"""
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        try:
            user.email = form.email.data
            user.username = form.username.data
            user.phone = form.phone.data
            user.full_name = form.full_name.data
            user.nickname = form.nickname.data
            
            # 如果提供了新密码，则更新密码
            if form.password.data:
                user.password_hash = generate_password_hash(form.password.data)
            
            # 处理角色变更
            old_role = user.role
            new_role = form.role.data
            
            if old_role != new_role:
                # 删除旧的profile
                if old_role == 'admin' and user.admin_profile:
                    db.session.delete(user.admin_profile)
                elif old_role == 'teacher' and user.teacher_profile:
                    db.session.delete(user.teacher_profile)
                elif old_role == 'student' and user.student_profile:
                    db.session.delete(user.student_profile)
                
                # 创建新的profile
                user.role = new_role
                if new_role == 'admin':
                    profile = AdminProfile(user_id=user.id)
                    db.session.add(profile)
                elif new_role == 'teacher':
                    profile = TeacherProfile(
                        user_id=user.id,
                        school_id=form.school_id.data if form.school_id.data else None
                    )
                    db.session.add(profile)
                elif new_role == 'student':
                    profile = StudentProfile(user_id=user.id)
                    db.session.add(profile)
            
            db.session.commit()
            flash(f'用户 {user.username} 更新成功！', 'success')
            return redirect(url_for('admin.manage_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新用户失败：{str(e)}', 'error')
    
    return render_template('admin/edit_user.html', form=form, user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    """删除用户"""
    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f'用户 {user.username} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除用户失败：{str(e)}', 'error')
    
    return redirect(url_for('admin.manage_users'))

# --- 学校管理 ---

@admin_bp.route('/schools')
def schools():
    """学校管理页面"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)
    
    query = School.query
    
    if search:
        query = query.filter(
            db.or_(
                School.name.contains(search),
                School.sort_name.contains(search)
            )
        )
    
    schools = query.order_by(School.sort_name).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/schools.html', 
                         schools=schools, 
                         search=search)

@admin_bp.route('/schools/create', methods=['GET', 'POST'])
def create_school():
    """创建学校"""
    form = SchoolForm()
    if form.validate_on_submit():
        try:
            school = School(
                name=form.name.data,
                sort_name=form.sort_name.data
            )
            db.session.add(school)
            db.session.commit()
            flash(f'学校 {school.name} 创建成功！', 'success')
            return redirect(url_for('admin.manage_schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建学校失败：{str(e)}', 'error')
    
    return render_template('admin/create_school.html', form=form)

@admin_bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
def edit_school(school_id):
    """编辑学校"""
    school = School.query.get_or_404(school_id)
    form = SchoolForm(obj=school)
    
    if form.validate_on_submit():
        try:
            school.name = form.name.data
            school.sort_name = form.sort_name.data
            db.session.commit()
            flash(f'学校 {school.name} 更新成功！', 'success')
            return redirect(url_for('admin.manage_schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新学校失败：{str(e)}', 'error')
    
    return render_template('admin/edit_school.html', form=form, school=school)

@admin_bp.route('/schools/<int:school_id>/delete', methods=['POST'])
def delete_school(school_id):
    """删除学校"""
    school = School.query.get_or_404(school_id)
    try:
        db.session.delete(school)
        db.session.commit()
        flash(f'学校 {school.name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除学校失败：{str(e)}', 'error')
    
    return redirect(url_for('admin.manage_schools'))

# --- 班级管理 ---

@admin_bp.route('/classrooms')
def classrooms():
    """班级管理页面"""
    page = request.args.get('page', 1, type=int)
    school_filter = request.args.get('school', '', type=str)
    
    query = Classroom.query.join(School)
    
    if school_filter:
        query = query.filter(School.id == school_filter)
    
    classrooms = query.order_by(School.sort_name, Classroom.entry_year, Classroom.class_number).paginate(
        page=page, per_page=20, error_out=False
    )
    
    schools = School.query.order_by(School.sort_name).all()
    
    return render_template('admin/classrooms.html', 
                         classrooms=classrooms, 
                         schools=schools,
                         school_filter=school_filter)

@admin_bp.route('/classrooms/create', methods=['GET', 'POST'])
def create_classroom():
    """创建班级"""
    form = ClassroomForm()
    if form.validate_on_submit():
        try:
            classroom = Classroom(
                school_id=form.school_id.data,
                entry_year=form.entry_year.data,
                graduate_year=form.graduate_year.data,
                class_number=form.class_number.data,
                class_name=form.class_name.data
            )
            db.session.add(classroom)
            db.session.commit()
            flash(f'班级 {classroom.class_name} 创建成功！', 'success')
            return redirect(url_for('admin.manage_classrooms'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建班级失败：{str(e)}', 'error')
    
    return render_template('admin/create_classroom.html', form=form)

@admin_bp.route('/classrooms/<int:classroom_id>/edit', methods=['GET', 'POST'])
def edit_classroom(classroom_id):
    """编辑班级"""
    classroom = Classroom.query.get_or_404(classroom_id)
    form = ClassroomForm(obj=classroom)
    
    if form.validate_on_submit():
        try:
            classroom.school_id = form.school_id.data
            classroom.entry_year = form.entry_year.data
            classroom.graduate_year = form.graduate_year.data
            classroom.class_number = form.class_number.data
            classroom.class_name = form.class_name.data
            db.session.commit()
            flash(f'班级 {classroom.class_name} 更新成功！', 'success')
            return redirect(url_for('admin.manage_classrooms'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新班级失败：{str(e)}', 'error')
    
    return render_template('admin/edit_classroom.html', form=form, classroom=classroom)

@admin_bp.route('/classrooms/<int:classroom_id>/delete', methods=['POST'])
def delete_classroom(classroom_id):
    """删除班级"""
    classroom = Classroom.query.get_or_404(classroom_id)
    try:
        db.session.delete(classroom)
        db.session.commit()
        flash(f'班级 {classroom.class_name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除班级失败：{str(e)}', 'error')
    
    return redirect(url_for('admin.manage_classrooms'))

# --- 作业管理 ---

@admin_bp.route('/assignments')
def assignments():
    """作业管理页面"""
    page = request.args.get('page', 1, type=int)
    teacher_filter = request.args.get('teacher', '', type=str)
    
    query = EssayAssignment.query.join(TeacherProfile).join(User)
    
    if teacher_filter:
        query = query.filter(TeacherProfile.id == teacher_filter)
    
    assignments = query.order_by(desc(EssayAssignment.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    teachers = TeacherProfile.query.join(User).order_by(User.full_name).all()
    
    return render_template('admin/assignments.html', 
                         assignments=assignments, 
                         teachers=teachers, 
                         teacher_filter=teacher_filter,
                         today=datetime.combine(date.today(), time.min))

# --- 作文管理 ---

@admin_bp.route('/essays')
def essays():
    """作文管理页面"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '', type=str)
    
    query = Essay.query.join(Enrollment).join(StudentProfile).join(User)
    
    if status_filter:
        query = query.filter(Essay.status == status_filter)
    
    pagination = query.order_by(desc(Essay.created_at)).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # 获取所有状态用于过滤
    statuses = db.session.query(Essay.status).distinct().all()
    statuses = [status[0] for status in statuses if status[0]]
    
    return render_template('admin/essays.html', 
                         pagination=pagination,
                         essays=pagination.items, 
                         statuses=statuses,
                         status_filter=status_filter)

@admin_bp.route('/essays/<int:essay_id>/detail')
def essay_detail(essay_id):
    """显示单个作文的详情"""
    essay = db.session.get(Essay, essay_id)
    if not essay:
        flash('作文不存在', 'error')
        return redirect(url_for('admin.essays'))
    
    return render_template('admin/essay_detail.html', essay=essay)

# --- 系统统计 ---

@admin_bp.route('/system-stats')
def system_stats():
    """系统统计页面"""
    # 统计数据
    stats = {
        'total_users': User.query.count(),
        'total_admins': User.query.filter_by(role='admin').count(),
        'total_teachers': User.query.filter_by(role='teacher').count(),
        'total_students': User.query.filter_by(role='student').count(),
        'total_schools': School.query.count(),
        'total_classrooms': Classroom.query.count(),
        'total_enrollments': Enrollment.query.count(),
        'total_assignments': EssayAssignment.query.count(),
        'total_essays': Essay.query.count(),
        'graded_essays': Essay.query.filter(Essay.status == 'graded').count(),
        'pending_essays': Essay.query.filter(Essay.status == 'pending').count(),
        'total_standards': GradingStandard.query.count(),
        'active_standards': GradingStandard.query.filter_by(is_active=True).count(),
        'new_users_today': 0,  # 可以后续实现
        'avg_users_per_school': 0,  # 可以后续实现
        'avg_students_per_class': 0,  # 可以后续实现
    }
    
    return render_template('admin/system_stats.html', stats=stats)

    all_grades = GradeLevel.query.order_by(GradeLevel.id).all()
    return render_template('admin/grade_levels.html', 
                           grades=all_grades, 
                           form=form, 
                           title="年级管理")

@admin_bp.route('/grade-levels/<int:grade_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_grade_level(grade_id):
    """Toggle the is_enabled status of a grade level."""
    grade = GradeLevel.query.get_or_404(grade_id)
    grade.is_enabled = not grade.is_enabled
    try:
        db.session.commit()
        status = "启用" if grade.is_enabled else "禁用"
        flash(f"年级 '{grade.name}' 已被设置为 {status} 状态。", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"更新年级状态时出错: {e}", "danger")
    return redirect(url_for('admin.manage_grade_levels'))

@admin_bp.route('/grade-levels/<int:grade_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_grade_level(grade_id):
    """Delete a grade level."""
    grade = GradeLevel.query.get_or_404(grade_id)
    
    # Prevent deletion if the grade is in use
    if grade.standards.first() or grade.prompt_style_associations.first():
        flash(f"无法删除年级 '{grade.name}'，因为它已被用于评分标准或评语风格中。", "danger")
        return redirect(url_for('admin.manage_grade_levels'))

    db.session.delete(grade)
    try:
        db.session.commit()
        flash(f"年级 '{grade.name}' 已被成功删除。", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"删除年级时出错: {e}", "danger")
    return redirect(url_for('admin.manage_grade_levels'))


@admin_bp.route('/prompt-styles/<int:template_id>/delete', methods=['POST'])
def delete_prompt_style(template_id):
    """Delete a prompt style template."""
    template = PromptStyleTemplate.query.get_or_404(template_id)
    db.session.delete(template)
    db.session.commit()
    flash('评语风格模板已删除。', 'success')
    return redirect(url_for('admin.manage_prompt_styles'))