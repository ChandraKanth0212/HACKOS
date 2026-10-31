import re
from datetime import timedelta

import pytest
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import AuditLog, Event, Participant, User
from app.services.passwords import hash_password
from app.services.time import utc_now


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def event_accounts(app):
    with app.app_context():
        now = utc_now()
        event = Event(
            name="Registration Event",
            slug="registration-event",
            timezone="UTC",
            status="active",
            registration_starts_at=now - timedelta(hours=1),
            registration_ends_at=now + timedelta(hours=1),
            capacity=3,
        )
        other_event = Event(
            name="Other Event",
            slug="other-event",
            timezone="UTC",
            status="active",
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id,
            email="organizer-registration@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        participant_user = User(
            event_id=event.id,
            email="participant-registration@test.example",
            password_hash=hash_password("password"),
            role="participant",
        )
        judge = User(
            event_id=event.id,
            email="judge-registration@test.example",
            password_hash=hash_password("password"),
            role="judge",
        )
        other_organizer = User(
            event_id=other_event.id,
            email="other-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add_all([organizer, participant_user, judge, other_organizer])
        db.session.flush()
        own_participant = Participant(
            event_id=event.id,
            user_id=participant_user.id,
            participant_code="OWN-CODE",
            full_name="Own Participant",
            email_normalized=participant_user.email,
            registration_status="confirmed",
        )
        db.session.add(own_participant)
        db.session.commit()
        return {
            "event": event.id,
            "slug": event.slug,
            "other_event": other_event.id,
            "organizer": organizer.email,
            "participant": participant_user.email,
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


def test_public_registration_normalizes_email_hashes_password_and_audits(
    client, app, event_accounts
):
    page = client.get(f"/register/{event_accounts['slug']}")
    response = client.post(
        f"/register/{event_accounts['slug']}",
        data={
            "csrf_token": _token(page),
            "full_name": "New Participant",
            "email": "  NEW@Example.COM ",
            "phone": "555-0100",
            "institution": "Synthetic College",
            "password": "participant-password",
            "registration_status": "confirmed",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        participant = Participant.query.filter_by(
            email_normalized="new@example.com"
        ).one()
        user = db.session.get(User, participant.user_id)
        assert participant.registration_status == "pending"
        assert user.role == "participant"
        assert user.password_hash != "participant-password"
        assert check_password_hash(user.password_hash, "participant-password")
        assert AuditLog.query.filter_by(
            action="participant.created", entity_id=participant.id
        ).count() == 1


def test_duplicate_registration_is_event_scoped_and_rejected(
    client, app, event_accounts
):
    page = client.get(f"/register/{event_accounts['slug']}")
    data = {
        "csrf_token": _token(page),
        "full_name": "Duplicate Participant",
        "email": "participant-registration@test.example",
        "password": "participant-password",
    }
    response = client.post(f"/register/{event_accounts['slug']}", data=data)
    assert response.status_code == 200
    with app.app_context():
        assert Participant.query.filter_by(
            event_id=event_accounts["event"],
            email_normalized="participant-registration@test.example",
        ).count() == 1


def test_organizer_can_list_detail_create_and_edit_participants(
    client, app, event_accounts
):
    _login(client, event_accounts["organizer"])
    assert client.get("/organizer/participants").status_code == 200
    response = client.post(
        "/organizer/participants/new",
        data={
            "csrf_token": _token(client.get("/organizer/participants/new")),
            "full_name": "Organizer Created",
            "email": "CREATED@Example.com",
            "phone": "",
            "institution": "Demo Institute",
            "registration_status": "confirmed",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        participant = Participant.query.filter_by(
            email_normalized="created@example.com"
        ).one()
        participant_id = participant.id
    assert client.get(response.location).status_code == 200
    response = client.post(
        f"/organizer/participants/{participant_id}/edit",
        data={
            "csrf_token": _token(
                client.get(f"/organizer/participants/{participant_id}/edit")
            ),
            "full_name": "Edited Participant",
            "email": "edited@example.com",
            "phone": "",
            "institution": "",
            "registration_status": "cancelled",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        participant = db.session.get(Participant, participant_id)
        assert participant.full_name == "Edited Participant"
        assert participant.registration_status == "cancelled"
        assert AuditLog.query.filter_by(
            action="participant.updated", entity_id=participant_id
        ).count() == 1


@pytest.mark.parametrize("event_change", ("capacity", "window", "status"))
def test_registration_eligibility_is_enforced(client, app, event_accounts, event_change):
    with app.app_context():
        event = db.session.get(Event, event_accounts["event"])
        if event_change == "capacity":
            event.capacity = 1
        elif event_change == "window":
            event.registration_ends_at = utc_now() - timedelta(minutes=1)
        else:
            event.status = "draft"
        db.session.commit()
    page = client.get(f"/register/{event_accounts['slug']}")
    response = client.post(
        f"/register/{event_accounts['slug']}",
        data={
            "csrf_token": _token(page),
            "full_name": f"Blocked {event_change}",
            "email": f"blocked-{event_change}@example.com",
            "password": "participant-password",
        },
    )
    assert response.status_code == 200
    with app.app_context():
        assert Participant.query.filter(
            Participant.email_normalized == f"blocked-{event_change}@example.com"
        ).count() == 0


def test_participant_and_judge_cannot_manage_or_view_other_event_records(
    client, app, event_accounts
):
    _login(client, event_accounts["participant"])
    assert client.get("/organizer/participants").status_code == 403
    assert client.get("/participant/profile").status_code == 200
    with app.app_context():
        foreign = Participant(
            event_id=event_accounts["other_event"],
            participant_code="FOREIGN-CODE",
            full_name="Foreign Participant",
            email_normalized="foreign@example.com",
        )
        db.session.add(foreign)
        db.session.commit()
        foreign_id = foreign.id
    assert client.get(f"/organizer/participants/{foreign_id}").status_code == 403
    dashboard = client.get("/participant/dashboard")
    client.post("/logout", data={"csrf_token": _token(dashboard)})
    _login(client, event_accounts["judge"])
    assert client.get("/organizer/participants").status_code == 403


def test_unauthenticated_and_csrf_protected_participant_routes(client, event_accounts):
    assert client.get("/organizer/participants").status_code == 302
    response = client.post(
        f"/register/{event_accounts['slug']}",
        data={
            "full_name": "No Token",
            "email": "no-token@example.com",
            "password": "participant-password",
        },
    )
    assert response.status_code == 400


def test_participant_codes_are_unique_for_repeated_creations(app, event_accounts):
    with app.app_context():
        event = db.session.get(Event, event_accounts["event"])
        from app.services.participants import create_participant

        first = create_participant(
            event,
            {
                "full_name": "Code One",
                "email": "code-one@example.com",
                "registration_status": "pending",
            },
        )
        second = create_participant(
            event,
            {
                "full_name": "Code Two",
                "email": "code-two@example.com",
                "registration_status": "pending",
            },
        )
        db.session.commit()
        assert first.participant_code != second.participant_code
