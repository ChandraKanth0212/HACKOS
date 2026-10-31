import csv
import io
import re
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    Attendance,
    AuditLog,
    Evaluation,
    EvaluationScore,
    Event,
    Judge,
    JudgeAssignment,
    Participant,
    RubricCriterion,
    Submission,
    Team,
    TeamMember,
    User,
)
from app.services.passwords import hash_password


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def report_fixture(app):
    with app.app_context():
        event = Event(
            name="Reports Event",
            slug="reports-event",
            timezone="Asia/Kolkata",
            status="active",
        )
        other_event = Event(
            name="Other Event", slug="other-event", timezone="UTC", status="active"
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id,
            email="reports-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        participant_user = User(
            event_id=event.id,
            email="reports-participant@test.example",
            password_hash=hash_password("password"),
            role="participant",
        )
        judge_user = User(
            event_id=event.id,
            email="reports-judge@test.example",
            password_hash=hash_password("password"),
            role="judge",
        )
        other_organizer = User(
            event_id=other_event.id,
            email="other-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add_all(
            [organizer, participant_user, judge_user, other_organizer]
        )
        db.session.flush()
        participant = Participant(
            event_id=event.id,
            user_id=participant_user.id,
            participant_code="REPORT-P1",
            full_name="=Formula, 名称",
            email_normalized=participant_user.email,
            institution="College\nwith comma",
            registration_status="confirmed",
        )
        pending = Participant(
            event_id=event.id,
            participant_code="REPORT-P2",
            full_name="Pending Person",
            email_normalized="pending@test.example",
            registration_status="pending",
        )
        team = Team(
            event_id=event.id,
            team_code="REPORT-T1",
            name="Team, One",
            status="active",
        )
        db.session.add_all([participant, pending, team])
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, participant_id=participant.id))
        db.session.add(
            Attendance(
                event_id=event.id,
                participant_id=participant.id,
                checked_in_by=organizer.id,
                source="manual",
            )
        )
        submission = Submission(
            event_id=event.id,
            team_id=team.id,
            project_title="=Project\nTitle",
            description="Safe description",
            repository_url="https://example.test/repo",
            demo_url="https://example.test/demo",
            updated_by=organizer.id,
        )
        judge = Judge(
            event_id=event.id,
            user_id=judge_user.id,
            display_name='Judge "One"',
        )
        criterion = RubricCriterion(
            event_id=event.id,
            name="Impact",
            max_score=10,
            weight=Decimal("1"),
            display_order=1,
            is_active=True,
        )
        db.session.add_all([submission, judge, criterion])
        db.session.flush()
        assignment = JudgeAssignment(
            event_id=event.id,
            submission_id=submission.id,
            judge_id=judge.id,
            assigned_by=organizer.id,
            status="completed",
        )
        evaluation = Evaluation(
            event_id=event.id,
            submission_id=submission.id,
            judge_id=judge.id,
            status="submitted",
            comments="Private judge comment",
            total_score=Decimal("80"),
        )
        db.session.add_all([assignment, evaluation])
        db.session.flush()
        db.session.add(
            EvaluationScore(
                evaluation_id=evaluation.id, criterion_id=criterion.id, score=8
            )
        )
        db.session.commit()
        return {
            "event": event.id,
            "organizer": organizer.email,
            "participant": participant_user.email,
            "judge": judge_user.email,
            "other_organizer": other_organizer.email,
            "submission": submission.id,
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )
    assert response.status_code == 302


def _rows(response):
    return list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))


@pytest.mark.parametrize(
    "report_type,headers",
    [
        ("participants", ["Participant code", "Name", "Email"]),
        ("teams", ["Team code", "Team name", "Member count"]),
        ("attendance", ["Participant code", "Participant name", "Check-in status"]),
        ("submissions", ["Team name", "Team code", "Project title"]),
        ("judging", ["Judge name", "Team name", "Team code"]),
        ("leaderboard", ["Rank", "Team name", "Project title"]),
    ],
)
def test_each_export_has_stable_headers_and_event_scoped_data(
    client, report_fixture, report_type, headers
):
    _login(client, report_fixture["organizer"])
    response = client.get(f"/organizer/reports/{report_type}.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    rows = _rows(response)
    assert rows[0][: len(headers)] == headers
    assert len(rows) == (3 if report_type in {"participants", "attendance"} else 2)
    assert "password_hash" not in response.data.decode("utf-8")
    assert "Private judge comment" not in response.data.decode("utf-8")
    assert "check_in_token" not in response.data.decode("utf-8")


def test_csv_handles_formula_unicode_commas_quotes_and_newlines(
    client, report_fixture
):
    _login(client, report_fixture["organizer"])
    response = client.get("/organizer/reports/participants.csv")
    rows = _rows(response)
    assert rows[1][1] == "'=Formula, 名称"
    assert rows[1][3] == "College\nwith comma"


def test_reports_metrics_and_export_audit(client, app, report_fixture):
    _login(client, report_fixture["organizer"])
    response = client.get("/organizer/reports")
    assert response.status_code == 200
    assert b"Registered participants" in response.data
    assert b"Attendance" in response.data
    client.get("/organizer/reports/attendance.csv")
    with app.app_context():
        assert AuditLog.query.filter_by(
            event_id=report_fixture["event"], action="report.exported"
        ).count() == 1


def test_reports_are_organizer_only_and_unknown_exports_are_not_available(
    client, report_fixture
):
    _login(client, report_fixture["participant"])
    assert client.get("/organizer/reports").status_code == 403
    assert client.get("/organizer/reports/participants.csv").status_code == 403
    client.post("/logout", data={"csrf_token": _token(client.get("/participant/dashboard"))})
    _login(client, report_fixture["judge"])
    assert client.get("/organizer/reports").status_code == 403
    client.post("/logout", data={"csrf_token": _token(client.get("/judge/dashboard"))})
    _login(client, report_fixture["other_organizer"])
    assert client.get("/organizer/reports/participants.csv").status_code == 200
    assert b"REPORT-P1" not in client.get("/organizer/reports/participants.csv").data
    assert client.get("/organizer/reports/nope.csv").status_code == 404


def test_empty_event_exports_have_headers_only(app, client):
    with app.app_context():
        event = Event(
            name="Empty Event",
            slug="empty-event",
            timezone="UTC",
            status="active",
        )
        organizer = User(
            event=event,
            email="empty-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add_all([event, organizer])
        db.session.commit()
    _login(client, "empty-organizer@test.example")
    rows = _rows(client.get("/organizer/reports/leaderboard.csv"))
    assert len(rows) == 1
