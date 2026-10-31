from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.services.participants import REGISTRATION_STATUSES


class ParticipantForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=160)])
    email = StringField("Email", validators=[DataRequired(), Length(max=320)])
    phone = StringField("Phone", validators=[Optional(), Length(max=40)])
    institution = StringField(
        "Institution", validators=[Optional(), Length(max=200)]
    )
    registration_status = SelectField(
        "Registration status",
        choices=[
            (status, status.replace("_", " ").capitalize())
            for status in REGISTRATION_STATUSES
        ],
    )
    submit = SubmitField("Save participant")


class RegistrationForm(ParticipantForm):
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=128)]
    )
