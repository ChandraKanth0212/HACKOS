import json
import re

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuditLog, Participant, Team, TeamMember
from app.services.time import utc_now


class TeamValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Team validation failed")
        self.errors = errors


class MembershipError(ValueError):
    pass


def _team_code(name):
    base = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-") or "TEAM"
    return f"{base[:20]}-{utc_now().strftime('%H%M%S')}-{utc_now().microsecond % 10000:04d}"


def unique_team_code(event_id, name):
    for _ in range(10):
        code = _team_code(name)
        if not Team.query.filter_by(event_id=event_id, team_code=code).first():
            return code
    raise MembershipError("Could not generate a unique team code.")


def validate_team_data(data):
    errors = {}
    name = (data.get("name") or "").strip()
    problem_statement = (data.get("problem_statement") or "").strip() or None
    status = (data.get("status") or "active").strip()
    if not name:
        errors["name"] = "Team name is required."
    elif len(name) > 160:
        errors["name"] = "Team name must be 160 characters or fewer."
    if problem_statement and len(problem_statement) > 4000:
        errors["problem_statement"] = "Problem statement must be 4000 characters or fewer."
    if status not in ("active", "withdrawn"):
        errors["status"] = "Choose a valid team status."
    if errors:
        raise TeamValidationError(errors)
    return {
        "name": name,
        "problem_statement": problem_statement,
        "status": status,
    }


def _active_members(team):
    return TeamMember.query.filter_by(team_id=team.id, left_at=None)


def _minimum(event):
    return event.team_size_min or 0


def _maximum(event):
    return event.team_size_max


def _audit(actor, event, action, entity_type, entity_id, before=None, after=None):
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=json.dumps(before, sort_keys=True) if before else None,
            after_json=json.dumps(after, sort_keys=True) if after else None,
            created_at=utc_now(),
        )
    )


def create_team(actor, event, data):
    values = validate_team_data(data)
    team = Team(
        event_id=event.id,
        team_code=unique_team_code(event.id, values["name"]),
        **values,
    )
    db.session.add(team)
    db.session.flush()
    _audit(actor, event, "team.created", "team", team.id, after={
        "team_code": team.team_code, "name": team.name, "status": team.status
    })
    db.session.commit()
    return team


def update_team(actor, team, data):
    values = validate_team_data(data)
    before = {
        "name": team.name,
        "problem_statement": team.problem_statement,
        "status": team.status,
    }
    for key, value in values.items():
        setattr(team, key, value)
    _audit(actor, team.event, "team.updated", "team", team.id, before=before, after=values)
    db.session.commit()
    return team


def _participant_for_event(event, participant_id):
    participant = db.session.get(Participant, participant_id)
    if participant is None or participant.event_id != event.id:
        raise MembershipError("Participant does not belong to this event.")
    if participant.registration_status == "cancelled":
        raise MembershipError("Cancelled participants cannot join a team.")
    return participant


def _ensure_team_event(team, event):
    if team.event_id != event.id:
        raise MembershipError("Team does not belong to this event.")


def _current_membership(event, participant_id):
    return (
        TeamMember.query.join(Team, Team.id == TeamMember.team_id)
        .filter(
            TeamMember.participant_id == participant_id,
            TeamMember.left_at.is_(None),
            Team.event_id == event.id,
        )
        .first()
    )


def add_member(actor, team, participant_id, member_role=None):
    event = team.event
    participant = _participant_for_event(event, participant_id)
    if team.status != "active":
        raise MembershipError("Members can only be added to active teams.")
    maximum = _maximum(event)
    if maximum is not None and _active_members(team).count() >= maximum:
        raise MembershipError("This team has reached its maximum size.")
    current = _current_membership(event, participant.id)
    if current:
        raise MembershipError("Participant already has an active team membership.")
    membership = TeamMember(
        team_id=team.id,
        participant_id=participant.id,
        member_role=(member_role or "").strip() or None,
        joined_at=utc_now(),
    )
    db.session.add(membership)
    try:
        db.session.flush()
        _audit(
            actor, event, "team.member_added", "team_member", membership.id,
            after={"team_id": team.id, "participant_id": participant.id},
        )
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise MembershipError("Participant already has an active team membership.") from error
    return membership


def remove_member(actor, team, participant_id):
    event = team.event
    _participant_for_event(event, participant_id)
    membership = _current_membership(event, participant_id)
    if membership is None or membership.team_id != team.id:
        raise MembershipError("Participant is not an active member of this team.")
    minimum = _minimum(event)
    if _active_members(team).count() <= minimum:
        raise MembershipError("This removal would leave the team below its minimum size.")
    membership.left_at = utc_now()
    _audit(
        actor, event, "team.member_removed", "team_member", membership.id,
        before={"team_id": team.id, "participant_id": participant_id},
        after={"left_at": membership.left_at.isoformat()},
    )
    db.session.commit()
    return membership


def transfer_member(actor, source_team, target_team, participant_id, member_role=None):
    event = source_team.event
    _ensure_team_event(target_team, event)
    if target_team.id == source_team.id:
        raise MembershipError("Participant is already on this team.")
    if target_team.status != "active":
        raise MembershipError("Participants can only transfer to active teams.")
    maximum = _maximum(event)
    if maximum is not None and _active_members(target_team).count() >= maximum:
        raise MembershipError("The destination team has reached its maximum size.")
    current = _current_membership(event, participant_id)
    if current is None or current.team_id != source_team.id:
        raise MembershipError("Participant is not an active member of the source team.")
    if _active_members(source_team).count() <= _minimum(event):
        raise MembershipError("This transfer would leave the source team below its minimum size.")
    now = utc_now()
    new_membership = TeamMember(
        team_id=target_team.id,
        participant_id=participant_id,
        member_role=(member_role or current.member_role),
        joined_at=now,
    )
    current.left_at = now
    db.session.add(new_membership)
    try:
        db.session.flush()
        _audit(
            actor, event, "team.member_transferred", "team_member", new_membership.id,
            before={"from_team_id": source_team.id, "participant_id": participant_id},
            after={"to_team_id": target_team.id, "participant_id": participant_id},
        )
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise MembershipError("Participant could not be transferred safely.") from error
    return new_membership
