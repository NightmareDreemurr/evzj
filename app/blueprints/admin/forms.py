from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField, SelectMultipleField, widgets, SelectField, IntegerField, PasswordField
from wtforms.validators import DataRequired, Length, ValidationError, Email, Optional, NumberRange
from sqlalchemy import func
from app.models import GradeLevel, User, School


class PromptStyleForm(FlaskForm):
    """评语风格模板表单"""
    name = StringField('模板名称', validators=[DataRequired(), Length(max=100)])
    style_instructions = TextAreaField('核心Prompt风格指令', validators=[DataRequired()])
    # Use SelectMultipleField to manage grade level checkboxes
    grade_levels = SelectMultipleField('适用年级', coerce=int, validators=[DataRequired(message="请至少选择一个适用年级。")])
    submit = SubmitField('保存模板')

    def set_grade_levels(self, grade_levels_list):
        """Populates the choices for the grade_levels field."""
        self.grade_levels.choices = [(g.id, g.name) for g in grade_levels_list]

class GradeLevelForm(FlaskForm):
    """Form for adding or editing a Grade Level."""
    name = StringField('年级名称', validators=[
        DataRequired(message='年级名称不能为空。'),
        Length(min=2, max=50, message='名称长度必须在2到50个字符之间。')
    ])
    submit = SubmitField('添加年级')

    def validate_name(self, name):
        """Custom validator to check for duplicate grade level names."""
        # Case-insensitive check
        existing_grade = GradeLevel.query.filter(func.lower(GradeLevel.name) == func.lower(name.data)).first()
        if existing_grade:
            raise ValidationError('该年级名称已存在，请使用其他名称。')

class UserForm(FlaskForm):
    """用户管理表单"""
    email = StringField('邮箱', validators=[
        DataRequired(message='邮箱不能为空。'),
        Email(message='请输入有效的邮箱地址。'),
        Length(max=120, message='邮箱长度不能超过120个字符。')
    ])
    username = StringField('用户名', validators=[
        DataRequired(message='用户名不能为空。'),
        Length(min=3, max=100, message='用户名长度必须在3到100个字符之间。')
    ])
    phone = StringField('手机号', validators=[
        Optional(),
        Length(max=100, message='手机号长度不能超过100个字符。')
    ])
    password = PasswordField('密码', validators=[
        Optional(),
        Length(min=6, message='密码长度至少6个字符。')
    ])
    role = SelectField('角色', choices=[
        ('admin', '管理员'),
        ('teacher', '教师'),
        ('student', '学生')
    ], validators=[DataRequired(message='请选择用户角色。')])
    full_name = StringField('姓名', validators=[
        DataRequired(message='姓名不能为空。'),
        Length(max=100, message='姓名长度不能超过100个字符。')
    ])
    nickname = StringField('昵称', validators=[
        Optional(),
        Length(max=100, message='昵称长度不能超过100个字符。')
    ])
    school_id = SelectField('所属学校', coerce=int, validators=[Optional()])
    submit = SubmitField('保存用户')
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        # 动态加载学校选项
        self.school_id.choices = [(0, '请选择学校')] + [(s.id, s.name) for s in School.query.order_by(School.sort_name).all()]
    
    def validate_email(self, email):
        """验证邮箱唯一性"""
        user = User.query.filter_by(email=email.data).first()
        if user and (not hasattr(self, '_obj') or user.id != self._obj.id):
            raise ValidationError('该邮箱已被使用。')
    
    def validate_username(self, username):
        """验证用户名唯一性"""
        user = User.query.filter_by(username=username.data).first()
        if user and (not hasattr(self, '_obj') or user.id != self._obj.id):
            raise ValidationError('该用户名已被使用。')
    
    def validate_phone(self, phone):
        """验证手机号唯一性"""
        if phone.data:
            user = User.query.filter_by(phone=phone.data).first()
            if user and (not hasattr(self, '_obj') or user.id != self._obj.id):
                raise ValidationError('该手机号已被使用。')

class SchoolForm(FlaskForm):
    """学校管理表单"""
    name = StringField('学校名称', validators=[
        DataRequired(message='学校名称不能为空。'),
        Length(min=2, max=150, message='学校名称长度必须在2到150个字符之间。')
    ])
    sort_name = StringField('排序名称', validators=[
        DataRequired(message='排序名称不能为空。'),
        Length(min=2, max=150, message='排序名称长度必须在2到150个字符之间。')
    ])
    submit = SubmitField('保存学校')
    
    def validate_name(self, name):
        """验证学校名称唯一性"""
        school = School.query.filter_by(name=name.data).first()
        if school and (not hasattr(self, '_obj') or school.id != self._obj.id):
            raise ValidationError('该学校名称已存在。')
    
    def validate_sort_name(self, sort_name):
        """验证排序名称唯一性"""
        school = School.query.filter_by(sort_name=sort_name.data).first()
        if school and (not hasattr(self, '_obj') or school.id != self._obj.id):
            raise ValidationError('该排序名称已存在。')

class ClassroomForm(FlaskForm):
    """班级管理表单"""
    school_id = SelectField('所属学校', coerce=int, validators=[
        DataRequired(message='请选择所属学校。')
    ])
    entry_year = IntegerField('入学年份', validators=[
        DataRequired(message='入学年份不能为空。'),
        NumberRange(min=2000, max=2050, message='入学年份必须在2000到2050之间。')
    ])
    graduate_year = IntegerField('毕业年份', validators=[
        DataRequired(message='毕业年份不能为空。'),
        NumberRange(min=2000, max=2060, message='毕业年份必须在2000到2060之间。')
    ])
    class_number = IntegerField('班级编号', validators=[
        DataRequired(message='班级编号不能为空。'),
        NumberRange(min=1, max=99, message='班级编号必须在1到99之间。')
    ])
    class_name = StringField('班级名称', validators=[
        DataRequired(message='班级名称不能为空。'),
        Length(min=2, max=100, message='班级名称长度必须在2到100个字符之间。')
    ])
    submit = SubmitField('保存班级')
    
    def __init__(self, *args, **kwargs):
        super(ClassroomForm, self).__init__(*args, **kwargs)
        # 动态加载学校选项
        self.school_id.choices = [(s.id, s.name) for s in School.query.order_by(School.sort_name).all()]
    
    def validate_graduate_year(self, graduate_year):
        """验证毕业年份必须大于入学年份"""
        if self.entry_year.data and graduate_year.data:
            if graduate_year.data <= self.entry_year.data:
                raise ValidationError('毕业年份必须大于入学年份。')