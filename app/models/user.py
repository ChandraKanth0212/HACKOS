from flask_login import UserMixin

from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.UniqueConstraint("event_id", "email", name="uq_users_event_id_email"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    email = db.Column(db.Text, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    role = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    event = db.relationship("Event", back_populates="users")
    participant = db.relationship("Participant", back_populates="user", uselist=False)
    judge = db.relationship("Judge", back_populates="user", uselist=False)
    audit_logs = db.relationship("AuditLog", back_populates="actor")
