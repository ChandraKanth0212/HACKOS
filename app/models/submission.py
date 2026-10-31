from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Submission(db.Model):
    __tablename__ = "submissions"
    __table_args__ = (
        db.UniqueConstraint("event_id", "team_id", name="uq_submissions_event_id_team_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    team_id = db.Column(db.String(36), db.ForeignKey("teams.id"), nullable=False)
    project_title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    repository_url = db.Column(db.Text, nullable=True)
    demo_url = db.Column(db.Text, nullable=True)
    status = db.Column(db.Text, nullable=False, default="submitted")
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    updated_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)

    event = db.relationship("Event", back_populates="submissions")
    team = db.relationship("Team", back_populates="submission")
    updater = db.relationship("User", foreign_keys=[updated_by])
    assignments = db.relationship("JudgeAssignment", back_populates="submission")
    evaluations = db.relationship("Evaluation", back_populates="submission")
