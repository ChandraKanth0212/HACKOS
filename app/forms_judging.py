from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class AssignmentForm(FlaskForm):
    submission_id = SelectField("Submission", validators=[DataRequired()])
    judge_id = SelectField("Judge", validators=[DataRequired()])
    submit = SubmitField("Assign judge")


class EvaluationForm(FlaskForm):
    comments = TextAreaField("Overall comments", validators=[Optional(), Length(max=10000)])
    submit_action = StringField(default="draft")
    submit = SubmitField("Save evaluation")
