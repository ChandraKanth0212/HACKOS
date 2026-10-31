from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Participant(db.Model):
    __tablename__ = "participants"
    __table_args__ = (
        db.UniqueConstraint(
            "event_id", "email_normalized", name="uq_participants_event_id_email"
        ),
        db.UniqueConstraint(
            "event_id", "participant_code", name="uq_participants_event_id_code"
        ),
        db.UniqueConstraint("user_id", name="uq_participants_user_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    participant_code = db.Column(db.Text, nullable=False)
    full_name = db.Column(db.Text, nullable=False)
    email_normalized = db.Column(db.Text, nullable=False)
    phone = db.Column(db.Text, nullable=True)
    institution = db.Column(db.Text, nullable=True)
    registration_status = db.Column(db.Text, nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    event = db.relationship("Event", back_populates="participants")
    user = db.relationship("User", back_populates="participant")
    memberships = db.relationship("TeamMember", back_populates="participant")
    attendance = db.relationship("Attendance", back_populates="participant", uselist=False)
