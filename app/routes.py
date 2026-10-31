import json

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user

from app.auth import LogoutForm, judge_required, organizer_required, participant_required
from app.models import (
    Attendance,
    Evaluation,
    JudgeAssignment,
    Participant,
    Submission,
    Team,
)

main = Blueprint("main", __name__)
organizer = Blueprint("organizer", __name__, url_prefix="/organizer")
participant = Blueprint("participant", __name__, url_prefix="/participant")
judge = Blueprint("judge", __name__, url_prefix="/judge")


def _event_is_sample(event):
    if not event or not event.settings_json:
        return False
    try:
        return bool(json.loads(event.settings_json).get("is_synthetic_sample"))
    except (TypeError, ValueError):
        return False


def _dashboard_context():
    event = current_user.event
    return {
        "event": event,
        "is_sample": _event_is_sample(event),
        "logout_form": LogoutForm(),
    }


@main.get("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))
    return render_template("public/home.html")


@organizer.get("/dashboard", endpoint="dashboard")
@organizer_required
def organizer_dashboard():
    event = current_user.event
    metrics = {
        "participants": Participant.query.filter_by(event_id=event.id).count(),
        "teams": Team.query.filter_by(event_id=event.id, status="active").count(),
        "attendance": Attendance.query.filter_by(event_id=event.id).count(),
        "submissions": Submission.query.filter_by(event_id=event.id).count(),
    }
    return render_template(
        "dashboard/organizer.html",
        **_dashboard_context(),
        metrics=metrics,
    )


@participant.get("/dashboard", endpoint="dashboard")
@participant_required
def participant_dashboard():
    profile = current_user.participant
    membership = None
    team = None
    submission = None
    attendance = None
    if profile:
        membership = next(
            (item for item in profile.memberships if item.left_at is None), None
        )
        team = membership.team if membership else None
        submission = team.submission if team else None
        attendance = profile.attendance
    return render_template(
        "dashboard/participant.html",
        **_dashboard_context(),
        team=team,
        submission=submission,
        attendance=attendance,
    )


@judge.get("/dashboard", endpoint="dashboard")
@judge_required
def judge_dashboard():
    judge_profile = current_user.judge
    assignments = []
    pending_count = 0
    if judge_profile:
        assignments = JudgeAssignment.query.filter_by(
            event_id=current_user.event_id, judge_id=judge_profile.id
        ).filter(JudgeAssignment.status != "revoked").all()
        evaluated_ids = {
            evaluation.submission_id
            for evaluation in Evaluation.query.filter_by(judge_id=judge_profile.id).all()
            if evaluation.status == "submitted"
        }
        pending_count = sum(
            assignment.submission_id not in evaluated_ids for assignment in assignments
        )
    return render_template(
        "dashboard/judge.html",
        **_dashboard_context(),
        assigned_count=len(assignments),
        pending_count=pending_count,
    )


@main.app_errorhandler(403)
def forbidden(_error):
    return render_template("errors/403.html"), 403


@main.app_errorhandler(404)
def not_found(_error):
    return render_template("errors/404.html"), 404


def register_routes(app):
    app.register_blueprint(main)
    app.register_blueprint(organizer)
    app.register_blueprint(participant)
    app.register_blueprint(judge)
