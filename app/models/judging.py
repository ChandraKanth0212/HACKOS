from app.extensions import db
from app.models.base import generate_uuid
from app.services.time import utc_now


class Judge(db.Model):
    __tablename__ = "judges"
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_judges_user_id"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    display_name = db.Column(db.Text, nullable=False)
    expertise = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    event = db.relationship("Event", back_populates="judges")
    user = db.relationship("User", back_populates="judge")
    assignments = db.relationship("JudgeAssignment", back_populates="judge")
    evaluations = db.relationship("Evaluation", back_populates="judge")


class JudgeAssignment(db.Model):
    __tablename__ = "judge_assignments"
    __table_args__ = (
        db.UniqueConstraint(
            "submission_id", "judge_id", name="uq_judge_assignments_submission_judge"
        ),
        db.Index("ix_judge_assignments_judge_id_status", "judge_id", "status"),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    submission_id = db.Column(
        db.String(36), db.ForeignKey("submissions.id"), nullable=False
    )
    judge_id = db.Column(db.String(36), db.ForeignKey("judges.id"), nullable=False)
    status = db.Column(db.Text, nullable=False, default="assigned")
    assigned_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    event = db.relationship("Event", back_populates="judge_assignments")
    submission = db.relationship("Submission", back_populates="assignments")
    judge = db.relationship("Judge", back_populates="assignments")
    assigner = db.relationship("User", foreign_keys=[assigned_by])


class RubricCriterion(db.Model):
    __tablename__ = "rubric_criteria"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_score = db.Column(db.Numeric(10, 2), nullable=False)
    weight = db.Column(db.Numeric(10, 4), nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    event = db.relationship("Event", back_populates="rubric_criteria")
    scores = db.relationship("EvaluationScore", back_populates="criterion")


class Evaluation(db.Model):
    __tablename__ = "evaluations"
    __table_args__ = (
        db.UniqueConstraint(
            "submission_id", "judge_id", name="uq_evaluations_submission_judge"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    submission_id = db.Column(
        db.String(36), db.ForeignKey("submissions.id"), nullable=False
    )
    judge_id = db.Column(db.String(36), db.ForeignKey("judges.id"), nullable=False)
    status = db.Column(db.Text, nullable=False, default="draft")
    comments = db.Column(db.Text, nullable=True)
    total_score = db.Column(db.Numeric(10, 4), nullable=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    event = db.relationship("Event", back_populates="evaluations")
    submission = db.relationship("Submission", back_populates="evaluations")
    judge = db.relationship("Judge", back_populates="evaluations")
    scores = db.relationship("EvaluationScore", back_populates="evaluation")


class EvaluationScore(db.Model):
    __tablename__ = "evaluation_scores"
    __table_args__ = (
        db.UniqueConstraint(
            "evaluation_id", "criterion_id", name="uq_evaluation_scores_eval_criterion"
        ),
    )

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    evaluation_id = db.Column(
        db.String(36), db.ForeignKey("evaluations.id"), nullable=False
    )
    criterion_id = db.Column(
        db.String(36), db.ForeignKey("rubric_criteria.id"), nullable=False
    )
    score = db.Column(db.Numeric(10, 2), nullable=False)
    comment = db.Column(db.Text, nullable=True)

    evaluation = db.relationship("Evaluation", back_populates="scores")
    criterion = db.relationship("RubricCriterion", back_populates="scores")
