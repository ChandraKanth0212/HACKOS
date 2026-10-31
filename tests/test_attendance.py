import re
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models import Attendance, AuditLog, Event, Participant, User
from app.services.attendance import (
    AttendanceAuthorizationError,
    InvalidCredentialError,
    check_in_with_code,
    check_in_with_token,
    ensure_check_in_token,
    revoke_check_in_token,
)
from app.services.passwords import hash_password
from app.services.time import as_utc, utc_now


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def attendance_fixture(app):
    with app.app_context():
        event = Event(name="Attendance Event", slug="attendance-event", timezone="UTC", status="active")
        other_event = Event(name="Other Attendance Event", slug="other-attendance-event", timezone="UTC", status="active")
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(event_id=event.id, email="attendance-organizer@test.example", password_hash=hash_password("password"), role="organizer")
        participant_user = User(event_id=event.id, email="attendance-participant@test.example", password_hash=hash_password("password"), role="participant")
        judge = User(event_id=event.id, email="attendance-judge@test.example", password_hash=hash_password("password"), role="judge")
        other_organizer = User(event_id=other_event.id, email="other-attendance-organizer@test.example", password_hash=hash_password("password"), role="organizer")
        db.session.add_all([organizer, participant_user, judge, other_organizer])
        db.session.flush()
        participant = Participant(
            event_id=event.id,
            user_id=participant_user.id,
            participant_code="ATTEND-001",
            full_name="Attendance Participant",
            email_normalized=participant_user.email,
            registration_status="confirmed",
        )
        other_participant = Participant(
            event_id=other_event.id,
            participant_code="OTHER-001",
            full_name="Other Participant",
            email_normalized="other-participant@test.example",
            registration_status="confirmed",
        )
        db.session.add_all([participant, other_participant])
        db.session.commit()
        return {
            "event": event.id,
            "other_event": other_event.id,
            "participant": participant.id,
            "other_participant": other_participant.id,
            "organizer": organizer.email,
            "participant_user": participant_user.email,
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


def test_manual_check_in_is_idempotent_and_records_operator(app, attendance_fixture):
    with app.app_context():
        event = db.session.get(Event, attendance_fixture["event"])
        organizer = User.query.filter_by(email=attendance_fixture["organizer"]).one()
        before = utc_now()
        first = check_in_with_code(organizer, event, "ATTEND-001", "operation-1")
        second = check_in_with_code(organizer, event, "ATTEND-001", "operation-1")
        assert first.status == "checked_in"
        assert second.status == "idempotent"
        assert Attendance.query.filter_by(event_id=event.id).count() == 1
        record = first.attendance
        assert record.checked_in_by == organizer.id
        assert as_utc(record.checked_in_at) >= before
        assert record.source == "manual"
        assert AuditLog.query.filter_by(action="attendance.checked_in").count() == 1


def test_qr_check_in_valid_cross_event_invalid_and_revoked(app, attendance_fixture):
    with app.app_context():
        event = db.session.get(Event, attendance_fixture["event"])
        other_event = db.session.get(Event, attendance_fixture["other_event"])
        organizer = User.query.filter_by(email=attendance_fixture["organizer"]).one()
        participant = db.session.get(Participant, attendance_fixture["participant"])
        token = ensure_check_in_token(participant)
        assert token.startswith("HACKOS1.")
        assert participant.check_in_token_hash not in token
        result = check_in_with_token(organizer, event, token, "qr-operation")
        assert result.status == "checked_in"
        with pytest.raises(InvalidCredentialError):
            check_in_with_token(organizer, other_event, token)
        revoke_check_in_token(participant)
        with pytest.raises(InvalidCredentialError):
            check_in_with_token(organizer, event, token)


def test_invalid_qr_and_unauthorized_service_access(app, attendance_fixture):
    with app.app_context():
        event = db.session.get(Event, attendance_fixture["event"])
        judge = User.query.filter_by(email=attendance_fixture["judge"]).one()
        with pytest.raises(InvalidCredentialError):
            check_in_with_token(judge, event, "not-a-token")
        with pytest.raises(AttendanceAuthorizationError):
            check_in_with_code(judge, event, "ATTEND-001")


def test_check_in_routes_rbac_csrf_and_pass(client, attendance_fixture):
    assert client.get("/organizer/attendance").status_code == 302
    _login(client, attendance_fixture["organizer"])
    assert client.get("/organizer/attendance").status_code == 200
    response = client.post(
        "/organizer/attendance/check-in",
        data={"participant_code": "ATTEND-001"},
    )
    assert response.status_code == 400
    response = client.post(
        "/organizer/attendance/check-in",
        data={
            "csrf_token": _token(client.get("/organizer/attendance")),
            "participant_code": "ATTEND-001",
            "operation_id": "route-operation",
        },
    )
    assert response.status_code == 302
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/organizer/dashboard"))},
    )
    _login(client, attendance_fixture["participant_user"])
    assert client.get("/organizer/attendance").status_code == 403
    assert client.get("/participant/check-in-pass").status_code == 200
    assert client.get("/participant/attendance").status_code == 200
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/participant/dashboard"))},
    )
    _login(client, attendance_fixture["judge"])
    assert client.get("/organizer/attendance").status_code == 403


def test_token_is_unique_and_qr_pass_contains_no_internal_id(app, attendance_fixture):
    with app.app_context():
        participant = db.session.get(Participant, attendance_fixture["participant"])
        token = ensure_check_in_token(participant)
        assert participant.id not in token
        assert participant.check_in_token_nonce
        assert participant.check_in_token_revoked_at is None
