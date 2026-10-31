import csv
import io
import json
import re

from app.extensions import db
from app.models import (
    Attendance,
    AuditLog,
    Evaluation,
    JudgeAssignment,
    Participant,
    Submission,
    Team,
)
from app.services.results import aggregate_results, results_are_published
from app.services.time import to_event_timezone, utc_now


REPORT_TYPES = (
    "participants",
    "teams",
    "attendance",
    "submissions",
    "judging",
    "leaderboard",
)


class ReportError(ValueError):
    pass


def _event_local(value, event):
    if value is None:
        return ""
    return to_event_timezone(value, event.timezone).strftime("%Y-%m-%d %H:%M:%S %Z")


def _csv_value(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _write_csv(headers, rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_value(value) for value in row])
    return "\ufeff" + output.getvalue()


def _assert_actor_event(actor, event):
    if actor.role != "organizer" or actor.event_id != event.id:
        raise ReportError("You are not authorized to access this report.")


def _active_members(team):
    return sorted(
        (
            member.participant.full_name
            for member in team.members
            if member.left_at is None and member.participant is not None
        ),
        key=str.casefold,
    )


def _participant_rows(event):
    participants = Participant.query.filter_by(event_id=event.id).order_by(
        Participant.created_at.asc(), Participant.id.asc()
    )
    return [
        (
            participant.participant_code,
            participant.full_name,
            participant.email_normalized,
            participant.institution,
            participant.registration_status,
            _event_local(participant.created_at, event),
        )
        for participant in participants
    ]


def _team_rows(event):
    teams = Team.query.filter_by(event_id=event.id).order_by(
        Team.created_at.asc(), Team.id.asc()
    )
    return [
        (
            team.team_code,
            team.name,
            len(_active_members(team)),
            team.status,
            ", ".join(_active_members(team)),
        )
        for team in teams
    ]


def _attendance_rows(event):
    participants = Participant.query.filter_by(event_id=event.id).order_by(
        Participant.full_name.asc(), Participant.id.asc()
    )
    records = {
        record.participant_id: record
        for record in Attendance.query.filter_by(event_id=event.id).all()
    }
    return [
        (
            participant.participant_code,
            participant.full_name,
            "Checked in" if records.get(participant.id) else "Not checked in",
            _event_local(
                records[participant.id].checked_in_at, event
            )
            if participant.id in records
            else "",
            records[participant.id].staff_user.email
            if participant.id in records and records[participant.id].staff_user
            else "",
        )
        for participant in participants
    ]


def _submission_rows(event):
    submissions = Submission.query.filter_by(event_id=event.id).join(
        Submission.team
    ).order_by(Team.name.asc(), Submission.id.asc())
    return [
        (
            submission.team.name,
            submission.team.team_code,
            submission.project_title,
            submission.status,
            _event_local(submission.submitted_at, event),
            "Late" if submission.status == "late" else "On time",
            submission.repository_url,
            submission.demo_url,
        )
        for submission in submissions
    ]


def _judging_rows(event):
    assignments = JudgeAssignment.query.filter_by(event_id=event.id).join(
        JudgeAssignment.submission
    ).join(JudgeAssignment.judge).order_by(
        JudgeAssignment.assigned_at.asc(), JudgeAssignment.id.asc()
    )
    evaluations = {
        (evaluation.submission_id, evaluation.judge_id): evaluation
        for evaluation in Evaluation.query.filter_by(event_id=event.id).all()
    }
    return [
        (
            assignment.judge.display_name,
            assignment.submission.team.name,
            assignment.submission.team.team_code,
            assignment.status,
            evaluations.get(
                (assignment.submission_id, assignment.judge_id)
            ).status
            if evaluations.get((assignment.submission_id, assignment.judge_id))
            else "Not started",
            _event_local(
                evaluations[
                    (assignment.submission_id, assignment.judge_id)
                ].submitted_at,
                event,
            )
            if (
                assignment.submission_id,
                assignment.judge_id,
            )
            in evaluations
            and evaluations[
                (assignment.submission_id, assignment.judge_id)
            ].submitted_at
            else "",
            evaluations[
                (assignment.submission_id, assignment.judge_id)
            ].total_score
            if (
                assignment.submission_id,
                assignment.judge_id,
            )
            in evaluations
            and evaluations[
                (assignment.submission_id, assignment.judge_id)
            ].status
            == "submitted"
            else "",
        )
        for assignment in assignments
    ]


def _leaderboard_rows(event):
    return [
        (
            row["rank"] if row["rank"] is not None else "Pending",
            row["team"].name,
            row["submission"].project_title,
            row["average_score"] if row["average_score"] is not None else "",
            row["judge_count"],
            "Evaluated" if row["rank"] is not None else "Pending",
        )
        for row in aggregate_results(event)
    ]


_REPORT_DEFINITIONS = {
    "participants": (
        (
            "Participant code",
            "Name",
            "Email",
            "Organization/college",
            "Registration status",
            "Registration timestamp",
        ),
        _participant_rows,
    ),
    "teams": (
        ("Team code", "Team name", "Member count", "Team status", "Member names"),
        _team_rows,
    ),
    "attendance": (
        (
            "Participant code",
            "Participant name",
            "Check-in status",
            "Check-in timestamp",
            "Checked-in operator",
        ),
        _attendance_rows,
    ),
    "submissions": (
        (
            "Team name",
            "Team code",
            "Project title",
            "Submission status",
            "Submitted timestamp",
            "Late/on-time status",
            "Repository URL",
            "Demo URL",
        ),
        _submission_rows,
    ),
    "judging": (
        (
            "Judge name",
            "Team name",
            "Team code",
            "Assignment status",
            "Evaluation status",
            "Submitted timestamp",
            "Final score",
        ),
        _judging_rows,
    ),
    "leaderboard": (
        (
            "Rank",
            "Team name",
            "Project title",
            "Final score",
            "Submitted judge count",
            "Status",
        ),
        _leaderboard_rows,
    ),
}


def export_report(actor, event, report_type):
    _assert_actor_event(actor, event)
    if report_type not in _REPORT_DEFINITIONS:
        raise ReportError("Unknown report type.")
    headers, row_factory = _REPORT_DEFINITIONS[report_type]
    content = _write_csv(headers, row_factory(event))
    db.session.add(
        AuditLog(
            event_id=event.id,
            actor_user_id=actor.id,
            action="report.exported",
            entity_type="report",
            entity_id=report_type,
            before_json=None,
            after_json=json.dumps({"report_type": report_type}),
            created_at=utc_now(),
        )
    )
    db.session.commit()
    return content


def report_metrics(actor, event):
    _assert_actor_event(actor, event)
    participants = Participant.query.filter_by(event_id=event.id).all()
    teams = Team.query.filter_by(event_id=event.id).all()
    attendance_count = Attendance.query.filter_by(event_id=event.id).count()
    submissions = Submission.query.filter_by(event_id=event.id).all()
    assignments = JudgeAssignment.query.filter_by(event_id=event.id).all()
    evaluations = Evaluation.query.filter_by(event_id=event.id).all()
    active_member_counts = [len(_active_members(team)) for team in teams]
    return {
        "participants": {
            "total": len(participants),
            "confirmed": sum(
                participant.registration_status == "confirmed"
                for participant in participants
            ),
            "pending": sum(
                participant.registration_status == "pending"
                for participant in participants
            ),
            "cancelled": sum(
                participant.registration_status == "cancelled"
                for participant in participants
            ),
        },
        "teams": {
            "total": len(teams),
            "average_size": (
                sum(active_member_counts) / len(active_member_counts)
                if active_member_counts
                else None
            ),
        },
        "attendance": {
            "checked_in": attendance_count,
            "not_checked_in": max(len(participants) - attendance_count, 0),
        },
        "submissions": {
            "total": len(submissions),
            "late": sum(submission.status == "late" for submission in submissions),
        },
        "judging": {
            "assignments_total": len(assignments),
            "assignments_completed": sum(
                assignment.status == "completed" for assignment in assignments
            ),
            "evaluations_total": len(evaluations),
            "evaluations_submitted": sum(
                evaluation.status == "submitted" for evaluation in evaluations
            ),
        },
        "results_published": results_are_published(event),
    }


def report_filename(event, report_type):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", event.slug).strip("-") or "event"
    return f"{slug}-{report_type}.csv"
