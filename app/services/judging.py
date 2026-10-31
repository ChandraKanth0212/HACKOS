import json
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AuditLog,
    Evaluation,
    EvaluationScore,
    Judge,
    JudgeAssignment,
    RubricCriterion,
    Submission,
)
from app.services.time import utc_now


class JudgingError(ValueError):
    pass


class JudgingValidationError(JudgingError):
    def __init__(self, errors):
        super().__init__("Judging validation failed")
        self.errors = errors


def _audit(actor, event_id, action, entity_type, entity_id, before=None, after=None):
    db.session.add(
        AuditLog(
            event_id=event_id,
            actor_user_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=json.dumps(before, sort_keys=True) if before else None,
            after_json=json.dumps(after, sort_keys=True) if after else None,
            created_at=utc_now(),
        )
    )


def _assert_organizer_event(actor, event_id):
    if actor.role != "organizer" or actor.event_id != event_id:
        raise JudgingError("You are not authorized for this event.")


def _get_assignment_for_judge(judge_user, submission_id):
    judge = Judge.query.filter_by(
        user_id=judge_user.id, event_id=judge_user.event_id
    ).first()
    if judge is None:
        raise JudgingError("Judge profile not found.")
    assignment = JudgeAssignment.query.filter_by(
        judge_id=judge.id, submission_id=submission_id, event_id=judge.event_id
    ).first()
    if assignment is None or assignment.status == "revoked":
        raise JudgingError("This submission is not assigned to you.")
    return judge, assignment


def assign_judge(actor, submission_id, judge_id):
    submission = db.session.get(Submission, submission_id)
    judge = db.session.get(Judge, judge_id)
    if submission is None or judge is None:
        raise JudgingError("The submission or judge does not exist.")
    _assert_organizer_event(actor, submission.event_id)
    if judge.event_id != submission.event_id:
        raise JudgingError("Judge and submission must belong to the same event.")
    existing = JudgeAssignment.query.filter_by(
        submission_id=submission.id, judge_id=judge.id
    ).first()
    if existing is not None:
        if existing.status != "revoked":
            raise JudgingError("This judge is already assigned to the submission.")
        existing.status = "assigned"
        existing.assigned_by = actor.id
        existing.assigned_at = utc_now()
        _audit(
            actor, submission.event_id, "judge.assignment_reactivated",
            "judge_assignment", existing.id, after={"status": "assigned"},
        )
        db.session.commit()
        return existing
    assignment = JudgeAssignment(
        event_id=submission.event_id,
        submission_id=submission.id,
        judge_id=judge.id,
        status="assigned",
        assigned_by=actor.id,
        assigned_at=utc_now(),
    )
    db.session.add(assignment)
    try:
        db.session.flush()
        _audit(
            actor, submission.event_id, "judge.assignment_created",
            "judge_assignment", assignment.id,
            after={"submission_id": submission.id, "judge_id": judge.id},
        )
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise JudgingError("This judge is already assigned to the submission.") from error
    return assignment


def revoke_assignment(actor, assignment_id):
    assignment = db.session.get(JudgeAssignment, assignment_id)
    if assignment is None:
        raise JudgingError("Assignment not found.")
    _assert_organizer_event(actor, assignment.event_id)
    if assignment.status == "revoked":
        return assignment
    evaluation = Evaluation.query.filter_by(
        submission_id=assignment.submission_id, judge_id=assignment.judge_id
    ).first()
    if evaluation and evaluation.status == "submitted":
        raise JudgingError("Submitted evaluations cannot be revoked.")
    assignment.status = "revoked"
    _audit(
        actor, assignment.event_id, "judge.assignment_revoked",
        "judge_assignment", assignment.id, after={"status": "revoked"},
    )
    db.session.commit()
    return assignment


def _active_criteria(event_id):
    criteria = RubricCriterion.query.filter_by(
        event_id=event_id, is_active=True
    ).order_by(RubricCriterion.display_order.asc(), RubricCriterion.id.asc()).all()
    if any(c.max_score <= 0 for c in criteria):
        raise JudgingError("Active rubric maximum scores must be positive.")
    if any(c.weight is not None and c.weight < 0 for c in criteria):
        raise JudgingError("Rubric weights cannot be negative.")
    if any(c.weight is not None for c in criteria) and any(
        c.weight is None for c in criteria
    ):
        raise JudgingError("All active rubric criteria must define a weight.")
    return criteria


def _parse_scores(criteria, score_data, require_all):
    errors = {}
    parsed = {}
    for criterion in criteria:
        raw = score_data.get(criterion.id)
        if raw in (None, ""):
            if require_all:
                errors[criterion.id] = f"{criterion.name} requires a score."
            continue
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            errors[criterion.id] = "Score must be a number."
            continue
        maximum = Decimal(str(criterion.max_score))
        if value < 0 or value > maximum:
            errors[criterion.id] = f"Score must be between 0 and {maximum}."
            continue
        parsed[criterion.id] = value
    if errors:
        raise JudgingValidationError(errors)
    return parsed


def _total_score(criteria, parsed):
    weighted = any(criterion.weight is not None for criterion in criteria)
    if weighted:
        total_weight = sum(
            (Decimal(str(c.weight)) for c in criteria if c.weight is not None),
            Decimal("0"),
        )
        if total_weight <= 0:
            raise JudgingError("Active rubric weights must have a positive total.")
        return (
            sum(
                (
                    parsed[c.id] / Decimal(str(c.max_score))
                    * Decimal(str(c.weight))
                    for c in criteria
                    if c.id in parsed and c.weight is not None
                ),
                Decimal("0"),
            )
            / total_weight
            * Decimal("100")
        ).quantize(Decimal("0.0001"))
    return sum(parsed.values(), Decimal("0")).quantize(Decimal("0.0001"))


def _criterion_comment(value):
    value = (value or "").strip()
    if len(value) > 5000:
        raise JudgingValidationError(
            {"comments": "Criterion comments must be 5000 characters or fewer."}
        )
    return value or None


def save_evaluation(
    judge_user, submission_id, score_data, comments, submit=False, criterion_comments=None
):
    judge, assignment = _get_assignment_for_judge(judge_user, submission_id)
    evaluation = Evaluation.query.filter_by(
        submission_id=submission_id, judge_id=judge.id
    ).first()
    if evaluation and evaluation.status == "submitted":
        raise JudgingError("Submitted evaluations are read-only.")
    criteria = _active_criteria(assignment.event_id)
    parsed = _parse_scores(criteria, score_data, require_all=submit)
    comments = (comments or "").strip() or None
    if evaluation is None:
        evaluation = Evaluation(
            event_id=assignment.event_id,
            submission_id=submission_id,
            judge_id=judge.id,
            status="draft",
            comments=comments,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(evaluation)
        db.session.flush()
    else:
        evaluation.comments = comments
    existing_scores = {
        score.criterion_id: score for score in evaluation.scores
    }
    for criterion_id, value in parsed.items():
        score = existing_scores.get(criterion_id)
        if score is None:
            db.session.add(
                EvaluationScore(
                    evaluation_id=evaluation.id,
                    criterion_id=criterion_id,
                    score=value,
                    comment=_criterion_comment(
                        (criterion_comments or {}).get(criterion_id)
                    ),
                )
            )
        else:
            score.score = value
            if criterion_comments is not None and criterion_id in criterion_comments:
                score.comment = _criterion_comment(criterion_comments[criterion_id])
    if submit:
        evaluation.status = "submitted"
        evaluation.total_score = _total_score(criteria, parsed)
        evaluation.submitted_at = utc_now()
        assignment.status = "completed"
    else:
        evaluation.status = "draft"
    _audit(
        judge_user,
        assignment.event_id,
        "evaluation.submitted" if submit else "evaluation.draft_saved",
        "evaluation",
        evaluation.id,
        after={"status": evaluation.status, "total_score": str(evaluation.total_score) if evaluation.total_score is not None else None},
    )
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise JudgingError("The evaluation could not be saved.") from error
    return evaluation
