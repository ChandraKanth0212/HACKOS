import re
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import AuditLog, Event, Participant, Submission, Team, TeamMember, User
from app.services.passwords import hash_password
from app.services.submissions import (
    SubmissionConflictError,
    SubmissionValidationError,
    create_submission,
)
from app.services.time import utc_now


def _token(response):
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


@pytest.fixture
def submission_fixture(app):
    with app.app_context():
        event = Event(
            name="Submission Event",
            slug="submission-event",
            timezone="UTC",
            status="active",
            submission_deadline=utc_now() + timedelta(hours=2),
        )
        other_event = Event(
            name="Other Submission Event", slug="other-submission-event", timezone="UTC"
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id, email="submission-organizer@test.example",
            password_hash=hash_password("password"), role="organizer",
        )
        participant_user = User(
            event_id=event.id, email="submission-participant@test.example",
            password_hash=hash_password("password"), role="participant",
        )
        judge = User(
            event_id=event.id, email="submission-judge@test.example",
            password_hash=hash_password("password"), role="judge",
        )
        db.session.add_all([organizer, participant_user, judge])
        db.session.flush()
        participant = Participant(
            event_id=event.id, user_id=participant_user.id,
            participant_code="SUB-001", full_name="Submission Participant",
            email_normalized=participant_user.email, registration_status="confirmed",
        )
        team = Team(
            event_id=event.id, team_code="SUB-TEAM", name="Submission Team",
            status="active",
        )
        db.session.add_all([participant, team])
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, participant_id=participant.id))
        db.session.commit()
        return {
            "event": event.id,
            "organizer": organizer.email,
            "participant": participant_user.email,
            "judge": judge.email,
            "team": team.id,
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login", data={"email": email, "password": "password", "csrf_token": _token(page)}
    )
    assert response.status_code == 302


def _submission_data(token):
    return {
        "csrf_token": token,
        "project_title": "Synthetic Project",
        "description": "A project created for the submission workflow.",
        "repository_url": "https://github.com/example/project",
        "demo_url": "https://demo.example.test/project",
    }


def test_participant_can_create_and_edit_submission_with_audit(client, app, submission_fixture):
    _login(client, submission_fixture["participant"])
    response = client.get("/participant/submission")
    assert response.status_code == 200
    data = _submission_data(_token(response))
    response = client.post("/participant/submission", data=data)
    assert response.status_code == 302
    with app.app_context():
        submission = Submission.query.one()
        submission_id = submission.id
        original_time = submission.submitted_at
        assert submission.status == "submitted"
        assert AuditLog.query.filter_by(action="submission.created").count() == 1
    response = client.post(
        "/participant/submission",
        data={**data, "csrf_token": _token(client.get("/participant/submission")),
              "project_title": "Updated Project"},
    )
    assert response.status_code == 302
    with app.app_context():
        submission = db.session.get(Submission, submission_id)
        assert submission.project_title == "Updated Project"
        assert submission.submitted_at == original_time
        assert AuditLog.query.filter_by(action="submission.updated").count() == 1


def test_submission_validation_duplicate_and_unsafe_url(app, submission_fixture):
    with app.app_context():
        participant = User.query.filter_by(email=submission_fixture["participant"]).one()
        team = db.session.get(Team, submission_fixture["team"])
        with pytest.raises(SubmissionValidationError):
            create_submission(
                participant, team,
                {"project_title": "x", "description": "y", "repository_url": "javascript:alert(1)"},
            )
        create_submission(
            participant, team,
            {"project_title": "x", "description": "y", "repository_url": "https://example.test"},
        )
        with pytest.raises(SubmissionConflictError):
            create_submission(
                participant, team,
                {"project_title": "z", "description": "y"},
            )


def test_organizer_lists_details_and_scopes_access(client, submission_fixture):
    _login(client, submission_fixture["participant"])
    response = client.get("/participant/submission")
    client.post("/participant/submission", data=_submission_data(_token(response)))
    logout_page = client.get("/participant/dashboard")
    client.post("/logout", data={"csrf_token": _token(logout_page)})
    _login(client, submission_fixture["organizer"])
    assert client.get("/organizer/submissions").status_code == 200
    with client.application.app_context():
        submission_id = Submission.query.one().id
    assert client.get(f"/organizer/submissions/{submission_id}").status_code == 200
    logout_page = client.get("/organizer/dashboard")
    client.post("/logout", data={"csrf_token": _token(logout_page)})
    _login(client, submission_fixture["judge"])
    assert client.get("/organizer/submissions").status_code == 403


def test_submission_csrf_and_unauthenticated_access(client, submission_fixture):
    assert client.get("/participant/submission").status_code == 302
    _login(client, submission_fixture["participant"])
    response = client.post("/participant/submission", data=_submission_data("invalid"))
    assert response.status_code == 400
