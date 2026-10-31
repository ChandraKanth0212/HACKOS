import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.extensions import db
from app.models import Announcement, AuditLog, ScheduleItem
from app.services.time import utc_now

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
CONTENT_STATUSES = ("draft", "published")


class CommunicationValidationError(ValueError):
    def __init__(self, errors):
        super().__init__("Communication validation failed")
        self.errors = errors


def _required_text(data, field, label, maximum, errors):
    value = (data.get(field) or "").strip()
    if not value:
        errors[field] = f"{label} is required."
    elif len(value) > maximum:
        errors[field] = f"{label} must be {maximum} characters or fewer."
    return value


def _optional_text(data, field, maximum, errors):
    value = (data.get(field) or "").strip()
    if len(value) > maximum:
        errors[field] = f"{field.replace('_', ' ').capitalize()} must be {maximum} characters or fewer."
    return value or None


def _status(data, errors):
    value = data.get("status", "draft")
    if value not in CONTENT_STATUSES:
        errors["status"] = "Choose a valid publication status."
    return value


def _event_local_datetime(value, field, timezone_name, errors):
    try:
        local = datetime.strptime((value or "").strip(), DATETIME_FORMAT)
    except (TypeError, ValueError):
        errors[field] = "Enter a valid date and time."
        return None
    try:
        return local.replace(tzinfo=ZoneInfo(timezone_name)).astimezone(ZoneInfo("UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        errors[field] = "The event timezone is invalid."
        return None


def validate_announcement_data(data):
    errors = {}
    title = _required_text(data, "title", "Title", 200, errors)
    body = _required_text(data, "body", "Content", 10000, errors)
    status = _status(data, errors)
    if errors:
        raise CommunicationValidationError(errors)
    return {"title": title, "body": body, "status": status}


def validate_schedule_data(data, event):
    errors = {}
    title = _required_text(data, "title", "Title", 200, errors)
    description = _optional_text(data, "description", 10000, errors)
    location = _optional_text(data, "location", 240, errors)
    starts_at = _event_local_datetime(
        data.get("starts_at"), "starts_at", event.timezone, errors
    )
    ends_at = _event_local_datetime(
        data.get("ends_at"), "ends_at", event.timezone, errors
    )
    if starts_at and ends_at and ends_at <= starts_at:
        errors["ends_at"] = "Schedule end must be after the start."
    status = _status(data, errors)
    if errors:
        raise CommunicationValidationError(errors)
    return {
        "title": title,
        "description": description,
        "location": location,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "status": status,
    }


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


def _announcement_state(announcement):
    return {
        "title": announcement.title,
        "status": announcement.status,
        "published_at": announcement.published_at.isoformat()
        if announcement.published_at
        else None,
    }


def create_announcement(actor, event, data):
    values = validate_announcement_data(data)
    announcement = Announcement(event_id=event.id, created_by=actor.id, **values)
    if values["status"] == "published":
        announcement.published_at = utc_now()
    db.session.add(announcement)
    db.session.flush()
    _audit(actor, event, "announcement.created", "announcement", announcement.id, after=_announcement_state(announcement))
    db.session.commit()
    return announcement


def update_announcement(actor, announcement, data):
    event = announcement.event
    values = validate_announcement_data(data)
    before = _announcement_state(announcement)
    for key in ("title", "body", "status"):
        setattr(announcement, key, values[key])
    if values["status"] == "published" and announcement.published_at is None:
        announcement.published_at = utc_now()
    elif values["status"] == "draft":
        announcement.published_at = None
    _audit(actor, event, "announcement.updated", "announcement", announcement.id, before, _announcement_state(announcement))
    db.session.commit()
    return announcement


def delete_announcement(actor, announcement):
    event = announcement.event
    before = _announcement_state(announcement)
    _audit(actor, event, "announcement.deleted", "announcement", announcement.id, before=before)
    db.session.delete(announcement)
    db.session.commit()


def create_schedule_item(actor, event, data):
    values = validate_schedule_data(data, event)
    item = ScheduleItem(event_id=event.id, created_by=actor.id, **values)
    db.session.add(item)
    db.session.flush()
    _audit(actor, event, "schedule.created", "schedule_item", item.id, after={"title": item.title, "status": item.status})
    db.session.commit()
    return item


def update_schedule_item(actor, item, data):
    event = item.event
    values = validate_schedule_data(data, event)
    before = {"title": item.title, "status": item.status}
    for key, value in values.items():
        setattr(item, key, value)
    _audit(actor, event, "schedule.updated", "schedule_item", item.id, before, {"title": item.title, "status": item.status})
    db.session.commit()
    return item


def delete_schedule_item(actor, item):
    event = item.event
    _audit(actor, event, "schedule.deleted", "schedule_item", item.id, before={"title": item.title, "status": item.status})
    db.session.delete(item)
    db.session.commit()
