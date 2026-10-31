from sqlalchemy import Index, text

from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Team(db.Model):
    __tablename__ = "teams"
    __table_args__ = (
        db.UniqueConstraint("event_id", "team_code", name="uq_teams_event_id_code"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    team_code = db.Column(db.Text, nullable=False)
    name = db.Column(db.Text, nullable=False)
    problem_statement = db.Column(db.Text, nullable=True)
    status = db.Column(db.Text, nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    event = db.relationship("Event", back_populates="teams")
    members = db.relationship("TeamMember", back_populates="team")
    submission = db.relationship("Submission", back_populates="team", uselist=False)


class TeamMember(db.Model):
    __tablename__ = "team_members"
    __table_args__ = (
        Index("ix_team_members_team_id_left_at", "team_id", "left_at"),
        Index(
            "uq_team_members_active_participant",
            "participant_id",
            unique=True,
            sqlite_where=text("left_at IS NULL"),
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False)
    participant_id = db.Column(
        db.String(36), db.ForeignKey("participants.id"), nullable=False
    )
    member_role = db.Column(db.Text, nullable=True)
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    left_at = db.Column(db.DateTime(timezone=True), nullable=True)

    team = db.relationship("Team", back_populates="members")
    participant = db.relationship("Participant", back_populates="memberships")
