from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class SubmissionForm(FlaskForm):
    project_title = StringField(
        "Project title", validators=[DataRequired(), Length(max=240)]
    )
    description = TextAreaField(
        "Project description", validators=[DataRequired(), Length(max=12000)]
    )
    repository_url = StringField(
        "Repository URL", validators=[Optional(), Length(max=2000)]
    )
    demo_url = StringField("Demo URL", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Save submission")
