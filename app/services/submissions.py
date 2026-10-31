import json
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuditLog, Participant, Submission, TeamMember
from app.services.time import as_utc, utc_now

SUBMISSION_STATUSES = ("submitted", "late", "locked", "withdrawn")
LATE_POLICIES = ("reject", "accept_and_flag", "allow")


class SubmissionValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Submission validation failed")
        self.errors = errors


class SubmissionAuthorizationError(ValueError):
    pass


class SubmissionConflictError(ValueError):
    pass


def _text(data, field, label, maximum, errors, required=True):
    value = (data.get(field) or "").strip()
    if required and not value:
        errors[field] = f"{label} is required."
    elif len(value) > maximum:
        errors[field] = f"{label} must be {maximum} characters or fewer."
    return value or None


def _url(data, field, label, errors):
    value = (data.get(field) or "").strip() or None
    if value:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors[field] = f"{label} must be a valid HTTP or HTTPS URL."
    return value


def validate_submission_data(data):
    errors = {}
    values = {
        "project_title": _text(data, "project_title", "Project title", 240, errors),
        "description": _text(
            data, "description", "Project description", 12000, errors
        ),
        "repository_url": _url(data, "repository_url", "Repository URL", errors),
        "demo_url": _url(data, "demo_url", "Demo URL", errors),
    }
    if errors:
        raise SubmissionValidationError(errors)
    return values


def _late_policy(event):
    try:
        settings = json.loads(event.settings_json or "{}")
    except (TypeError, ValueError):
        settings = {}
    policy = settings.get("late_submission_policy", "accept_and_flag")
    return policy if policy in LATE_POLICIES else "accept_and_flag"


def _submission_status(event, submitted_at):
    deadline = as_utc(event.submission_deadline)
    if deadline and as_utc(submitted_at) > deadline:
        policy = _late_policy(event)
        if policy == "reject":
            raise SubmissionConflictError("The submission deadline has passed.")
        if policy == "accept_and_flag":
            return "late"
    return "submitted"


def _active_member(team, participant):
    return TeamMember.query.filter_by(
        team_id=team.id, participant_id=participant.id, left_at=None
    ).first()


def _authorize_participant(participant_user, team):
    if (
        participant_user is None
        or participant_user.role != "participant"
        or participant_user.event_id != team.event_id
    ):
        raise SubmissionAuthorizationError(
            "You are not authorized to submit for this team."
        )
    participant = Participant.query.filter_by(
        user_id=participant_user.id, event_id=team.event_id
    ).first()
    if participant is None or _active_member(team, participant) is None:
        raise SubmissionAuthorizationError(
            "Only an active team member may submit for this team."
        )
    return participant


def _audit(actor, submission, action, before=None):
    db.session.add(
        AuditLog(
            event_id=submission.event_id,
            actor_user_id=actor.id,
            action=action,
            entity_type="submission",
            entity_id=submission.id,
            before_json=json.dumps(before, sort_keys=True) if before else None,
            after_json=json.dumps(
                {
                    "team_id": submission.team_id,
                    "project_title": submission.project_title,
                    "status": submission.status,
                },
                sort_keys=True,
            ),
            created_at=utc_now(),
        )
    )


def _values_state(submission):
    return {
        "project_title": submission.project_title,
        "description": submission.description,
        "repository_url": submission.repository_url,
        "demo_url": submission.demo_url,
        "status": submission.status,
        "submitted_at": submission.submitted_at.isoformat(),
    }


def create_submission(actor, team, data):
    if team.status != "active":
        raise SubmissionAuthorizationError(
            "Submissions are available only for active teams."
        )
    _authorize_participant(actor, team)
    values = validate_submission_data(data)
    existing = Submission.query.filter_by(
        event_id=team.event_id, team_id=team.id
    ).first()
    if existing:
        raise SubmissionConflictError(
            "This team already has a submission. Use edit instead."
        )
    submitted_at = utc_now()
    status = _submission_status(team.event, submitted_at)
    submission = Submission(
        event_id=team.event_id,
        team_id=team.id,
        updated_by=actor.id,
        submitted_at=submitted_at,
        status=status,
        **values,
    )
    db.session.add(submission)
    try:
        db.session.flush()
        _audit(actor, submission, "submission.created")
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise SubmissionConflictError(
            "This team already has a submission. Use edit instead."
        ) from error
    return submission


def update_submission(actor, submission, data):
    team = submission.team
    if actor.role == "participant":
        _authorize_participant(actor, team)
    elif actor.role != "organizer" or actor.event_id != submission.event_id:
        raise SubmissionAuthorizationError(
            "You are not authorized to update this submission."
        )
    if submission.status == "locked":
        raise SubmissionConflictError("This submission is locked.")
    values = validate_submission_data(data)
    before = _values_state(submission)
    for key, value in values.items():
        setattr(submission, key, value)
    if actor.role == "participant":
        submission.status = _submission_status(team.event, submission.submitted_at)
    submission.updated_by = actor.id
    _audit(actor, submission, "submission.updated", before)
    db.session.commit()
    return submission
