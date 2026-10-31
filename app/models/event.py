from app.extensions import db
from app.models.base import TimestampMixin, generate_uuid
from app.services.time import DEFAULT_EVENT_TIMEZONE


class Event(TimestampMixin, db.Model):
    __tablename__ = "events"
    __table_args__ = (
        db.CheckConstraint(
            "team_size_min IS NULL OR team_size_min > 0",
            name="ck_events_team_size_min_positive",
        ),
        db.CheckConstraint(
            "team_size_max IS NULL OR team_size_max > 0",
            name="ck_events_team_size_max_positive",
        ),
        db.CheckConstraint(
            "team_size_min IS NULL OR team_size_max IS NULL OR team_size_max >= team_size_min",
            name="ck_events_team_size_range",
        ),
        db.CheckConstraint(
            "capacity IS NULL OR capacity > 0", name="ck_events_capacity_positive"
        ),
        db.CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'cancelled')",
            name="ck_events_status_valid",
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.Text, nullable=False)
    slug = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    venue = db.Column(db.Text, nullable=True)
    timezone = db.Column(db.Text, nullable=False, default=DEFAULT_EVENT_TIMEZONE)
    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    registration_starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    registration_ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    submission_deadline = db.Column(db.DateTime(timezone=True), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    team_size_min = db.Column(db.Integer, nullable=True)
    team_size_max = db.Column(db.Integer, nullable=True)
    status = db.Column(db.Text, nullable=False, default="draft")
    owner_user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    settings_json = db.Column(db.Text, nullable=True)

    users = db.relationship(
        "User", foreign_keys="User.event_id", back_populates="event"
    )
    participants = db.relationship("Participant", back_populates="event")
    teams = db.relationship("Team", back_populates="event")
    announcements = db.relationship("Announcement", back_populates="event")
    schedule_items = db.relationship("ScheduleItem", back_populates="event")
    submissions = db.relationship("Submission", back_populates="event")
    judges = db.relationship("Judge", back_populates="event")
    judge_assignments = db.relationship("JudgeAssignment", back_populates="event")
    rubric_criteria = db.relationship("RubricCriterion", back_populates="event")
    evaluations = db.relationship("Evaluation", back_populates="event")
    attendance_records = db.relationship("Attendance", back_populates="event")
    audit_logs = db.relationship("AuditLog", back_populates="event")
    automation_outbox = db.relationship("AutomationOutbox", back_populates="event")
    owner = db.relationship("User", foreign_keys=[owner_user_id], back_populates="owned_events")
