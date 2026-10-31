from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DEFAULT_EVENT_TIMEZONE = "Asia/Kolkata"


def utc_now():
    return datetime.now(timezone.utc)


def as_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_event_timezone(value, timezone_name=DEFAULT_EVENT_TIMEZONE):
    return as_utc(value).astimezone(ZoneInfo(timezone_name))
