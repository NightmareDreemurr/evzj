from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    """登录表单"""
    account = StringField('账号', validators=[DataRequired("请输入您的账号。"), Length(1, 120)])
    password = PasswordField('密码', validators=[DataRequired("请输入您的密码。")])
    submit = SubmitField('登录')

class RegistrationForm(FlaskForm):
    """注册表单"""
    email = StringField('邮箱', validators=[DataRequired(), Length(1, 120), Email()])
    username = StringField('用户名', validators=[DataRequired(), Length(1, 100)])
    phone = StringField('手机号', validators=[Length(0, 100)])
    # 新增：角色选择字段
    role = SelectField('角色', choices=[
        ('student', '学生'),
        ('teacher', '教师'),
        ('admin', '管理员')
    ], validators=[DataRequired()])
    password = PasswordField('密码', validators=[
        DataRequired(), EqualTo('password2', message='两次输入的密码必须一致。')
    ])
    password2 = PasswordField('确认密码', validators=[DataRequired()])
    submit = SubmitField('注册')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('该邮箱已被注册。')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('该用户名已被使用。')

    def validate_phone(self, field):
        if field.data and User.query.filter_by(phone=field.data).first():
            raise ValidationError('该手机号已被注册。') 