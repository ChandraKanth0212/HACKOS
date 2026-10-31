import json

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from app.auth import LogoutForm, judge_required, organizer_required, participant_required
from app.extensions import db
from app.models import (
    Attendance,
    Announcement,
    Event,
    Evaluation,
    Judge,
    JudgeAssignment,
    RubricCriterion,
    Participant,
    Submission,
    ScheduleItem,
    Team,
    TeamMember,
)
from app.forms import EventForm
from app.forms_attendance import AttendanceCheckInForm, QRCheckInForm
from app.forms_communications import AnnouncementForm, ScheduleItemForm
from app.forms_participants import ParticipantForm, RegistrationForm
from app.forms_submissions import SubmissionForm
from app.forms_teams import MembershipForm, TeamForm, TransferForm
from app.services.participants import (
    ParticipantRegistrationError,
    ParticipantValidationError,
    create_participant,
    normalize_email,
    register_participant,
    registration_is_open,
    update_participant,
)
from app.services.events import (
    EventValidationError,
    audit_event,
    event_form_data,
    unique_slug,
    validate_event_data,
)
from app.services.teams import (
    MembershipError,
    TeamValidationError,
    add_member,
    create_team,
    remove_member,
    transfer_member,
    update_team,
)
from app.services.attendance import (
    AttendanceError,
    InvalidCredentialError,
    check_in_with_code,
    check_in_with_token,
    ensure_check_in_token,
    qr_svg_data_uri,
)
from app.services.communications import (
    CommunicationValidationError,
    create_announcement,
    create_schedule_item,
    delete_announcement,
    delete_schedule_item,
    update_announcement,
    update_schedule_item,
)
from app.services.time import to_event_timezone
from app.services.submissions import (
    SubmissionAuthorizationError,
    SubmissionConflictError,
    SubmissionValidationError,
    create_submission,
    update_submission,
)
from app.forms_judging import AssignmentForm, EvaluationForm
from app.services.judging import (
    JudgingError,
    JudgingValidationError,
    assign_judge,
    revoke_assignment,
    save_evaluation,
)
from app.services.results import (
    ResultsError,
    aggregate_results,
    results_are_published,
    set_results_publication,
)
from app.services.reports import (
    REPORT_TYPES,
    ReportError,
    export_report,
    report_filename,
    report_metrics,
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


def _dashboard_context(event_override=None):
    event = event_override or current_user.event
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


@main.get("/demo")
def demo():
    return render_template("public/demo.html")


@main.route("/register/<event_slug>", methods=["GET", "POST"])
def participant_register(event_slug):
    event = Event.query.filter_by(slug=event_slug).first_or_404()
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            register_participant(
                event, {**form.data, "registration_status": "pending"}
            )
        except (ParticipantValidationError, ParticipantRegistrationError) as error:
            if isinstance(error, ParticipantValidationError):
                for field, message in error.errors.items():
                    if hasattr(form, field):
                        getattr(form, field).errors.append(message)
            else:
                form.email.errors.append(str(error))
        else:
            flash("Registration received. You can sign in after confirmation.", "success")
            return redirect(url_for("auth.login"))
    return render_template(
        "participants/register.html",
        form=form,
        event=event,
        registration_open=registration_is_open(event),
    )


@organizer.get("/dashboard", endpoint="dashboard")
@organizer_required
def organizer_dashboard():
    if current_user.event is None:
        return redirect(url_for("organizer.event_create"))
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


@organizer.get("/attendance", endpoint="attendance")
@organizer_required
def attendance_dashboard():
    event = current_user.event
    query = Participant.query.filter_by(event_id=event.id)
    search = request.args.get("q", "").strip()
    if search:
        normalized = normalize_email(search)
        query = query.filter(
            db.or_(
                Participant.full_name.ilike(f"%{search}%"),
                Participant.email_normalized.ilike(f"%{normalized}%"),
                Participant.participant_code.ilike(f"%{search}%"),
            )
        )
    participants = query.order_by(Participant.full_name.asc()).all()
    records = {
        record.participant_id: record
        for record in Attendance.query.filter_by(event_id=event.id).all()
    }
    return render_template(
        "organizer/attendance.html",
        **_dashboard_context(),
        participants=participants,
        attendance_records=records,
        search=search,
        checked_in_count=len(records),
        total_count=Participant.query.filter_by(event_id=event.id).count(),
        check_in_form=AttendanceCheckInForm(),
        qr_form=QRCheckInForm(),
    )


@organizer.post("/attendance/check-in", endpoint="attendance_check_in")
@organizer_required
def attendance_check_in():
    form = AttendanceCheckInForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        result = check_in_with_code(
            current_user,
            current_user.event,
            form.participant_code.data,
            form.operation_id.data,
        )
    except (AttendanceError, InvalidCredentialError) as error:
        flash(str(error), "danger")
    else:
        message = {
            "checked_in": "Participant checked in successfully.",
            "duplicate": "Participant is already checked in.",
            "idempotent": "Check-in was already processed.",
        }[result.status]
        flash(message, "success" if result.status == "checked_in" else "info")
    return redirect(url_for("organizer.attendance", q=form.participant_code.data))


@organizer.post("/attendance/check-in/qr", endpoint="attendance_check_in_qr")
@organizer_required
def attendance_check_in_qr():
    form = QRCheckInForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        result = check_in_with_token(
            current_user,
            current_user.event,
            form.token.data,
            form.operation_id.data,
        )
    except (AttendanceError, InvalidCredentialError) as error:
        flash(str(error), "danger")
    else:
        message = {
            "checked_in": "QR check-in recorded.",
            "duplicate": "Participant is already checked in.",
            "idempotent": "QR check-in was already processed.",
        }[result.status]
        flash(message, "success" if result.status == "checked_in" else "info")
    return redirect(url_for("organizer.attendance"))


def _managed_announcement(announcement_id):
    return Announcement.query.filter_by(
        id=announcement_id, event_id=current_user.event_id
    ).first_or_404()


def _managed_schedule_item(item_id):
    return ScheduleItem.query.filter_by(
        id=item_id, event_id=current_user.event_id
    ).first_or_404()


def _communication_form_errors(form, error):
    for field, message in error.errors.items():
        if hasattr(form, field):
            getattr(form, field).errors.append(message)


def _submission_form_errors(form, error):
    for field, message in error.errors.items():
        if hasattr(form, field):
            getattr(form, field).errors.append(message)


def _managed_submission(submission_id):
    return Submission.query.filter_by(
        id=submission_id, event_id=current_user.event_id
    ).first_or_404()


@organizer.get("/submissions", endpoint="submissions")
@organizer_required
def submission_list():
    query = Submission.query.filter_by(event_id=current_user.event_id)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    if search:
        query = query.join(Team).filter(
            db.or_(
                Team.name.ilike(f"%{search}%"),
                Team.team_code.ilike(f"%{search}%"),
                Submission.project_title.ilike(f"%{search}%"),
            )
        )
    if status:
        query = query.filter_by(status=status)
    submissions = query.order_by(Submission.submitted_at.desc()).all()
    return render_template(
        "organizer/submissions/list.html",
        **_dashboard_context(),
        submissions=submissions,
        search=search,
        status=status,
        event_timezone=current_user.event.timezone,
        to_event_timezone=to_event_timezone,
    )


@organizer.get("/submissions/<submission_id>", endpoint="submission_detail")
@organizer_required
def submission_detail(submission_id):
    return render_template(
        "organizer/submissions/detail.html",
        **_dashboard_context(),
        submission=_managed_submission(submission_id),
        event_timezone=current_user.event.timezone,
        to_event_timezone=to_event_timezone,
    )


@organizer.route(
    "/submissions/<submission_id>/edit",
    methods=["GET", "POST"],
    endpoint="submission_edit",
)
@organizer_required
def submission_edit(submission_id):
    submission = _managed_submission(submission_id)
    form = SubmissionForm(
        data={
            "project_title": submission.project_title,
            "description": submission.description,
            "repository_url": submission.repository_url or "",
            "demo_url": submission.demo_url or "",
        }
    )
    if form.validate_on_submit():
        try:
            update_submission(current_user, submission, form.data)
        except SubmissionValidationError as error:
            _submission_form_errors(form, error)
        except (SubmissionAuthorizationError, SubmissionConflictError) as error:
            flash(str(error), "danger")
        else:
            flash("Submission updated successfully.", "success")
            return redirect(
                url_for("organizer.submission_detail", submission_id=submission.id)
            )
    return render_template(
        "organizer/submissions/form.html",
        **_dashboard_context(),
        form=form,
        heading="Edit submission",
        submission=submission,
    )


@organizer.get("/judging", endpoint="judging")
@organizer_required
def judging_dashboard():
    event_id = current_user.event_id
    judges = Judge.query.filter_by(event_id=event_id).order_by(Judge.display_name.asc()).all()
    submissions = Submission.query.filter_by(event_id=event_id).order_by(
        Submission.project_title.asc()
    ).all()
    assignments = JudgeAssignment.query.filter_by(event_id=event_id).order_by(
        JudgeAssignment.assigned_at.desc()
    ).all()
    assignment_form = AssignmentForm()
    assignment_form.judge_id.choices = [(judge.id, judge.display_name) for judge in judges]
    assignment_form.submission_id.choices = [
        (submission.id, f"{submission.team.name} — {submission.project_title}")
        for submission in submissions
    ]
    return render_template(
        "organizer/judging.html",
        **_dashboard_context(),
        judges=judges,
        submissions=submissions,
        assignments=assignments,
        assignment_form=assignment_form,
    )


@organizer.post("/judging/assign", endpoint="judging_assign")
@organizer_required
def judging_assign():
    form = AssignmentForm()
    form.judge_id.choices = [
        (judge.id, judge.display_name)
        for judge in Judge.query.filter_by(event_id=current_user.event_id).all()
    ]
    form.submission_id.choices = [
        (submission.id, f"{submission.team.name} — {submission.project_title}")
        for submission in Submission.query.filter_by(
            event_id=current_user.event_id
        ).all()
    ]
    if not form.validate_on_submit():
        abort(400)
    try:
        assign_judge(current_user, form.submission_id.data, form.judge_id.data)
    except JudgingError as error:
        flash(str(error), "danger")
    else:
        flash("Judge assigned successfully.", "success")
    return redirect(url_for("organizer.judging"))


@organizer.post("/judging/<assignment_id>/revoke", endpoint="judging_revoke")
@organizer_required
def judging_revoke(assignment_id):
    form = LogoutForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        revoke_assignment(current_user, assignment_id)
    except JudgingError as error:
        flash(str(error), "danger")
    else:
        flash("Judge assignment revoked.", "success")
    return redirect(url_for("organizer.judging"))


@organizer.get(
    "/judging/evaluations/<evaluation_id>", endpoint="judging_evaluation_detail"
)
@organizer_required
def judging_evaluation_detail(evaluation_id):
    evaluation = Evaluation.query.filter_by(
        id=evaluation_id, event_id=current_user.event_id
    ).first_or_404()
    return render_template(
        "organizer/evaluation_detail.html",
        **_dashboard_context(),
        evaluation=evaluation,
    )


@organizer.route("/results", methods=["GET", "POST"], endpoint="results")
@organizer_required
def organizer_results():
    publication_form = LogoutForm()
    if publication_form.validate_on_submit():
        published = request.form.get("published") == "1"
        try:
            set_results_publication(current_user, current_user.event, published)
        except ResultsError as error:
            flash(str(error), "danger")
        else:
            flash(
                "Results published." if published else "Results unpublished.",
                "success",
            )
        return redirect(url_for("organizer.results"))
    return render_template(
        "organizer/results.html",
        **_dashboard_context(),
        rows=aggregate_results(current_user.event),
        published=results_are_published(current_user.event),
        publication_form=publication_form,
    )


@participant.get("/results", endpoint="results")
@participant_required
def participant_results():
    event = current_user.event
    own_team = None
    if current_user.participant:
        membership = TeamMember.query.filter_by(
            participant_id=current_user.participant.id, left_at=None
        ).first()
        own_team = membership.team if membership else None
    return render_template(
        "participants/results.html",
        **_dashboard_context(),
        rows=aggregate_results(event) if results_are_published(event) else [],
        published=results_are_published(event),
        own_team=own_team,
    )


@organizer.get("/reports", endpoint="reports")
@organizer_required
def organizer_reports():
    return render_template(
        "organizer/reports.html",
        **_dashboard_context(),
        metrics=report_metrics(current_user, current_user.event),
        report_types=REPORT_TYPES,
    )


@organizer.get("/reports/<report_type>.csv", endpoint="report_export")
@organizer_required
def organizer_report_export(report_type):
    try:
        content = export_report(current_user, current_user.event, report_type)
    except ReportError:
        abort(404)
    response = make_response(content)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{report_filename(current_user.event, report_type)}"'
    )
    return response


@organizer.get("/announcements", endpoint="announcements")
@organizer_required
def announcement_list():
    announcements = Announcement.query.filter_by(
        event_id=current_user.event_id
    ).order_by(Announcement.created_at.desc()).all()
    return render_template(
        "organizer/announcements/list.html",
        **_dashboard_context(),
        announcements=announcements,
    )


@organizer.route(
    "/announcements/new", methods=["GET", "POST"], endpoint="announcement_create"
)
@organizer_required
def announcement_create():
    form = AnnouncementForm()
    if form.validate_on_submit():
        try:
            announcement = create_announcement(
                current_user, current_user.event, form.data
            )
        except CommunicationValidationError as error:
            _communication_form_errors(form, error)
        else:
            flash("Announcement created successfully.", "success")
            return redirect(
                url_for(
                    "organizer.announcement_edit",
                    announcement_id=announcement.id,
                )
            )
    return render_template(
        "organizer/announcements/form.html",
        **_dashboard_context(),
        form=form,
        heading="Create announcement",
    )


@organizer.route(
    "/announcements/<announcement_id>/edit",
    methods=["GET", "POST"],
    endpoint="announcement_edit",
)
@organizer_required
def announcement_edit(announcement_id):
    announcement = _managed_announcement(announcement_id)
    form = AnnouncementForm(
        data={
            "title": announcement.title,
            "body": announcement.body,
            "status": announcement.status,
        }
    )
    if form.validate_on_submit():
        try:
            update_announcement(current_user, announcement, form.data)
        except CommunicationValidationError as error:
            _communication_form_errors(form, error)
        else:
            flash("Announcement updated successfully.", "success")
            return redirect(url_for("organizer.announcements"))
    return render_template(
        "organizer/announcements/form.html",
        **_dashboard_context(),
        form=form,
        heading="Edit announcement",
        announcement=announcement,
    )


@organizer.post(
    "/announcements/<announcement_id>/delete", endpoint="announcement_delete"
)
@organizer_required
def announcement_delete(announcement_id):
    announcement = _managed_announcement(announcement_id)
    delete_announcement(current_user, announcement)
    flash("Announcement deleted.", "success")
    return redirect(url_for("organizer.announcements"))


@organizer.get("/schedule", endpoint="schedule")
@organizer_required
def schedule_list():
    items = ScheduleItem.query.filter_by(event_id=current_user.event_id).order_by(
        ScheduleItem.starts_at.asc()
    ).all()
    return render_template(
        "organizer/schedule/list.html",
        **_dashboard_context(),
        items=items,
        event_timezone=current_user.event.timezone,
        to_event_timezone=to_event_timezone,
    )


@organizer.route(
    "/schedule/new", methods=["GET", "POST"], endpoint="schedule_create"
)
@organizer_required
def schedule_create():
    form = ScheduleItemForm()
    if form.validate_on_submit():
        try:
            item = create_schedule_item(current_user, current_user.event, form.data)
        except CommunicationValidationError as error:
            _communication_form_errors(form, error)
        else:
            flash("Schedule item created successfully.", "success")
            return redirect(url_for("organizer.schedule"))
    return render_template(
        "organizer/schedule/form.html",
        **_dashboard_context(),
        form=form,
        heading="Create schedule item",
    )


@organizer.route(
    "/schedule/<item_id>/edit",
    methods=["GET", "POST"],
    endpoint="schedule_edit",
)
@organizer_required
def schedule_edit(item_id):
    item = _managed_schedule_item(item_id)
    form = ScheduleItemForm(
        data={
            "title": item.title,
            "description": item.description or "",
            "location": item.location or "",
            "starts_at": to_event_timezone(
                item.starts_at, current_user.event.timezone
            ).strftime("%Y-%m-%dT%H:%M"),
            "ends_at": to_event_timezone(
                item.ends_at, current_user.event.timezone
            ).strftime("%Y-%m-%dT%H:%M"),
            "status": item.status,
        }
    )
    if form.validate_on_submit():
        try:
            update_schedule_item(current_user, item, form.data)
        except CommunicationValidationError as error:
            _communication_form_errors(form, error)
        else:
            flash("Schedule item updated successfully.", "success")
            return redirect(url_for("organizer.schedule"))
    return render_template(
        "organizer/schedule/form.html",
        **_dashboard_context(),
        form=form,
        heading="Edit schedule item",
        item=item,
    )


@organizer.post("/schedule/<item_id>/delete", endpoint="schedule_delete")
@organizer_required
def schedule_delete(item_id):
    item = _managed_schedule_item(item_id)
    delete_schedule_item(current_user, item)
    flash("Schedule item deleted.", "success")
    return redirect(url_for("organizer.schedule"))


def _managed_events():
    return Event.query.filter(
        (Event.owner_user_id == current_user.id)
        | (Event.id == current_user.event_id)
    ).order_by(Event.created_at.desc())


def _managed_event(event_id):
    return _managed_events().filter(Event.id == event_id).first_or_404()


@organizer.get("/events", endpoint="events")
@organizer_required
def event_list():
    return render_template(
        "organizer/events/list.html",
        **_dashboard_context(),
        events=_managed_events().all(),
    )


@organizer.route("/events/new", methods=["GET", "POST"], endpoint="event_create")
@organizer_required
def event_create():
    form = EventForm()
    if form.validate_on_submit():
        try:
            values = validate_event_data(form.data)
        except EventValidationError as error:
            for field, message in error.errors.items():
                getattr(form, field).errors.append(message)
        else:
            event = Event(**values, slug=unique_slug(values["name"]), owner=current_user)
            db.session.add(event)
            db.session.flush()
            if current_user.event_id is None:
                current_user.event_id = event.id
            audit_event(current_user, event, "event.created")
            db.session.commit()
            flash("Event created successfully.", "success")
            return redirect(url_for("organizer.event_detail", event_id=event.id))
    return render_template(
        "organizer/events/form.html",
        **_dashboard_context(),
        form=form,
        heading="Create event",
    )


@organizer.route("/events/<event_id>", methods=["GET"], endpoint="event_detail")
@organizer_required
def event_detail(event_id):
    event = _managed_event(event_id)
    return render_template(
        "organizer/events/detail.html",
        **_dashboard_context(event),
    )


@organizer.route("/events/<event_id>/edit", methods=["GET", "POST"], endpoint="event_edit")
@organizer_required
def event_edit(event_id):
    event = _managed_event(event_id)
    form = EventForm(data=event_form_data(event))
    if form.validate_on_submit():
        try:
            values = validate_event_data(form.data)
        except EventValidationError as error:
            for field, message in error.errors.items():
                getattr(form, field).errors.append(message)
        else:
            before = {
                "name": event.name,
                "status": event.status,
                "timezone": event.timezone,
                "capacity": event.capacity,
                "team_size_min": event.team_size_min,
                "team_size_max": event.team_size_max,
            }
            for key, value in values.items():
                setattr(event, key, value)
            event.slug = unique_slug(event.name, event.id)
            audit_event(current_user, event, "event.updated", before)
            db.session.commit()
            flash("Event updated successfully.", "success")
            return redirect(url_for("organizer.event_detail", event_id=event.id))
    return render_template(
        "organizer/events/form.html",
        **_dashboard_context(event),
        form=form,
        heading="Edit event",
    )


def _managed_participant(participant_id):
    return Participant.query.filter_by(
        id=participant_id, event_id=current_user.event_id
    ).first_or_404()


@organizer.get("/participants", endpoint="participants")
@organizer_required
def participant_list():
    query = Participant.query.filter_by(event_id=current_user.event_id)
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    if search:
        normalized = normalize_email(search)
        query = query.filter(
            db.or_(
                Participant.full_name.ilike(f"%{search}%"),
                Participant.email_normalized.ilike(f"%{normalized}%"),
                Participant.participant_code.ilike(f"%{search}%"),
            )
        )
    if status:
        query = query.filter_by(registration_status=status)
    return render_template(
        "organizer/participants/list.html",
        **_dashboard_context(),
        participants=query.order_by(Participant.created_at.desc()).all(),
        search=search,
        status=status,
    )


@organizer.get("/participants/<participant_id>", endpoint="participant_detail")
@organizer_required
def participant_detail(participant_id):
    participant = _managed_participant(participant_id)
    return render_template(
        "organizer/participants/detail.html",
        **_dashboard_context(),
        participant=participant,
    )


@organizer.route(
    "/participants/new", methods=["GET", "POST"], endpoint="participant_create"
)
@organizer_required
def participant_create():
    form = ParticipantForm()
    if form.validate_on_submit():
        try:
            participant = create_participant(current_user.event, form.data, current_user)
            db.session.commit()
        except (ParticipantValidationError, ParticipantRegistrationError) as error:
            if isinstance(error, ParticipantValidationError):
                for field, message in error.errors.items():
                    if hasattr(form, field):
                        getattr(form, field).errors.append(message)
            else:
                form.email.errors.append(str(error))
        else:
            flash("Participant created successfully.", "success")
            return redirect(
                url_for("organizer.participant_detail", participant_id=participant.id)
            )
    return render_template(
        "organizer/participants/form.html",
        **_dashboard_context(),
        form=form,
        heading="Create participant",
    )


@organizer.route(
    "/participants/<participant_id>/edit",
    methods=["GET", "POST"],
    endpoint="participant_edit",
)
@organizer_required
def participant_edit(participant_id):
    participant = _managed_participant(participant_id)
    form = ParticipantForm(
        data={
            "full_name": participant.full_name,
            "email": participant.email_normalized,
            "phone": participant.phone or "",
            "institution": participant.institution or "",
            "registration_status": participant.registration_status,
        }
    )
    if form.validate_on_submit():
        try:
            update_participant(current_user, participant, form.data)
        except (ParticipantValidationError, ParticipantRegistrationError) as error:
            if isinstance(error, ParticipantValidationError):
                for field, message in error.errors.items():
                    if hasattr(form, field):
                        getattr(form, field).errors.append(message)
            else:
                form.email.errors.append(str(error))
        else:
            flash("Participant updated successfully.", "success")
            return redirect(
                url_for("organizer.participant_detail", participant_id=participant.id)
            )
    return render_template(
        "organizer/participants/form.html",
        **_dashboard_context(),
        form=form,
        heading="Edit participant",
        participant=participant,
    )


def _managed_team(team_id):
    return Team.query.filter_by(
        id=team_id, event_id=current_user.event_id
    ).first_or_404()


def _team_form_errors(form, error):
    if isinstance(error, TeamValidationError):
        for field, message in error.errors.items():
            if hasattr(form, field):
                getattr(form, field).errors.append(message)


@organizer.get("/teams", endpoint="teams")
@organizer_required
def team_list():
    teams = Team.query.filter_by(event_id=current_user.event_id).order_by(
        Team.created_at.desc()
    ).all()
    return render_template(
        "organizer/teams/list.html",
        **_dashboard_context(),
        teams=teams,
    )


@organizer.get("/teams/<team_id>", endpoint="team_detail")
@organizer_required
def team_detail(team_id):
    team = _managed_team(team_id)
    members = TeamMember.query.filter_by(team_id=team.id).order_by(
        TeamMember.joined_at.asc()
    ).all()
    return render_template(
        "organizer/teams/detail.html",
        **_dashboard_context(),
        team=team,
        members=members,
        participant_form=MembershipForm(),
        transfer_form=TransferForm(),
    )


@organizer.route("/teams/new", methods=["GET", "POST"], endpoint="team_create")
@organizer_required
def team_create():
    form = TeamForm()
    if form.validate_on_submit():
        try:
            team = create_team(current_user, current_user.event, form.data)
        except TeamValidationError as error:
            _team_form_errors(form, error)
        else:
            flash("Team created successfully.", "success")
            return redirect(url_for("organizer.team_detail", team_id=team.id))
    return render_template(
        "organizer/teams/form.html",
        **_dashboard_context(),
        form=form,
        heading="Create team",
    )


@organizer.route("/teams/<team_id>/edit", methods=["GET", "POST"], endpoint="team_edit")
@organizer_required
def team_edit(team_id):
    team = _managed_team(team_id)
    form = TeamForm(
        data={
            "name": team.name,
            "problem_statement": team.problem_statement or "",
            "status": team.status,
        }
    )
    if form.validate_on_submit():
        try:
            update_team(current_user, team, form.data)
        except TeamValidationError as error:
            _team_form_errors(form, error)
        else:
            flash("Team updated successfully.", "success")
            return redirect(url_for("organizer.team_detail", team_id=team.id))
    return render_template(
        "organizer/teams/form.html",
        **_dashboard_context(),
        form=form,
        heading="Edit team",
        team=team,
    )


@organizer.post("/teams/<team_id>/members/add", endpoint="team_member_add")
@organizer_required
def team_member_add(team_id):
    team = _managed_team(team_id)
    form = MembershipForm()
    if form.validate_on_submit():
        try:
            add_member(current_user, team, form.participant_id.data, form.member_role.data)
        except MembershipError as error:
            flash(str(error), "danger")
        else:
            flash("Participant added to team.", "success")
    else:
        flash("Provide a valid participant ID.", "danger")
    return redirect(url_for("organizer.team_detail", team_id=team.id))


@organizer.post(
    "/teams/<team_id>/members/<participant_id>/remove",
    endpoint="team_member_remove",
)
@organizer_required
def team_member_remove(team_id, participant_id):
    team = _managed_team(team_id)
    form = MembershipForm()
    if not form.validate_on_submit():
        abort(400)
    try:
        remove_member(current_user, team, participant_id)
    except MembershipError as error:
        flash(str(error), "danger")
    else:
        flash("Participant removed from team.", "success")
    return redirect(url_for("organizer.team_detail", team_id=team.id))


@organizer.post("/teams/<team_id>/members/<participant_id>/transfer", endpoint="team_member_transfer")
@organizer_required
def team_member_transfer(team_id, participant_id):
    source = _managed_team(team_id)
    form = TransferForm()
    if not form.validate_on_submit():
        abort(400)
    target = _managed_team(form.team_id.data)
    try:
        transfer_member(
            current_user,
            source,
            target,
            participant_id,
            form.member_role.data,
        )
    except MembershipError as error:
        flash(str(error), "danger")
    else:
        flash("Participant transferred successfully.", "success")
    return redirect(url_for("organizer.team_detail", team_id=source.id))


@participant.get("/announcements", endpoint="announcements")
@participant_required
def participant_announcements():
    announcements = Announcement.query.filter_by(
        event_id=current_user.event_id, status="published"
    ).order_by(Announcement.published_at.desc(), Announcement.created_at.desc()).all()
    return render_template(
        "participants/announcements.html",
        **_dashboard_context(),
        announcements=announcements,
    )


@participant.get("/schedule", endpoint="schedule")
@participant_required
def participant_schedule():
    items = ScheduleItem.query.filter_by(
        event_id=current_user.event_id, status="published"
    ).order_by(ScheduleItem.starts_at.asc()).all()
    return render_template(
        "participants/schedule.html",
        **_dashboard_context(),
        items=items,
        event_timezone=current_user.event.timezone,
        to_event_timezone=to_event_timezone,
    )


def _participant_team():
    profile = Participant.query.filter_by(
        user_id=current_user.id, event_id=current_user.event_id
    ).first_or_404()
    membership = TeamMember.query.filter_by(
        participant_id=profile.id, left_at=None
    ).first()
    return membership.team if membership else None


@participant.route("/submission", methods=["GET", "POST"], endpoint="submission")
@participant_required
def participant_submission():
    team = _participant_team()
    if team is None:
        return render_template(
            "participants/submission.html",
            **_dashboard_context(),
            team=None,
            submission=None,
            form=None,
        )
    submission = team.submission
    form = SubmissionForm(
        data={
            "project_title": submission.project_title if submission else "",
            "description": submission.description if submission else "",
            "repository_url": submission.repository_url if submission else "",
            "demo_url": submission.demo_url if submission else "",
        }
    )
    if form.validate_on_submit():
        try:
            if submission:
                update_submission(current_user, submission, form.data)
            else:
                submission = create_submission(current_user, team, form.data)
        except SubmissionValidationError as error:
            _submission_form_errors(form, error)
        except (SubmissionAuthorizationError, SubmissionConflictError) as error:
            flash(str(error), "danger")
        else:
            flash("Submission saved successfully.", "success")
            return redirect(url_for("participant.submission"))
    return render_template(
        "participants/submission.html",
        **_dashboard_context(),
        team=team,
        submission=submission,
        form=form,
        event_timezone=current_user.event.timezone,
        to_event_timezone=to_event_timezone,
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


@participant.get("/profile", endpoint="profile")
@participant_required
def participant_profile():
    if current_user.participant is None:
        abort(404)
    profile = Participant.query.filter_by(
        id=current_user.participant.id, event_id=current_user.event_id
    ).first_or_404()
    return render_template(
        "participants/profile.html",
        **_dashboard_context(),
        participant=profile,
    )


@participant.get("/check-in-pass", endpoint="check_in_pass")
@participant_required
def participant_check_in_pass():
    if current_user.participant is None:
        abort(404)
    profile = Participant.query.filter_by(
        id=current_user.participant.id, event_id=current_user.event_id
    ).first_or_404()
    token = ensure_check_in_token(profile)
    return render_template(
        "participants/check_in_pass.html",
        **_dashboard_context(),
        participant=profile,
        token=token,
        qr_data_uri=qr_svg_data_uri(token),
    )


@participant.get("/attendance", endpoint="attendance")
@participant_required
def participant_attendance():
    if current_user.participant is None:
        abort(404)
    profile = Participant.query.filter_by(
        id=current_user.participant.id, event_id=current_user.event_id
    ).first_or_404()
    return render_template(
        "participants/attendance.html",
        **_dashboard_context(),
        participant=profile,
        attendance=profile.attendance,
    )


@participant.get("/team", endpoint="team")
@participant_required
def participant_team():
    if current_user.participant is None:
        abort(404)
    profile = Participant.query.filter_by(
        id=current_user.participant.id, event_id=current_user.event_id
    ).first_or_404()
    membership = TeamMember.query.filter_by(
        participant_id=profile.id, left_at=None
    ).first()
    return render_template(
        "participants/team.html",
        **_dashboard_context(),
        membership=membership,
        team=membership.team if membership else None,
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


@judge.get("/assignments", endpoint="assignments")
@judge_required
def judge_assignments():
    judge_profile = current_user.judge
    assignments = []
    if judge_profile:
        assignments = JudgeAssignment.query.filter_by(
            event_id=current_user.event_id, judge_id=judge_profile.id
        ).filter(JudgeAssignment.status != "revoked").order_by(
            JudgeAssignment.assigned_at.desc()
        ).all()
    return render_template(
        "judge/assignments.html",
        **_dashboard_context(),
        assignments=assignments,
    )


@judge.route(
    "/assignments/<submission_id>/evaluate",
    methods=["GET", "POST"],
    endpoint="evaluate",
)
@judge_required
def judge_evaluate(submission_id):
    judge_profile = current_user.judge
    if judge_profile is None:
        abort(403)
    if not Submission.query.filter_by(
        id=submission_id, event_id=current_user.event_id
    ).first():
        abort(404)
    assignment = JudgeAssignment.query.filter_by(
        event_id=current_user.event_id,
        judge_id=judge_profile.id,
        submission_id=submission_id,
    ).filter(JudgeAssignment.status != "revoked").first()
    if assignment is None:
        abort(403)
    submission = assignment.submission
    criteria = RubricCriterion.query.filter_by(
        event_id=current_user.event_id, is_active=True
    ).order_by(RubricCriterion.display_order.asc(), RubricCriterion.id.asc()).all()
    evaluation = Evaluation.query.filter_by(
        event_id=current_user.event_id,
        submission_id=submission_id,
        judge_id=judge_profile.id,
    ).first()
    form = EvaluationForm()
    if form.validate_on_submit():
        submit = form.submit_action.data == "submit"
        score_data = {
            criterion.id: request.form.get(criterion.id, "")
            for criterion in criteria
        }
        criterion_comments = {
            criterion.id: request.form.get(f"comment_{criterion.id}", "")
            for criterion in criteria
        }
        try:
            evaluation = save_evaluation(
                current_user,
                submission_id,
                score_data,
                form.comments.data,
                submit=submit,
                criterion_comments=criterion_comments,
            )
        except JudgingValidationError as error:
            for message in error.errors.values():
                form.form_errors.append(message)
        except JudgingError as error:
            flash(str(error), "danger")
        else:
            flash(
                "Evaluation submitted." if submit else "Evaluation draft saved.",
                "success",
            )
            return redirect(url_for("judge.evaluate", submission_id=submission_id))
    score_values = {
        score.criterion_id: score for score in evaluation.scores
    } if evaluation else {}
    return render_template(
        "judge/evaluate.html",
        **_dashboard_context(),
        assignment=assignment,
        submission=submission,
        criteria=criteria,
        evaluation=evaluation,
        score_values=score_values,
        form=form,
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
