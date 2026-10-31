import re

import pytest

from app.extensions import db
from app.models import AuditLog, Event, User
from app.services.passwords import hash_password


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match, response.location
    return match.group(1)


@pytest.fixture
def organizer(app):
    with app.app_context():
        event = Event(name="Owned Event", slug="owned-event", timezone="Asia/Kolkata")
        db.session.add(event)
        db.session.flush()
        user = User(
            event_id=event.id,
            email="event-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add(user)
        db.session.commit()
        return user.email


def _login(client, email):
    page = client.get("/login")
    return client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )


def test_organizer_can_list_detail_and_create_event(client, app, organizer):
    _login(client, organizer)
    assert client.get("/organizer/events").status_code == 200
    response = client.post(
        "/organizer/events/new",
        data={
            "csrf_token": _token(client.get("/organizer/events/new")),
            "name": "New Hackathon",
            "description": "A synthetic event",
            "venue": "Demo Hall",
            "timezone": "Asia/Kolkata",
            "starts_at": "2027-01-10T09:00",
            "ends_at": "2027-01-11T18:00",
            "registration_starts_at": "2026-12-01T09:00",
            "registration_ends_at": "2027-01-09T18:00",
            "capacity": "100",
            "team_size_min": "2",
            "team_size_max": "5",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        event = Event.query.filter_by(name="New Hackathon").one()
        assert event.owner_user_id
        assert AuditLog.query.filter_by(action="event.created", entity_id=event.id).count() == 1
    assert client.get(response.headers["Location"]).status_code == 200


def test_event_edit_and_audit(client, app, organizer):
    _login(client, organizer)
    with app.app_context():
        event = Event.query.filter_by(slug="owned-event").one()
        event_id = event.id
    response = client.post(
        f"/organizer/events/{event_id}/edit",
        data={
            "csrf_token": _token(client.get(f"/organizer/events/{event_id}/edit")),
            "name": "Renamed Event",
            "timezone": "UTC",
            "capacity": "50",
            "team_size_min": "1",
            "team_size_max": "4",
            "status": "completed",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        event = db.session.get(Event, event_id)
        assert event.name == "Renamed Event"
        assert AuditLog.query.filter_by(action="event.updated", entity_id=event_id).count() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("name", ""),
        ("capacity", "0"),
        ("team_size_min", "5"),
        ("team_size_max", "1"),
    ),
)
def test_invalid_event_values_are_rejected(client, organizer, field, value):
    _login(client, organizer)
    data = {
        "csrf_token": _token(client.get("/organizer/events/new")),
        "name": "Invalid Event",
        "timezone": "Asia/Kolkata",
        "starts_at": "2027-01-10T09:00",
        "ends_at": "2027-01-11T18:00",
        "capacity": "10",
        "team_size_min": "1",
        "team_size_max": "4",
        "status": "draft",
    }
    data[field] = value
    if field == "team_size_max":
        data["team_size_min"] = "2"
    response = client.post("/organizer/events/new", data=data)
    assert response.status_code == 200
    assert b"Event validation failed" not in response.data


def test_invalid_date_range_is_rejected(client, organizer):
    _login(client, organizer)
    data = {
        "csrf_token": _token(client.get("/organizer/events/new")),
        "name": "Invalid Dates",
        "timezone": "Asia/Kolkata",
        "starts_at": "2027-01-11T09:00",
        "ends_at": "2027-01-10T18:00",
        "status": "draft",
    }
    response = client.post("/organizer/events/new", data=data)
    assert response.status_code == 200
    assert b"Event end must be after the event start." in response.data


def test_participant_judge_and_anonymous_cannot_manage_events(client, app):
    with app.app_context():
        event = Event(name="Access Event", slug="access-event", timezone="UTC")
        db.session.add(event)
        db.session.flush()
        for role, email in (
            ("participant", "event-participant@test.example"),
            ("judge", "event-judge@test.example"),
        ):
            db.session.add(
                User(
                    event_id=event.id,
                    email=email,
                    password_hash=hash_password("password"),
                    role=role,
                )
            )
        db.session.commit()
    assert app.test_client().get("/organizer/events").status_code == 302
