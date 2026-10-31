import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.extensions import db
from app.models import AuditLog, Event
from app.services.time import utc_now

EVENT_STATUSES = ("draft", "active", "completed", "cancelled")
DATETIME_FORMAT = "%Y-%m-%dT%H:%M"


class EventValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Event validation failed")
        self.errors = errors


def _parse_local_datetime(value, label, timezone_name, errors):
    if not value:
        return None
    try:
        local = datetime.strptime(value, DATETIME_FORMAT)
        return local.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(
            ZoneInfo("UTC")
        )
    except (ValueError, ZoneInfoNotFoundError):
        errors[label] = "Enter a valid date and time for the selected timezone."
        return None


def _positive_integer(value, label, errors):
    if value in ("", None):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors[label] = "Enter a whole number greater than zero."
        return None
    if parsed <= 0:
        errors[label] = "Enter a whole number greater than zero."
        return None
    return parsed


def validate_event_data(data):
    errors = {}
    name = data.get("name", "").strip()
    if not name:
        errors["name"] = "Event name is required."
    elif len(name) > 160:
        errors["name"] = "Event name must be 160 characters or fewer."

    timezone_name = data.get("timezone", "").strip()
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        errors["timezone"] = "Enter a valid IANA timezone."
        timezone_name = "UTC"

    starts_at = _parse_local_datetime(
        data.get("starts_at", ""), "starts_at", timezone_name, errors
    )
    ends_at = _parse_local_datetime(
        data.get("ends_at", ""), "ends_at", timezone_name, errors
    )
    registration_starts_at = _parse_local_datetime(
        data.get("registration_starts_at", ""),
        "registration_starts_at",
        timezone_name,
        errors,
    )
    registration_ends_at = _parse_local_datetime(
        data.get("registration_ends_at", ""),
        "registration_ends_at",
        timezone_name,
        errors,
    )
    if starts_at and ends_at and ends_at <= starts_at:
        errors["ends_at"] = "Event end must be after the event start."
    if registration_starts_at and registration_ends_at and registration_ends_at <= registration_starts_at:
        errors["registration_ends_at"] = "Registration end must be after registration start."
    if registration_ends_at and starts_at and registration_ends_at > starts_at:
        errors["registration_ends_at"] = "Registration must end by the event start."

    capacity = _positive_integer(data.get("capacity"), "capacity", errors)
    team_size_min = _positive_integer(data.get("team_size_min"), "team_size_min", errors)
    team_size_max = _positive_integer(data.get("team_size_max"), "team_size_max", errors)
    if capacity is not None and team_size_min is not None and team_size_min > capacity:
        errors["team_size_min"] = "Minimum team size cannot exceed event capacity."
    if team_size_min and team_size_max and team_size_max < team_size_min:
        errors["team_size_max"] = "Maximum team size must be at least the minimum."

    status = data.get("status", "draft")
    if status not in EVENT_STATUSES:
        errors["status"] = "Choose a valid event status."

    if errors:
        raise EventValidationError(errors)
    return {
        "name": name,
        "description": (data.get("description") or "").strip() or None,
        "venue": (data.get("venue") or "").strip() or None,
        "timezone": timezone_name,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "registration_starts_at": registration_starts_at,
        "registration_ends_at": registration_ends_at,
        "capacity": capacity,
        "team_size_min": team_size_min,
        "team_size_max": team_size_max,
        "status": status,
    }


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "event"


def unique_slug(name, event_id=None):
    base = slugify(name)
    slug = base
    counter = 2
    while Event.query.filter(Event.slug == slug, Event.id != event_id).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def event_form_data(event):
    def local(value):
        return value.strftime(DATETIME_FORMAT) if value else ""

    return {
        "name": event.name,
        "description": event.description or "",
        "venue": event.venue or "",
        "timezone": event.timezone,
        "starts_at": local(event.starts_at),
        "ends_at": local(event.ends_at),
        "registration_starts_at": local(event.registration_starts_at),
        "registration_ends_at": local(event.registration_ends_at),
        "capacity": str(event.capacity or ""),
        "team_size_min": str(event.team_size_min or ""),
        "team_size_max": str(event.team_size_max or ""),
        "status": event.status,
    }


def audit_event(actor, event, action, before=None):
    after = {
        "name": event.name,
        "slug": event.slug,
        "status": event.status,
        "timezone": event.timezone,
        "capacity": event.capacity,
        "team_size_min": event.team_size_min,
        "team_size_max": event.team_size_max,
    }
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id,
            action=action,
            entity_type="event",
            entity_id=event.id,
            before_json=json.dumps(before, sort_keys=True) if before else None,
            after_json=json.dumps(after, sort_keys=True),
            created_at=utc_now(),
        )
    )
