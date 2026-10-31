from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class AttendanceCheckInForm(FlaskForm):
    participant_code = StringField(
        "Participant code", validators=[DataRequired(), Length(max=160)]
    )
    operation_id = StringField("Operation ID", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Check in")


class QRCheckInForm(FlaskForm):
    token = StringField("QR credential", validators=[DataRequired(), Length(max=512)])
    operation_id = StringField("Operation ID", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Check in QR")
