from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.fields import DateTimeLocalField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from app.models import PromptStyleTemplate
from flask_wtf.file import FileField, FileAllowed

def get_prompt_styles():
    """Callable for QuerySelectField to get all prompt style templates."""
    return PromptStyleTemplate.query.order_by(PromptStyleTemplate.name).all()

class EssayAssignmentForm(FlaskForm):
    """作文作业布置表单"""
    title = StringField('作业标题', validators=[DataRequired(), Length(1, 200)])
    description = TextAreaField('作业要求', validators=[Optional(), Length(max=5000)])
    due_date = DateTimeLocalField('截止日期', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    
    grading_standard = QuerySelectField(
        '评分标准',
        get_label='title',
        allow_blank=False,
        validators=[DataRequired()]
    )
    
    prompt_style_template = QuerySelectField(
        '指定评语风格 (可选)',
        query_factory=get_prompt_styles,
        get_label='name',
        allow_blank=True,
        blank_text='-- 使用年级默认风格 --'
    )

    classrooms = QuerySelectMultipleField(
        '发布到班级',
        get_label='class_name',
        allow_blank=True
    )
    
    students = QuerySelectMultipleField(
        '发布给个别学生',
        get_label=lambda s: s.user.full_name, # 显示学生的姓名
        allow_blank=True
    )

    submit = SubmitField('发布作业')

class SubmissionForm(FlaskForm):
    """学生提交作业表单"""
    content = TextAreaField('作文内容', validators=[Optional(), Length(min=20, max=15000)])
    image = FileField('上传作文图片', validators=[
        Optional(), 
        FileAllowed(['jpg', 'png', 'jpeg'], '只支持上传图片格式 (jpg, png, jpeg)!')
    ])
    submit = SubmitField('提交作业')

    def validate(self, **kwargs):
        """确保至少提交了一项内容。"""
        if not super().validate(**kwargs):
            return False
        if not self.content.data and not self.image.data:
            msg = '请至少提供作文内容或上传一张图片。'
            self.content.errors.append(msg)
            self.image.errors.append(msg)
            return False
        return True

class BatchConfirmationForm(FlaskForm):
    """一个空的表单，主要用于在批量确认页面提供CSRF保护。"""
    submit = SubmitField('确认全班匹配结果') 