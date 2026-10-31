import json
import secrets

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AuditLog, AutomationOutbox, Event, Participant, User
from app.services.passwords import hash_password
from app.services.time import as_utc, utc_now

REGISTRATION_STATUSES = ("pending", "confirmed", "cancelled", "flagged_duplicate")


class ParticipantValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Participant validation failed")
        self.errors = errors


class ParticipantRegistrationError(ValueError):
    pass


def normalize_email(value):
    return " ".join((value or "").strip().casefold().split())


def validate_participant_data(data, require_password=False):
    errors = {}
    full_name = (data.get("full_name") or "").strip()
    email = normalize_email(data.get("email"))
    phone = (data.get("phone") or "").strip() or None
    institution = (data.get("institution") or "").strip() or None
    status = data.get("registration_status", "pending")

    if not full_name:
        errors["full_name"] = "Full name is required."
    elif len(full_name) > 160:
        errors["full_name"] = "Full name must be 160 characters or fewer."
    if not email or "@" not in email or len(email) > 320:
        errors["email"] = "Enter a valid email address."
    if phone and len(phone) > 40:
        errors["phone"] = "Phone must be 40 characters or fewer."
    if institution and len(institution) > 200:
        errors["institution"] = "Institution must be 200 characters or fewer."
    if status not in REGISTRATION_STATUSES:
        errors["registration_status"] = "Choose a valid registration status."
    password = data.get("password") or ""
    if require_password and len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if errors:
        raise ParticipantValidationError(errors)
    return {
        "full_name": full_name,
        "email_normalized": email,
        "phone": phone,
        "institution": institution,
        "registration_status": status,
        "password": password or None,
    }


def registration_is_open(event, now=None):
    now = as_utc(now or utc_now())
    if event.status != "active":
        return False
    starts = as_utc(event.registration_starts_at)
    ends = as_utc(event.registration_ends_at)
    return (starts is None or now >= starts) and (ends is None or now <= ends)


def _active_capacity_reached(event):
    if event.capacity is None:
        return False
    return Participant.query.filter(
        Participant.event_id == event.id,
        Participant.registration_status != "cancelled",
    ).count() >= event.capacity


def _participant_code(event_id):
    for _ in range(10):
        code = secrets.token_urlsafe(12)
        if not Participant.query.filter_by(
            event_id=event_id, participant_code=code
        ).first():
            return code
    raise ParticipantRegistrationError("Could not generate a unique participant code.")


def _audit(actor, event, action, participant, before=None):
    after = {
        "participant_id": participant.id,
        "full_name": participant.full_name,
        "email_normalized": participant.email_normalized,
        "registration_status": participant.registration_status,
    }
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id if actor else None,
            action=action,
            entity_type="participant",
            entity_id=participant.id,
            before_json=json.dumps(before, sort_keys=True) if before else None,
            after_json=json.dumps(after, sort_keys=True),
            created_at=utc_now(),
        )
    )


def _registration_outbox(event, participant):
    db.session.add(
        AutomationOutbox(
            event_id=event.id,
            event_type="registration.created",
            payload_json=json.dumps(
                {
                    "event_id": event.id,
                    "participant_id": participant.id,
                    "email": participant.email_normalized,
                    "full_name": participant.full_name,
                },
                sort_keys=True,
            ),
            status="pending",
            attempt_count=0,
            created_at=utc_now(),
        )
    )


def create_participant(event, data, actor=None):
    values = validate_participant_data(data)
    existing = Participant.query.filter_by(
        event_id=event.id, email_normalized=values["email_normalized"]
    ).first()
    if existing:
        raise ParticipantRegistrationError(
            "A participant with this email is already registered for this event."
        )
    if _active_capacity_reached(event):
        raise ParticipantRegistrationError("This event has reached its participant capacity.")
    existing_user = User.query.filter_by(
        event_id=event.id, email=values["email_normalized"]
    ).first()
    if existing_user and (
        existing_user.role != "participant" or existing_user.participant is not None
    ):
        raise ParticipantRegistrationError(
            "An account with this email already exists for this event."
        )

    for _ in range(3):
        participant = Participant(
            event_id=event.id,
            participant_code=_participant_code(event.id),
            full_name=values["full_name"],
            email_normalized=values["email_normalized"],
            phone=values["phone"],
            institution=values["institution"],
            registration_status=values["registration_status"],
        )
        db.session.add(participant)
        try:
            db.session.flush()
            from app.services.attendance import _assign_check_in_token

            _assign_check_in_token(participant)
            if existing_user:
                participant.user_id = existing_user.id
            _audit(actor, event, "participant.created", participant)
            _registration_outbox(event, participant)
            return participant
        except IntegrityError:
            db.session.rollback()
            existing = Participant.query.filter_by(
                event_id=event.id, email_normalized=values["email_normalized"]
            ).first()
            if existing:
                raise ParticipantRegistrationError(
                    "A participant with this email is already registered for this event."
                ) from None
    raise ParticipantRegistrationError("Participant could not be registered safely.")


def register_participant(event, data):
    if not registration_is_open(event):
        raise ParticipantRegistrationError(
            "Registration is not open for this event."
        )
    values = validate_participant_data(data, require_password=True)
    values["registration_status"] = "pending"
    existing_user = User.query.filter_by(
        event_id=event.id, email=values["email_normalized"]
    ).first()
    if existing_user:
        raise ParticipantRegistrationError(
            "An account with this email already exists for this event."
        )
    participant = create_participant(
        event, {**data, "registration_status": "pending"}
    )
    user = User(
        event_id=event.id,
        email=values["email_normalized"],
        password_hash=hash_password(values["password"]),
        role="participant",
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    participant.user_id = user.id
    try:
        db.session.commit()
    except IntegrityError as error:
        db.session.rollback()
        raise ParticipantRegistrationError(
            "An account with this email already exists for this event."
        ) from error
    return participant, user


def update_participant(actor, participant, data):
    values = validate_participant_data(data)
    duplicate = Participant.query.filter(
        Participant.event_id == participant.event_id,
        Participant.email_normalized == values["email_normalized"],
        Participant.id != participant.id,
    ).first()
    if duplicate:
        raise ParticipantRegistrationError(
            "A participant with this email is already registered for this event."
        )
    if participant.user is not None:
        duplicate_user = User.query.filter(
            User.event_id == participant.event_id,
            User.email == values["email_normalized"],
            User.id != participant.user_id,
        ).first()
        if duplicate_user:
            raise ParticipantRegistrationError(
                "An account with this email already exists for this event."
            )
    before = {
        "full_name": participant.full_name,
        "email_normalized": participant.email_normalized,
        "registration_status": participant.registration_status,
    }
    participant.full_name = values["full_name"]
    participant.email_normalized = values["email_normalized"]
    participant.phone = values["phone"]
    participant.institution = values["institution"]
    participant.registration_status = values["registration_status"]
    if participant.user is not None:
        participant.user.email = values["email_normalized"]
    _audit(actor, participant.event, "participant.updated", participant, before)
    db.session.commit()
    return participant
