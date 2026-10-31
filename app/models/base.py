import uuid

from app.extensions import db
from app.services.time import utc_now


def generate_uuid():
    return str(uuid.uuid4())


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
