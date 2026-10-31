from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class TeamForm(FlaskForm):
    name = StringField("Team name", validators=[DataRequired(), Length(max=160)])
    problem_statement = TextAreaField(
        "Problem statement", validators=[Optional(), Length(max=4000)]
    )
    status = SelectField(
        "Status",
        choices=[("active", "Active"), ("withdrawn", "Withdrawn")],
    )
    submit = SubmitField("Save team")


class MembershipForm(FlaskForm):
    participant_id = StringField("Participant ID", validators=[DataRequired()])
    member_role = StringField("Member role", validators=[Optional(), Length(max=80)])
    submit = SubmitField("Add member")


class TransferForm(MembershipForm):
    team_id = StringField("Destination team ID", validators=[DataRequired()])
    submit = SubmitField("Transfer member")
