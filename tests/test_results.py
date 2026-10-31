import re
from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    AuditLog,
    Evaluation,
    Event,
    Judge,
    Participant,
    RubricCriterion,
    Submission,
    Team,
    TeamMember,
    User,
)
from app.services.judging import assign_judge, save_evaluation
from app.services.passwords import hash_password
from app.services.results import aggregate_results, set_results_publication


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def results_fixture(app):
    with app.app_context():
        event = Event(
            name="Results Event",
            slug="results-event",
            timezone="UTC",
            status="active",
            settings_json='{"scoring":{"method":"weighted_criterion_sum_then_average_submitted_judges","missing_scores":"do_not_treat_as_zero"}}',
        )
        other_event = Event(
            name="Other Results Event", slug="other-results-event", timezone="UTC"
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id, email="results-organizer@test.example",
            password_hash=hash_password("password"), role="organizer",
        )
        participant_user = User(
            event_id=event.id, email="results-participant@test.example",
            password_hash=hash_password("password"), role="participant",
        )
        judge_user = User(
            event_id=event.id, email="results-judge@test.example",
            password_hash=hash_password("password"), role="judge",
        )
        other_organizer = User(
            event_id=other_event.id, email="other-results-organizer@test.example",
            password_hash=hash_password("password"), role="organizer",
        )
        db.session.add_all([organizer, participant_user, judge_user, other_organizer])
        db.session.flush()
        judge = Judge(
            event_id=event.id, user_id=judge_user.id, display_name="Results Judge"
        )
        participant = Participant(
            event_id=event.id, user_id=participant_user.id,
            participant_code="RESULTS-PARTICIPANT", full_name="Results Participant",
            email_normalized=participant_user.email, registration_status="confirmed",
        )
        team_one = Team(event_id=event.id, team_code="RESULTS-A", name="Alpha Team", status="active")
        team_two = Team(event_id=event.id, team_code="RESULTS-B", name="Beta Team", status="active")
        team_three = Team(event_id=event.id, team_code="RESULTS-C", name="Gamma Team", status="active")
        db.session.add_all([judge, participant, team_one, team_two, team_three])
        db.session.flush()
        db.session.add(TeamMember(team_id=team_one.id, participant_id=participant.id))
        submissions = [
            Submission(
                event_id=event.id, team_id=team_one.id, project_title="Alpha Project",
                description="Alpha", updated_by=organizer.id,
            ),
            Submission(
                event_id=event.id, team_id=team_two.id, project_title="Beta Project",
                description="Beta", updated_by=organizer.id,
            ),
            Submission(
                event_id=event.id, team_id=team_three.id, project_title="Gamma Project",
                description="Gamma", updated_by=organizer.id,
            ),
        ]
        criterion = RubricCriterion(
            event_id=event.id, name="Impact", max_score=10, weight=Decimal("1"),
            display_order=1, is_active=True,
        )
        db.session.add_all([*submissions, criterion])
        db.session.commit()
        return {
            "event": event.id,
            "organizer": organizer.email,
            "other_organizer": other_organizer.email,
            "participant": participant_user.email,
            "judge": judge_user.email,
            "judge_id": judge.id,
            "submissions": [submission.id for submission in submissions],
            "criterion": criterion.id,
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )
    assert response.status_code == 302


def test_aggregation_excludes_drafts_and_ranks_ties_deterministically(app, results_fixture):
    with app.app_context():
        organizer = User.query.filter_by(email=results_fixture["organizer"]).one()
        judge = User.query.filter_by(email=results_fixture["judge"]).one()
        first, second, third = results_fixture["submissions"]
        assign_judge(organizer, first, results_fixture["judge_id"])
        assign_judge(organizer, second, results_fixture["judge_id"])
        assign_judge(organizer, third, results_fixture["judge_id"])
        save_evaluation(judge, first, {results_fixture["criterion"]: "8"}, "private", submit=True)
        save_evaluation(judge, second, {results_fixture["criterion"]: "8"}, "private", submit=True)
        save_evaluation(judge, third, {results_fixture["criterion"]: "3"}, "draft", submit=False)
        rows = aggregate_results(db.session.get(Event, results_fixture["event"]))
        assert [(row["team"].name, row["rank"], row["average_score"]) for row in rows] == [
            ("Alpha Team", 1, Decimal("80.0000")),
            ("Beta Team", 1, Decimal("80.0000")),
            ("Gamma Team", None, None),
        ]
        assert all("private" not in str(row) for row in rows)


def test_publication_is_audited_and_participant_visibility_is_scoped(
    client, app, results_fixture
):
    _login(client, results_fixture["participant"])
    assert client.get("/participant/results").status_code == 200
    assert b"have not been published" in client.get("/participant/results").data
    assert client.get("/organizer/results").status_code == 403
    page = client.get("/participant/results")
    client.post("/logout", data={"csrf_token": _token(page)})
    _login(client, results_fixture["organizer"])
    page = client.get("/organizer/results")
    response = client.post(
        "/organizer/results",
        data={"csrf_token": _token(page), "published": "1"},
    )
    assert response.status_code == 302
    page = client.get("/organizer/results")
    client.post("/logout", data={"csrf_token": _token(page)})
    _login(client, results_fixture["participant"])
    response = client.get("/participant/results")
    assert response.status_code == 200
    assert b"Alpha Project" in response.data
    with app.app_context():
        event = db.session.get(Event, results_fixture["event"])
        assert event.settings_json and '"results_published": true' in event.settings_json
        assert AuditLog.query.filter_by(
            event_id=event.id, action="results.published"
        ).count() == 1


def test_publication_requires_csrf_and_event_owner(client, results_fixture):
    _login(client, results_fixture["other_organizer"])
    assert client.get("/organizer/results").status_code == 200
    response = client.post("/organizer/results", data={"published": "1"})
    assert response.status_code == 400
