from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint(
            "event_id", "participant_id", name="uq_attendance_event_id_participant_id"
        ),
        db.UniqueConstraint("operation_id", name="uq_attendance_operation_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    participant_id = db.Column(
        db.String(36), db.ForeignKey("participants.id"), nullable=False
    )
    checked_in_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    checked_in_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    operation_id = db.Column(db.Text, nullable=True)
    source = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    event = db.relationship("Event", back_populates="attendance_records")
    participant = db.relationship("Participant", back_populates="attendance")
    staff_user = db.relationship("User", foreign_keys=[checked_in_by])
