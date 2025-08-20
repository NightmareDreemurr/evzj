from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, Email
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models import Classroom

class StudentForm(FlaskForm):
    """学生信息表单"""
    full_name = StringField('学生姓名', validators=[DataRequired(), Length(1, 100)])
    email = StringField('邮箱地址', validators=[DataRequired(), Email()])
    phone = StringField('手机号码', validators=[Optional(), Length(11, 11)])
    classroom = QuerySelectField(
        '所属班级',
        get_label='class_name',
        allow_blank=False,
        validators=[DataRequired()]
    )
    student_number = StringField('学号', validators=[Optional(), Length(1, 50)])
    status = SelectField('状态', 
                        choices=[('active', '在读'), ('graduated', '毕业'), 
                                ('withdrawn', '退学'), ('transferred', '转学')],
                        default='active')
    submit = SubmitField('保存')

class StudentSearchForm(FlaskForm):
    """学生搜索表单"""
    q = StringField('搜索关键词', validators=[Optional()], 
                   render_kw={'placeholder': '输入学生姓名或学号'})
    classroom_id = QuerySelectField(
        '班级筛选',
        get_label='class_name',
        allow_blank=True,
        blank_text='-- 所有班级 --'
    )
    status = SelectField('状态筛选',
                        choices=[('', '-- 所有状态 --'),
                                ('active', '在读'), 
                                ('graduated', '毕业'),
                                ('withdrawn', '退学'), 
                                ('transferred', '转学')],
                        default='')
    submit = SubmitField('搜索')

class DeleteStudentForm(FlaskForm):
    """删除学生确认表单"""
    student_id = HiddenField(validators=[DataRequired()])
    submit = SubmitField('确认删除')