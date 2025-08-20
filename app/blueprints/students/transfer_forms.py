from flask_wtf import FlaskForm
from wtforms import SubmitField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length
from wtforms_sqlalchemy.fields import QuerySelectField
from app.models import Classroom

class StudentTransferForm(FlaskForm):
    """学生班级转移表单"""
    student_id = HiddenField(validators=[DataRequired()])
    target_classroom = QuerySelectField(
        '目标班级',
        get_label='class_name',
        allow_blank=False,
        validators=[DataRequired(message='请选择目标班级')]
    )
    reason = TextAreaField(
        '转移原因', 
        validators=[Optional(), Length(max=500)],
        render_kw={'placeholder': '请简要说明转移原因（可选）', 'rows': 3}
    )
    submit = SubmitField('确认转移')