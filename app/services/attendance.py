import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from io import BytesIO

import qrcode
from flask import current_app
from qrcode.image.svg import SvgPathImage
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Attendance, AuditLog, Participant
from app.models.base import generate_uuid
from app.services.time import utc_now


class AttendanceError(ValueError):
    pass


class InvalidCredentialError(AttendanceError):
    pass


class AttendanceAuthorizationError(AttendanceError):
    pass


@dataclass
class CheckInResult:
    status: str
    attendance: Attendance
    participant: Participant


def _token_digest(participant, nonce):
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    message = f"{participant.event_id}:{participant.id}:{nonce}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _token_value(participant, nonce):
    return f"HACKOS1.{nonce}.{_token_digest(participant, nonce)}"


def _assign_check_in_token(participant):
    nonce = secrets.token_urlsafe(32)
    token = _token_value(participant, nonce)
    participant.check_in_token_nonce = nonce
    participant.check_in_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    participant.check_in_token_revoked_at = None
    return token


def ensure_check_in_token(participant):
    if (
        participant.check_in_token_nonce
        and participant.check_in_token_hash
        and participant.check_in_token_revoked_at is None
    ):
        return _token_value(participant, participant.check_in_token_nonce)
    token = _assign_check_in_token(participant)
    db.session.commit()
    return token


def revoke_check_in_token(participant):
    participant.check_in_token_revoked_at = utc_now()
    db.session.commit()


def qr_svg_data_uri(token):
    qr = qrcode.QRCode(box_size=8, border=4)
    qr.add_data(token)
    qr.make(fit=True)
    image = qr.make_image(image_factory=SvgPathImage)
    output = BytesIO()
    image.save(output)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _authorized_actor(actor, event):
    if actor is None or actor.role != "organizer" or actor.event_id != event.id:
        raise AttendanceAuthorizationError("Only an organizer for this event may check in participants.")


def _validate_participant(participant, event):
    if participant is None or participant.event_id != event.id:
        raise InvalidCredentialError("The participant credential is not valid for this event.")
    if participant.registration_status == "cancelled":
        raise InvalidCredentialError("This participant registration is cancelled.")


def _record_check_in(actor, event, participant, source, operation_id):
    _authorized_actor(actor, event)
    _validate_participant(participant, event)
    existing = Attendance.query.filter_by(
        event_id=event.id, participant_id=participant.id
    ).first()
    if existing:
        status = "idempotent" if operation_id and existing.operation_id == operation_id else "duplicate"
        return CheckInResult(status, existing, participant)

    record = Attendance(
        event_id=event.id,
        participant_id=participant.id,
        checked_in_by=actor.id,
        operation_id=operation_id or generate_uuid(),
        source=source,
    )
    db.session.add(record)
    db.session.flush()
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id,
            action="attendance.checked_in",
            entity_type="attendance",
            entity_id=record.id,
            after_json=f'{{"participant_id":"{participant.id}","source":"{source}"}}',
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = Attendance.query.filter_by(
            event_id=event.id, participant_id=participant.id
        ).first()
        if existing:
            status = "idempotent" if operation_id and existing.operation_id == operation_id else "duplicate"
            return CheckInResult(status, existing, participant)
        raise AttendanceError("The check-in could not be recorded.")
    return CheckInResult("checked_in", record, participant)


def check_in_with_code(actor, event, participant_code, operation_id=None):
    code = (participant_code or "").strip()
    participant = Participant.query.filter_by(
        event_id=event.id, participant_code=code
    ).first()
    if participant is None:
        raise InvalidCredentialError("Participant code was not found for this event.")
    return _record_check_in(actor, event, participant, "manual", operation_id)


def check_in_with_token(actor, event, token, operation_id=None):
    raw_token = (token or "").strip()
    parts = raw_token.split(".")
    if len(parts) != 3 or parts[0] != "HACKOS1":
        raise InvalidCredentialError("QR credential is invalid.")
    nonce = parts[1]
    participant = Participant.query.filter_by(
        event_id=event.id, check_in_token_nonce=nonce
    ).first()
    if (
        participant is None
        or participant.check_in_token_revoked_at is not None
        or participant.check_in_token_hash
        != hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        or not hmac.compare_digest(parts[2], _token_digest(participant, nonce))
    ):
        raise InvalidCredentialError("QR credential is invalid or revoked.")
    return _record_check_in(actor, event, participant, "qr", operation_id)
