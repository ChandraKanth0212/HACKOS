import re
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    AuditLog,
    Evaluation,
    EvaluationScore,
    Event,
    Judge,
    Participant,
    RubricCriterion,
    Submission,
    Team,
    TeamMember,
    User,
)
from app.services.judging import (
    JudgingError,
    JudgingValidationError,
    assign_judge,
    revoke_assignment,
    save_evaluation,
)
from app.services.passwords import hash_password
from app.services.time import utc_now


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def judging_fixture(app):
    with app.app_context():
        event = Event(
            name="Judging Event",
            slug="judging-event",
            timezone="UTC",
            status="active",
            settings_json='{"scoring":{"method":"weighted_criterion_sum_then_average_submitted_judges","missing_scores":"do_not_treat_as_zero"}}',
            submission_deadline=utc_now() + timedelta(hours=2),
        )
        other_event = Event(
            name="Other Judging Event", slug="other-judging-event", timezone="UTC"
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id, email="judging-organizer@test.example",
            password_hash=hash_password("password"), role="organizer",
        )
        judge_user = User(
            event_id=event.id, email="judging-judge@test.example",
            password_hash=hash_password("password"), role="judge",
        )
        second_judge_user = User(
            event_id=event.id, email="judging-second@test.example",
            password_hash=hash_password("password"), role="judge",
        )
        other_judge_user = User(
            event_id=other_event.id, email="other-judging-judge@test.example",
            password_hash=hash_password("password"), role="judge",
        )
        db.session.add_all(
            [organizer, judge_user, second_judge_user, other_judge_user]
        )
        db.session.flush()
        judge = Judge(
            event_id=event.id, user_id=judge_user.id, display_name="Judge One"
        )
        second_judge = Judge(
            event_id=event.id, user_id=second_judge_user.id, display_name="Judge Two"
        )
        other_judge = Judge(
            event_id=other_event.id,
            user_id=other_judge_user.id,
            display_name="Other Judge",
        )
        team = Team(
            event_id=event.id, team_code="JUDGE-TEAM", name="Judging Team", status="active"
        )
        db.session.add_all([judge, second_judge, other_judge, team])
        db.session.flush()
        participant = Participant(
            event_id=event.id,
            participant_code="JUDGE-PARTICIPANT",
            full_name="Judging Participant",
            email_normalized="judging-participant@test.example",
            registration_status="confirmed",
        )
        db.session.add(participant)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, participant_id=participant.id))
        submission = Submission(
            event_id=event.id,
            team_id=team.id,
            project_title="Judging Project",
            description="A synthetic project.",
            status="submitted",
            updated_by=organizer.id,
        )
        criterion_one = RubricCriterion(
            event_id=event.id, name="Impact", max_score=10, weight=Decimal("0.6"),
            display_order=1, is_active=True,
        )
        criterion_two = RubricCriterion(
            event_id=event.id, name="Execution", max_score=20, weight=Decimal("0.4"),
            display_order=2, is_active=True,
        )
        db.session.add_all([submission, criterion_one, criterion_two])
        db.session.commit()
        return {
            "event": event.id,
            "other_event": other_event.id,
            "organizer": organizer.email,
            "judge": judge_user.email,
            "second_judge": second_judge_user.email,
            "other_judge": other_judge_user.email,
            "judge_id": judge.id,
            "second_judge_id": second_judge.id,
            "other_judge_id": other_judge.id,
            "submission": submission.id,
            "criterion_one": criterion_one.id,
            "criterion_two": criterion_two.id,
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )
    assert response.status_code == 302


def _logout(client, role="judge"):
    page = client.get(f"/{role}/dashboard")
    response = client.post("/logout", data={"csrf_token": _token(page)})
    assert response.status_code == 302


def test_assignment_lifecycle_is_scoped_and_audited(app, judging_fixture):
    with app.app_context():
        organizer = User.query.filter_by(email=judging_fixture["organizer"]).one()
        assignment = assign_judge(
            organizer, judging_fixture["submission"], judging_fixture["judge_id"]
        )
        with pytest.raises(JudgingError, match="already assigned"):
            assign_judge(
                organizer, judging_fixture["submission"], judging_fixture["judge_id"]
            )
        with pytest.raises(JudgingError, match="same event"):
            assign_judge(
                organizer,
                judging_fixture["submission"],
                judging_fixture["other_judge_id"],
            )
        revoke_assignment(organizer, assignment.id)
        assert assignment.status == "revoked"
        reactivated = assign_judge(
            organizer, judging_fixture["submission"], judging_fixture["judge_id"]
        )
        assert reactivated.id == assignment.id
        assert reactivated.status == "assigned"
        assert AuditLog.query.filter(
            AuditLog.action.in_(
                ["judge.assignment_created", "judge.assignment_revoked"]
            )
        ).count() == 2


def test_evaluation_validates_scores_missing_criteria_and_formula(app, judging_fixture):
    with app.app_context():
        organizer = User.query.filter_by(email=judging_fixture["organizer"]).one()
        judge = User.query.filter_by(email=judging_fixture["judge"]).one()
        assign_judge(organizer, judging_fixture["submission"], judging_fixture["judge_id"])
        with pytest.raises(JudgingValidationError):
            save_evaluation(
                judge,
                judging_fixture["submission"],
                {judging_fixture["criterion_one"]: "11"},
                "",
                submit=True,
            )
        draft = save_evaluation(
            judge,
            judging_fixture["submission"],
            {judging_fixture["criterion_one"]: "8"},
            "Draft note",
            submit=False,
        )
        assert draft.status == "draft"
        with pytest.raises(JudgingValidationError):
            save_evaluation(
                judge,
                judging_fixture["submission"],
                {judging_fixture["criterion_one"]: "8"},
                "",
                submit=True,
            )
        evaluation = save_evaluation(
            judge,
            judging_fixture["submission"],
            {
                judging_fixture["criterion_one"]: "8",
                judging_fixture["criterion_two"]: "15",
            },
            "Final note",
            submit=True,
        )
        assert evaluation.status == "submitted"
        assert evaluation.total_score == Decimal("78.0000")
        with pytest.raises(JudgingError, match="read-only"):
            save_evaluation(
                judge,
                judging_fixture["submission"],
                {
                    judging_fixture["criterion_one"]: "1",
                    judging_fixture["criterion_two"]: "1",
                },
                "Changed",
                submit=True,
            )
        assert AuditLog.query.filter_by(action="evaluation.submitted").count() == 1


def test_unassigned_judge_cannot_evaluate_and_duplicate_scores_are_blocked(
    app, judging_fixture
):
    with app.app_context():
        judge = User.query.filter_by(email=judging_fixture["judge"]).one()
        with pytest.raises(JudgingError, match="not assigned"):
            save_evaluation(
                judge,
                judging_fixture["submission"],
                {},
                "",
                submit=False,
            )
        organizer = User.query.filter_by(email=judging_fixture["organizer"]).one()
        assign_judge(organizer, judging_fixture["submission"], judging_fixture["judge_id"])
        evaluation = save_evaluation(
            judge,
            judging_fixture["submission"],
            {judging_fixture["criterion_one"]: "5"},
            "",
            submit=False,
        )
        db.session.add(
            EvaluationScore(
                evaluation_id=evaluation.id,
                criterion_id=judging_fixture["criterion_one"],
                score=Decimal("6"),
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_judge_routes_are_private_and_csrf_protected(client, app, judging_fixture):
    assert client.get("/judge/assignments").status_code == 302
    _login(client, judging_fixture["organizer"])
    assert client.get("/judge/assignments").status_code == 403
    _logout(client, "organizer")
    _login(client, judging_fixture["judge"])
    assert client.get("/judge/assignments").status_code == 200
    assert client.get(
        f"/judge/assignments/{judging_fixture['submission']}/evaluate"
    ).status_code == 403
    _logout(client)
    _login(client, judging_fixture["organizer"])
    response = client.post(
        "/organizer/judging/assign",
        data={
            "submission_id": judging_fixture["submission"],
            "judge_id": judging_fixture["judge_id"],
        },
    )
    assert response.status_code == 400
    page = client.get("/organizer/judging")
    response = client.post(
        "/organizer/judging/assign",
        data={
            "csrf_token": _token(page),
            "submission_id": judging_fixture["submission"],
            "judge_id": judging_fixture["judge_id"],
        },
    )
    assert response.status_code == 302
    _logout(client, "organizer")
    _login(client, judging_fixture["judge"])
    page = client.get(
        f"/judge/assignments/{judging_fixture['submission']}/evaluate"
    )
    response = client.post(
        f"/judge/assignments/{judging_fixture['submission']}/evaluate",
        data={
            "csrf_token": _token(page),
            "submit_action": "submit",
            judging_fixture["criterion_one"]: "8",
            judging_fixture["criterion_two"]: "15",
            "comments": "Clear submission.",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert Evaluation.query.one().status == "submitted"
