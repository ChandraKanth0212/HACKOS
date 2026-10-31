from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        db.Index("ix_audit_logs_event_id_created_at", "event_id", "created_at"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    actor_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.Text, nullable=False)
    entity_type = db.Column(db.Text, nullable=False)
    entity_id = db.Column(db.Text, nullable=False)
    before_json = db.Column(db.Text, nullable=True)
    after_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    event = db.relationship("Event", back_populates="audit_logs")
    actor = db.relationship("User", back_populates="audit_logs")
