import re

import pytest

from app.extensions import db
from app.models import Event, Judge, Participant, User
from app.services.passwords import hash_password


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match, "CSRF token was not rendered"
    return match.group(1)


@pytest.fixture
def accounts(app):
    with app.app_context():
        event = Event(name="Auth Test Event", slug="auth-test", timezone="Asia/Kolkata")
        db.session.add(event)
        db.session.flush()
        users = {}
        for role, email in (
            ("organizer", "organizer@test.example"),
            ("participant", "participant@test.example"),
            ("judge", "judge@test.example"),
        ):
            user = User(
                event_id=event.id,
                email=email,
                password_hash=hash_password("correct-password"),
                role=role,
            )
            db.session.add(user)
            db.session.flush()
            users[role] = user
        db.session.add(
            Participant(
                event_id=event.id,
                user_id=users["participant"].id,
                participant_code="AUTH-PARTICIPANT",
                full_name="Synthetic Participant",
                email_normalized="participant@test.example",
                registration_status="confirmed",
            )
        )
        db.session.add(
            Judge(
                event_id=event.id,
                user_id=users["judge"].id,
                display_name="Synthetic Judge",
            )
        )
        db.session.commit()
        return {role: user.email for role, user in users.items()}


def login(client, email, password="correct-password"):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": _token(page)},
        follow_redirects=False,
    )
    return response


@pytest.mark.parametrize(
    ("role", "path"),
    (
        ("organizer", "/organizer/dashboard"),
        ("participant", "/participant/dashboard"),
        ("judge", "/judge/dashboard"),
    ),
)
def test_role_login_redirects_to_actual_dashboard(client, accounts, role, path):
    response = login(client, accounts[role])
    assert response.status_code == 302, response.get_data(as_text=True)
    assert response.headers["Location"].endswith(path)


def test_incorrect_password_is_generic_and_does_not_login(client, accounts):
    response = login(client, accounts["organizer"], "wrong-password")
    assert response.status_code == 200
    assert b"We could not sign you in with those details." in response.data


def test_unknown_and_inactive_accounts_are_rejected_generically(client, app, accounts):
    unknown = login(client, "unknown@test.example")
    assert unknown.status_code == 200
    assert b"We could not sign you in with those details." in unknown.data
    with app.app_context():
        user = User.query.filter_by(email=accounts["organizer"]).one()
        user.is_active = False
        db.session.commit()
    inactive = login(client, accounts["organizer"])
    assert inactive.status_code == 200
    assert b"We could not sign you in with those details." in inactive.data


def test_login_rejects_external_and_protocol_relative_next_urls(client, accounts):
    for next_url in ("https://evil.example/", "//evil.example/"):
        page = client.get(f"/login?next={next_url}")
        response = client.post(
            f"/login?next={next_url}",
            data={
                "email": accounts["organizer"],
                "password": "correct-password",
                "csrf_token": _token(page),
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/organizer/dashboard")
        dashboard = client.get("/organizer/dashboard")
        client.post(
            "/logout",
            data={"csrf_token": _token(dashboard)},
            follow_redirects=False,
        )


def test_logout_clears_authenticated_session(client, accounts):
    login(client, accounts["organizer"])
    dashboard = client.get("/organizer/dashboard")
    response = client.post(
        "/logout", data={"csrf_token": _token(dashboard)}, follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert client.get("/organizer/dashboard").status_code == 302


def test_unauthenticated_dashboard_redirects_to_login(client):
    response = client.get("/organizer/dashboard")
    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login?next=")


@pytest.mark.parametrize(
    ("login_role", "restricted_path"),
    (
        ("participant", "/organizer/dashboard"),
        ("judge", "/participant/dashboard"),
        ("organizer", "/judge/dashboard"),
    ),
)
def test_cross_role_access_returns_403(client, accounts, login_role, restricted_path):
    login(client, accounts[login_role])
    response = client.get(restricted_path)
    assert response.status_code == 403
    assert b"not in your role" in response.data


def test_login_requires_csrf_token(client, accounts):
    response = client.post(
        "/login",
        data={"email": accounts["organizer"], "password": "correct-password"},
    )
    assert response.status_code == 400


def test_login_has_no_public_role_selector(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"name=\"role\"" not in response.data


@pytest.mark.parametrize(
    "path", ("/organizer/dashboard", "/participant/dashboard", "/judge/dashboard")
)
def test_dashboard_routes_render_live_content(client, accounts, path):
    role = path.split("/")[1]
    login(client, accounts[role])
    response = client.get(path)
    assert response.status_code == 200
    assert b"Sample data" in response.data
