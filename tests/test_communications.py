import re

import pytest

from app.extensions import db
from app.models import Announcement, AuditLog, Event, ScheduleItem, User
from app.services.communications import (
    CommunicationValidationError,
    create_announcement,
    create_schedule_item,
    delete_announcement,
    delete_schedule_item,
    update_announcement,
    update_schedule_item,
)
from app.services.passwords import hash_password
from app.services.time import as_utc


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def communications_fixture(app):
    with app.app_context():
        event = Event(
            name="Communications Event",
            slug="communications-event",
            timezone="Asia/Kolkata",
            status="active",
        )
        other_event = Event(
            name="Other Communications Event",
            slug="other-communications-event",
            timezone="UTC",
            status="active",
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id,
            email="communications-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        participant = User(
            event_id=event.id,
            email="communications-participant@test.example",
            password_hash=hash_password("password"),
            role="participant",
        )
        judge = User(
            event_id=event.id,
            email="communications-judge@test.example",
            password_hash=hash_password("password"),
            role="judge",
        )
        other_organizer = User(
            event_id=other_event.id,
            email="other-communications-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add_all([organizer, participant, judge, other_organizer])
        db.session.commit()
        return {
            "event": event.id,
            "other_event": other_event.id,
            "organizer": organizer.email,
            "participant": participant.email,
            "judge": judge.email,
            "other_organizer": other_organizer.email,
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )
    assert response.status_code == 302


def test_announcement_lifecycle_and_audit(app, communications_fixture):
    with app.app_context():
        event = db.session.get(Event, communications_fixture["event"])
        organizer = User.query.filter_by(email=communications_fixture["organizer"]).one()
        announcement = create_announcement(
            organizer, event, {"title": "Welcome", "body": "Doors open at nine.", "status": "draft"}
        )
        assert announcement.published_at is None
        update_announcement(
            organizer, announcement, {"title": "Welcome", "body": "Doors open at nine.", "status": "published"}
        )
        assert announcement.published_at is not None
        update_announcement(
            organizer, announcement, {"title": "Updated", "body": "New details.", "status": "draft"}
        )
        assert announcement.published_at is None
        delete_announcement(organizer, announcement)
        assert db.session.get(Announcement, announcement.id) is None
        actions = {
            row.action
            for row in AuditLog.query.filter_by(entity_type="announcement").all()
        }
        assert actions == {
            "announcement.created",
            "announcement.updated",
            "announcement.deleted",
        }


def test_schedule_uses_event_timezone_orders_and_audits(app, communications_fixture):
    with app.app_context():
        event = db.session.get(Event, communications_fixture["event"])
        organizer = User.query.filter_by(email=communications_fixture["organizer"]).one()
        item = create_schedule_item(
            organizer,
            event,
            {
                "title": "Opening",
                "description": "Welcome",
                "location": "Main hall",
                "starts_at": "2026-11-01T09:00",
                "ends_at": "2026-11-01T10:00",
                "status": "published",
            },
        )
        assert as_utc(item.starts_at).hour == 3
        update_schedule_item(
            organizer,
            item,
            {
                "title": "Opening updated",
                "description": "",
                "location": "Main hall",
                "starts_at": "2026-11-01T11:00",
                "ends_at": "2026-11-01T12:00",
                "status": "draft",
            },
        )
        assert item.status == "draft"
        delete_schedule_item(organizer, item)
        assert db.session.get(ScheduleItem, item.id) is None
        assert AuditLog.query.filter_by(entity_type="schedule_item").count() == 3


def test_invalid_schedule_range_is_rejected(app, communications_fixture):
    with app.app_context():
        event = db.session.get(Event, communications_fixture["event"])
        organizer = User.query.filter_by(email=communications_fixture["organizer"]).one()
        with pytest.raises(CommunicationValidationError):
            create_schedule_item(
                organizer,
                event,
                {
                    "title": "Invalid",
                    "starts_at": "2026-11-01T12:00",
                    "ends_at": "2026-11-01T11:00",
                    "status": "draft",
                },
            )


def test_routes_visibility_isolation_rbac_and_csrf(client, app, communications_fixture):
    assert client.get("/participant/announcements").status_code == 302
    _login(client, communications_fixture["organizer"])
    assert client.get("/organizer/announcements").status_code == 200
    assert client.get("/organizer/schedule").status_code == 200
    response = client.post(
        "/organizer/announcements/new",
        data={"title": "Draft", "body": "Private", "status": "draft"},
    )
    assert response.status_code == 400
    response = client.post(
        "/organizer/announcements/new",
        data={
            "csrf_token": _token(client.get("/organizer/announcements/new")),
            "title": "Published",
            "body": "Visible update",
            "status": "published",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        announcement = Announcement.query.filter_by(title="Published").one()
        announcement_id = announcement.id
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/organizer/dashboard"))},
    )
    _login(client, communications_fixture["participant"])
    assert client.get("/participant/announcements").status_code == 200
    assert b"Visible update" in client.get("/participant/announcements").data
    assert b"Private" not in client.get("/participant/announcements").data
    assert client.get("/organizer/announcements").status_code == 403
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/participant/dashboard"))},
    )
    _login(client, communications_fixture["judge"])
    assert client.get("/participant/schedule").status_code == 403
    assert client.get(f"/organizer/announcements/{announcement_id}/edit").status_code == 403


def test_organizer_event_isolation(client, communications_fixture):
    _login(client, communications_fixture["organizer"])
    assert client.get("/organizer/announcements/does-not-exist/edit").status_code == 404
    assert client.get("/organizer/schedule/does-not-exist/edit").status_code == 404
