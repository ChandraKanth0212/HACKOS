import re

from app.extensions import db
from app.models import Event, User
from app.services.passwords import verify_password


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


def _registration(client, **overrides):
    page = client.get("/register/organizer")
    data = {
        "name": "New Organizer",
        "email": "new-organizer@example.com",
        "password": "StrongPassword123",
        "password_confirmation": "StrongPassword123",
        "csrf_token": _token(page),
    }
    data.update(overrides)
    return client.post("/register/organizer", data=data, follow_redirects=False)


def test_landing_page_exposes_working_host_and_sign_in_entries(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Host a Hackathon" in response.data
    assert b'href="/register/organizer"' in response.data
    assert b'href="/login"' in response.data
    assert b'href="/demo"' in response.data


def test_demo_page_is_public_and_is_synthetic(client):
    response = client.get("/demo")
    assert response.status_code == 200
    assert b"HACKOS Innovation Challenge" in response.data
    assert b"Synthetic walkthrough" in response.data
    assert b"Start Demo" in response.data


def test_organizer_registration_page_is_public_and_csrf_protected(client):
    response = client.get("/register/organizer")
    assert response.status_code == 200
    assert b"Create organizer account" in response.data
    assert b'name="csrf_token"' in response.data


def test_organizer_registration_assigns_role_hashes_password_and_redirects_to_event_creation(
    app, client
):
    response = _registration(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/organizer/events/new")
    with app.app_context():
        user = User.query.filter_by(email="new-organizer@example.com").one()
        assert user.role == "organizer"
        assert user.event_id is None
        assert user.display_name == "New Organizer"
        assert user.password_hash != "StrongPassword123"
        assert verify_password(user.password_hash, "StrongPassword123")


def test_duplicate_organizer_email_is_rejected(client):
    first = _registration(client)
    assert first.status_code == 302
    client.post("/logout", data={"csrf_token": _token(client.get("/organizer/events/new"))})
    duplicate = _registration(client)
    assert duplicate.status_code == 200
    assert b"An account already exists for that email." in duplicate.data


def test_organizer_registration_rejects_weak_password_and_csrf(client):
    weak = _registration(
        client,
        password="passwordpassword",
        password_confirmation="passwordpassword",
    )
    assert weak.status_code == 200
    assert b"Use at least 12 characters" in weak.data
    response = client.post(
        "/register/organizer",
        data={
            "name": "No CSRF",
            "email": "csrf@example.com",
            "password": "StrongPassword123",
            "password_confirmation": "StrongPassword123",
        },
    )
    assert response.status_code == 400


def test_first_event_binds_new_organizer_and_other_organizer_cannot_access(
    app, client
):
    _registration(client)
    page = client.get("/organizer/events/new")
    response = client.post(
        "/organizer/events/new",
        data={
            "name": "Owned Hackathon",
            "timezone": "Asia/Kolkata",
            "status": "draft",
            "csrf_token": _token(page),
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    with app.app_context():
        organizer = User.query.filter_by(email="new-organizer@example.com").one()
        event = Event.query.filter_by(name="Owned Hackathon").one()
        assert organizer.event_id == event.id
        assert event.owner_user_id == organizer.id
