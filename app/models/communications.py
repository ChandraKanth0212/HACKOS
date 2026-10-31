from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    title = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.Text, nullable=False, default="draft")
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    event = db.relationship("Event", back_populates="announcements")
    author = db.relationship("User", foreign_keys=[created_by])


class ScheduleItem(db.Model):
    __tablename__ = "schedule_items"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=False)
    location = db.Column(db.Text, nullable=True)
    status = db.Column(db.Text, nullable=False, default="draft")
    created_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    event = db.relationship("Event", back_populates="schedule_items")
    author = db.relationship("User", foreign_keys=[created_by])
