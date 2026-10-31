import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Attendance,
    Evaluation,
    EvaluationScore,
    Event,
    Judge,
    JudgeAssignment,
    Participant,
    RubricCriterion,
    Submission,
    Team,
    User,
)
from app.services.passwords import hash_password
from app.services.time import utc_now

EXPECTED_TABLES = {
    "events",
    "users",
    "participants",
    "teams",
    "team_members",
    "attendance",
    "announcements",
    "schedule_items",
    "submissions",
    "judges",
    "judge_assignments",
    "rubric_criteria",
    "evaluations",
    "evaluation_scores",
    "audit_logs",
    "automation_outbox",
}


def _event():
    event = Event(
        name="Constraint Test Event",
        slug=f"constraint-{uuid.uuid4()}",
        timezone="Asia/Kolkata",
    )
    db.session.add(event)
    db.session.flush()
    return event


def _user(event, email, role="organizer"):
    user = User(
        event_id=event.id,
        email=email,
        password_hash=hash_password("not-the-real-password"),
        role=role,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _participant(event, email, code=None, user=None):
    participant = Participant(
        event_id=event.id,
        user_id=user.id if user else None,
        participant_code=code or secrets_code(),
        full_name="Sample Person",
        email_normalized=email,
        registration_status="confirmed",
    )
    db.session.add(participant)
    db.session.flush()
    return participant


def secrets_code():
    return uuid.uuid4().hex


def _team(event, code="TEAM-X"):
    team = Team(
        event_id=event.id,
        team_code=code,
        name="Test Team",
        status="active",
    )
    db.session.add(team)
    db.session.flush()
    return team


def test_all_expected_tables_exist(app):
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(tables)
    assert len(EXPECTED_TABLES) == 16


def test_foreign_keys_are_enforced(app):
    with pytest.raises(IntegrityError):
        db.session.add(
            User(
                event_id="missing-event",
                email="ghost@hackos.example",
                password_hash=hash_password("x"),
                role="organizer",
            )
        )
        db.session.flush()
    db.session.rollback()


def test_unique_user_email_per_event(app):
    event = _event()
    _user(event, "same@hackos.example")
    with pytest.raises(IntegrityError):
        _user(event, "same@hackos.example")
    db.session.rollback()


def test_unique_participant_email_and_code(app):
    event = _event()
    _participant(event, "p@hackos.example", code="CODE-ONE")
    with pytest.raises(IntegrityError):
        _participant(event, "p@hackos.example", code="CODE-TWO")
    db.session.rollback()

    event = _event()
    _participant(event, "one@hackos.example", code="SHARED-CODE")
    with pytest.raises(IntegrityError):
        _participant(event, "two@hackos.example", code="SHARED-CODE")
    db.session.rollback()


def test_duplicate_attendance_rejected(app):
    event = _event()
    staff = _user(event, "staff@hackos.example")
    participant = _participant(event, "attendee@hackos.example")
    db.session.add(
        Attendance(
            event_id=event.id,
            participant_id=participant.id,
            checked_in_at=utc_now(),
            checked_in_by=staff.id,
            operation_id="op-1",
            source="manual",
        )
    )
    db.session.flush()
    with pytest.raises(IntegrityError):
        db.session.add(
            Attendance(
                event_id=event.id,
                participant_id=participant.id,
                checked_in_at=utc_now(),
                checked_in_by=staff.id,
                operation_id="op-2",
                source="qr",
            )
        )
        db.session.flush()
    db.session.rollback()


def test_duplicate_team_submission_rejected(app):
    event = _event()
    user = _user(event, "lead@hackos.example", role="participant")
    team = _team(event)
    db.session.add(
        Submission(
            event_id=event.id,
            team_id=team.id,
            project_title="First",
            description="Sample description",
            status="submitted",
            updated_by=user.id,
        )
    )
    db.session.flush()
    with pytest.raises(IntegrityError):
        db.session.add(
            Submission(
                event_id=event.id,
                team_id=team.id,
                project_title="Second",
                description="Sample description",
                status="submitted",
                updated_by=user.id,
            )
        )
        db.session.flush()
    db.session.rollback()


def test_duplicate_assignment_and_evaluation_rejected(app):
    event = _event()
    organizer = _user(event, "org@hackos.example")
    judge_user = _user(event, "judge@hackos.example", role="judge")
    participant_user = _user(event, "puser@hackos.example", role="participant")
    team = _team(event, "TEAM-J")
    submission = Submission(
        event_id=event.id,
        team_id=team.id,
        project_title="Judged",
        description="Sample description",
        status="submitted",
        updated_by=participant_user.id,
    )
    db.session.add(submission)
    judge = Judge(
        event_id=event.id,
        user_id=judge_user.id,
        display_name="Judge Sample",
    )
    db.session.add(judge)
    db.session.flush()

    db.session.add(
        JudgeAssignment(
            event_id=event.id,
            submission_id=submission.id,
            judge_id=judge.id,
            assigned_by=organizer.id,
        )
    )
    db.session.flush()
    with pytest.raises(IntegrityError):
        with db.session.begin_nested():
            db.session.add(
                JudgeAssignment(
                    event_id=event.id,
                    submission_id=submission.id,
                    judge_id=judge.id,
                    assigned_by=organizer.id,
                )
            )

    db.session.add(
        Evaluation(
            event_id=event.id,
            submission_id=submission.id,
            judge_id=judge.id,
            status="draft",
        )
    )
    db.session.flush()
    with pytest.raises(IntegrityError):
        with db.session.begin_nested():
            db.session.add(
                Evaluation(
                    event_id=event.id,
                    submission_id=submission.id,
                    judge_id=judge.id,
                    status="submitted",
                )
            )


def test_duplicate_evaluation_score_for_criterion_rejected(app):
    event = _event()
    organizer = _user(event, "org2@hackos.example")
    judge_user = _user(event, "judge2@hackos.example", role="judge")
    participant_user = _user(event, "puser2@hackos.example", role="participant")
    team = _team(event, "TEAM-S")
    submission = Submission(
        event_id=event.id,
        team_id=team.id,
        project_title="Scored",
        description="Sample description",
        status="submitted",
        updated_by=participant_user.id,
    )
    judge = Judge(
        event_id=event.id, user_id=judge_user.id, display_name="Judge Two"
    )
    criterion = RubricCriterion(
        event_id=event.id,
        name="Impact",
        max_score=10,
        weight=1,
        display_order=1,
    )
    db.session.add_all([submission, judge, criterion])
    db.session.flush()
    evaluation = Evaluation(
        event_id=event.id,
        submission_id=submission.id,
        judge_id=judge.id,
        status="draft",
    )
    db.session.add(evaluation)
    db.session.flush()
    db.session.add(
        EvaluationScore(
            evaluation_id=evaluation.id,
            criterion_id=criterion.id,
            score=8,
        )
    )
    db.session.flush()
    with pytest.raises(IntegrityError):
        db.session.add(
            EvaluationScore(
                evaluation_id=evaluation.id,
                criterion_id=criterion.id,
                score=9,
            )
        )
        db.session.flush()
    db.session.rollback()
    assert organizer.id
