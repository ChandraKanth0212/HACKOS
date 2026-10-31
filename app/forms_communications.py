from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class AnnouncementForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    body = TextAreaField("Content", validators=[DataRequired(), Length(max=10000)])
    status = SelectField(
        "Publication status",
        choices=[("draft", "Draft"), ("published", "Published")],
    )
    submit = SubmitField("Save announcement")


class ScheduleItemForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(
        "Description", validators=[Optional(), Length(max=10000)]
    )
    location = StringField("Location", validators=[Optional(), Length(max=240)])
    starts_at = StringField("Starts", validators=[DataRequired()])
    ends_at = StringField("Ends", validators=[DataRequired()])
    status = SelectField(
        "Publication status",
        choices=[("draft", "Draft"), ("published", "Published")],
    )
    submit = SubmitField("Save schedule item")
