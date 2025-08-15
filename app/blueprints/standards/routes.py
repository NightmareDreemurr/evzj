from flask import render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from app.models import db, GradingStandard, GradeLevel, Tag, Dimension, Rubric, User
from .forms import GradingStandardForm
from . import standards_bp
import json
import re
from collections import defaultdict
from sqlalchemy import or_

@standards_bp.before_request
@login_required
def before_request():
    """Protect all routes in this blueprint and check for teacher or admin role."""
    if current_user.role not in ['admin', 'teacher']:
        abort(403)

def parse_dynamic_form(form_data):
    # ... (rest of the file is the same)
    dimensions_data = defaultdict(lambda: {'rubrics': defaultdict(dict)})
    
    dim_pattern = re.compile(r'dimensions-(\d+)-name')
    dim_max_score_pattern = re.compile(r'dimensions-(\d+)-max_score')
    rubric_pattern = re.compile(r'dimensions-(\d+)-rubrics-(\d+)-(\w+)')

    for key, value in form_data.items():
        match = dim_pattern.match(key)
        if match:
            dim_index = match.group(1)
            dimensions_data[dim_index]['name'] = value
            continue

        match = dim_max_score_pattern.match(key)
        if match:
            dim_index = match.group(1)
            dimensions_data[dim_index]['max_score'] = value
            continue
            
        match = rubric_pattern.match(key)
        if match:
            dim_index, rubric_index, field_name = match.groups()
            dimensions_data[dim_index]['rubrics'][rubric_index][field_name] = value
            
    sorted_dimensions = sorted(dimensions_data.items(), key=lambda i: int(i[0]))
    
    result = []
    for _, dim_data in sorted_dimensions:
        sorted_rubrics = sorted(dim_data['rubrics'].items(), key=lambda i: int(i[0]))
        dim_data['rubrics'] = [rubric_data for _, rubric_data in sorted_rubrics]
        result.append(dim_data)
        
    return result

@standards_bp.route('/')
def manage_standards():
    query = GradingStandard.query
    if current_user.role == 'teacher':
        # Teachers can see system standards (no creator) and their own
        query = query.filter(or_(GradingStandard.creator_id == None, GradingStandard.creator_id == current_user.id))
    
    standards = query.order_by(GradingStandard.grade_level_id, GradingStandard.id).all()
    return render_template('standards/standards.html', standards=standards)

@standards_bp.route('/add', methods=['GET', 'POST'])
def add_standard():
    form = GradingStandardForm()
    if form.validate_on_submit():
        try:
            new_standard = GradingStandard(
                title=form.title.data,
                grade_level_id=form.grade_level.data.id,
                total_score=request.form.get('total_score', 0, type=int)
            )
            new_standard.creator_id = current_user.id  # Set creator
            new_standard.tags = form.tags.data
            db.session.add(new_standard)
            db.session.flush()

            parsed_dimensions = parse_dynamic_form(request.form)
            if not parsed_dimensions:
                raise ValueError("至少需要一个维度。")

            for dim_data in parsed_dimensions:
                if not dim_data.get('name'): continue
                
                new_dimension = Dimension(
                    name=dim_data['name'],
                    max_score=int(float(dim_data['max_score'])),
                    standard_id=new_standard.id
                )
                db.session.add(new_dimension)
                db.session.flush()
                
                if not dim_data.get('rubrics'):
                    raise ValueError(f"维度 '{dim_data['name']}' 至少需要一个评分标准。")

                for rubric_data in dim_data['rubrics']:
                    new_rubric = Rubric(
                        level_name=rubric_data['level_name'],
                        description=rubric_data['description'],
                        min_score=float(rubric_data['min_score']),
                        max_score=float(rubric_data['max_score']),
                        dimension_id=new_dimension.id
                    )
                    db.session.add(new_rubric)

            db.session.commit()
            flash('成功创建评分标准。', 'success')
            return redirect(url_for('standards.manage_standards'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating standard: {e}', 'danger')
            
    return render_template('standards/add_standard.html', form=form)

@standards_bp.route('/edit/<int:standard_id>', methods=['GET', 'POST'])
def edit_standard(standard_id):
    standard = GradingStandard.query.get_or_404(standard_id)
    
    # Permission Check
    if current_user.role != 'admin' and standard.creator_id != current_user.id:
        abort(403)

    form = GradingStandardForm(obj=standard)
    if form.validate_on_submit():
        try:
            standard.title = form.title.data
            standard.grade_level_id = form.grade_level.data.id
            standard.total_score = request.form.get('total_score', 0, type=int)
            standard.tags = form.tags.data
            
            for dim in standard.dimensions:
                db.session.delete(dim)
            db.session.flush()

            parsed_dimensions = parse_dynamic_form(request.form)
            if not parsed_dimensions:
                raise ValueError("至少需要一个维度。")

            for dim_data in parsed_dimensions:
                if not dim_data.get('name'): continue
                
                new_dimension = Dimension(
                    name=dim_data['name'],
                    max_score=int(float(dim_data['max_score'])),
                    standard_id=standard.id
                )
                db.session.add(new_dimension)
                db.session.flush()
                
                if not dim_data.get('rubrics'):
                    raise ValueError(f"维度 '{dim_data['name']}' 至少需要一个评分标准。")

                for rubric_data in dim_data['rubrics']:
                    new_rubric = Rubric(
                        level_name=rubric_data['level_name'],
                        description=rubric_data['description'],
                        min_score=float(rubric_data['min_score']),
                        max_score=float(rubric_data['max_score']),
                        dimension_id=new_dimension.id
                    )
                    db.session.add(new_rubric)
            
            db.session.commit()
            flash('成功更新评分标准。', 'success')
            return redirect(url_for('standards.manage_standards'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating standard: {e}', 'danger')

    standard_json = {
        'id': standard.id,
        'title': standard.title,
        'grade_level_id': standard.grade_level_id,
        'tags': [{'id': t.id, 'name': t.name} for t in standard.tags],
        'total_score': standard.total_score,
        'dimensions': [
            {
                'name': dim.name,
                'max_score': dim.max_score,
                'rubrics': [
                    {
                        'level_name': r.level_name,
                        'description': r.description,
                        'min_score': r.min_score,
                        'max_score': r.max_score
                    } for r in dim.rubrics
                ]
            } for dim in standard.dimensions
        ]
    }
    
    return render_template('standards/edit_standard.html', form=form, standard=standard, standard_json=jsonify(standard_json).get_data(as_text=True))

@standards_bp.route('/delete/<int:standard_id>', methods=['POST'])
def delete_standard(standard_id):
    standard = GradingStandard.query.get_or_404(standard_id)
    # Permission Check
    if current_user.role != 'admin' and standard.creator_id != current_user.id:
        abort(403)
        
    try:
        db.session.delete(standard)
        db.session.commit()
        flash(f'Grading standard "{standard.title}" has been deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting standard: {e}', 'danger')
    return redirect(url_for('standards.manage_standards'))

@standards_bp.route('/toggle/<int:standard_id>', methods=['POST'])
def toggle_standard_status(standard_id):
    standard = GradingStandard.query.get_or_404(standard_id)
    # Permission Check: Only admins can activate/deactivate standards
    if current_user.role != 'admin':
        abort(403)
        
    try:
        standard.is_active = not standard.is_active
        db.session.commit()
        status = "activated" if standard.is_active else "deactivated"
        flash(f'Grading standard "{standard.title}" has been {status}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error toggling status: {e}', 'danger')
    return redirect(url_for('standards.manage_standards')) 