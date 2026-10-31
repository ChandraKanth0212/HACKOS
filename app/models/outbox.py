from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class AutomationOutbox(db.Model):
    __tablename__ = "automation_outbox"
    __table_args__ = (
        db.Index(
            "ix_automation_outbox_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    event_type = db.Column(db.Text, nullable=False)
    payload_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="pending")
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    event = db.relationship("Event", back_populates="automation_outbox")
