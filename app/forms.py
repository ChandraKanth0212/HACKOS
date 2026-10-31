from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

from app.services.events import EVENT_STATUSES


class EventForm(FlaskForm):
    name = StringField("Event name", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=4000)])
    venue = StringField("Venue", validators=[Optional(), Length(max=240)])
    timezone = StringField("Timezone", validators=[DataRequired(), Length(max=64)])
    starts_at = StringField("Event starts", validators=[Optional()])
    ends_at = StringField("Event ends", validators=[Optional()])
    registration_starts_at = StringField("Registration starts", validators=[Optional()])
    registration_ends_at = StringField("Registration ends", validators=[Optional()])
    capacity = StringField("Participant capacity", validators=[Optional()])
    team_size_min = StringField("Minimum team size", validators=[Optional()])
    team_size_max = StringField("Maximum team size", validators=[Optional()])
    status = SelectField(
        "Status", choices=[(status, status.capitalize()) for status in EVENT_STATUSES]
    )
    submit = SubmitField("Save event")
