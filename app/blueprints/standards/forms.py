from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length
from wtforms_sqlalchemy.fields import QuerySelectField, QuerySelectMultipleField
from app.models import GradeLevel, Tag

def get_enabled_grade_levels():
    """Returns a list of enabled grade levels for form choices."""
    return GradeLevel.query.filter_by(is_enabled=True).order_by(GradeLevel.id).all()

def get_tags():
    # This provides the initial list of existing tags for the dropdown
    return Tag.query.all()

class PatchedQuerySelectMultipleField(QuerySelectMultipleField):
    """
    A patched field to handle creating new tags on the fly.
    When the form is submitted, it can contain a mix of existing tag IDs
    and new tag names (strings). This field handles both cases.
    """
    def pre_validate(self, form):
        """
        Override pre_validate to allow new tags to be created.
        The default validator checks if all submitted values exist in the
        query, which we don't want for new tags.
        """
        if self.data:
            # Get all existing PKs from the query
            query_pks = [str(pk) for pk, obj in self._get_object_list()]
            
            # Check only the existing tags (those with numeric PKs)
            for value in self.object_data:
                if str(value.id) not in query_pks:
                     raise ValueError(self.gettext("Not a valid choice"))

    def process_formdata(self, valuelist):
        if valuelist:
            # Get existing tags from the DB
            super().process_formdata(valuelist)
            
            new_tags = []
            for value in valuelist:
                # A new tag will not be a valid integer PK
                if not value.isdigit():
                    name = value.strip()
                    if name:
                        # Check if a tag with this name already exists
                        tag = Tag.query.filter(Tag.name.ilike(name)).first()
                        if not tag:
                            # Create a new tag if it doesn't exist
                            tag = Tag(name=name)
                        if tag not in self.data:
                             new_tags.append(tag)
            
            self.data.extend(new_tags)


class GradingStandardForm(FlaskForm):
    """评分标准表单"""
    title = StringField('标准标题', validators=[DataRequired(), Length(1, 200)])
    grade_level = QuerySelectField('适用年级', query_factory=get_enabled_grade_levels, get_label='name', allow_blank=False)
    tags = PatchedQuerySelectMultipleField(
        '标签',
        query_factory=get_tags,
        get_label='name',
        allow_blank=True
    )
    submit = SubmitField('保存') 