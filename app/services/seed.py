import json
import os
import secrets
from datetime import timedelta

from app.extensions import db
from app.models import (
    Announcement,
    Attendance,
    AuditLog,
    AutomationOutbox,
    Event,
    Judge,
    Participant,
    RubricCriterion,
    ScheduleItem,
    Submission,
    Team,
    TeamMember,
    User,
)
from app.services.passwords import hash_password
from app.services.time import utc_now

SEED_EVENT_SLUG = "hackos-demo-2026"
SEED_EVENT_NAME = "HACKOS Sample Event"

TEAM_SPECS = (
    ("TEAM-01", "Atlas", 3, True),
    ("TEAM-02", "Beacon", 4, True),
    ("TEAM-03", "Cobalt", 4, True),
    ("TEAM-04", "Drift", 5, True),
    ("TEAM-05", "Ember", 3, False),
    ("TEAM-06", "Flux", 5, False),
)

FIRST_NAMES = (
    "Asha",
    "Dev",
    "Isha",
    "Kabir",
    "Leela",
    "Mira",
    "Neel",
    "Omar",
    "Priya",
    "Ravi",
    "Sana",
    "Tara",
    "Uma",
    "Vikram",
    "Zara",
    "Arjun",
    "Bina",
    "Chet",
    "Diya",
    "Eshan",
    "Farah",
    "Gita",
    "Hari",
    "Inaya",
)


def _settings_json():
    return json.dumps(
        {
            "is_synthetic_sample": True,
            "late_submission_policy": "accept_and_flag",
            "scoring": {
                "method": "weighted_criterion_sum_then_average_submitted_judges",
                "missing_scores": "do_not_treat_as_zero",
            },
        }
    )


def _get_or_create(model, defaults=None, **filters):
    instance = model.query.filter_by(**filters).first()
    if instance is not None:
        return instance, False
    params = dict(filters)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    db.session.add(instance)
    db.session.flush()
    return instance, True


def seed_database():
    password = os.environ.get("HACKOS_SEED_PASSWORD")
    if not password:
        raise RuntimeError("HACKOS_SEED_PASSWORD is not set")

    password_hash = hash_password(password)
    now = utc_now()

    event, _ = _get_or_create(
        Event,
        slug=SEED_EVENT_SLUG,
        defaults={
            "name": SEED_EVENT_NAME,
            "timezone": "Asia/Kolkata",
            "starts_at": now,
            "ends_at": now + timedelta(hours=24),
            "submission_deadline": now + timedelta(hours=16),
            "team_size_min": 3,
            "team_size_max": 5,
            "settings_json": _settings_json(),
        },
    )

    organizer, _ = _get_or_create(
        User,
        event_id=event.id,
        email="organizer@hackos.example",
        defaults={
            "password_hash": password_hash,
            "role": "organizer",
            "is_active": True,
        },
    )

    judge_specs = (
        ("judge1@hackos.example", "Jordan Blake", "Web systems"),
        ("judge2@hackos.example", "Casey Ng", "Product design"),
        ("judge3@hackos.example", "Riley Shah", "Data and ops"),
    )
    judges = []
    for email, display_name, expertise in judge_specs:
        user, _ = _get_or_create(
            User,
            event_id=event.id,
            email=email,
            defaults={
                "password_hash": password_hash,
                "role": "judge",
                "is_active": True,
            },
        )
        judge, _ = _get_or_create(
            Judge,
            event_id=event.id,
            user_id=user.id,
            defaults={"display_name": display_name, "expertise": expertise},
        )
        judges.append(judge)

    name_index = 0
    created_participants = []
    teams = []
    for team_code, team_name, size, has_submission in TEAM_SPECS:
        team, _ = _get_or_create(
            Team,
            event_id=event.id,
            team_code=team_code,
            defaults={
                "name": team_name,
                "problem_statement": "HACKOS — a reliable operating system for hackathon delivery",
                "status": "active",
            },
        )
        teams.append((team, has_submission))
        for member_index in range(size):
            first_name = FIRST_NAMES[name_index % len(FIRST_NAMES)]
            name_index += 1
            full_name = f"{first_name} Sample"
            email = f"{team_code.lower()}-member{member_index + 1}@hackos.example"
            user, _ = _get_or_create(
                User,
                event_id=event.id,
                email=email,
                defaults={
                    "password_hash": password_hash,
                    "role": "participant",
                    "is_active": True,
                },
            )
            participant, _ = _get_or_create(
                Participant,
                event_id=event.id,
                email_normalized=email,
                defaults={
                    "user_id": user.id,
                    "participant_code": secrets.token_urlsafe(18),
                    "full_name": full_name,
                    "institution": "Synthetic Demo University",
                    "registration_status": "confirmed",
                },
            )
            if participant.user_id is None:
                participant.user_id = user.id
            created_participants.append(participant)
            existing_membership = TeamMember.query.filter_by(
                team_id=team.id, participant_id=participant.id, left_at=None
            ).first()
            if existing_membership is None:
                db.session.add(
                    TeamMember(
                        team_id=team.id,
                        participant_id=participant.id,
                        member_role="leader" if member_index == 0 else "member",
                        joined_at=now,
                    )
                )

    rubric_specs = (
        (1, "Impact", "Problem value and usefulness", 10, 0.30),
        (2, "Technical execution", "Implementation quality", 10, 0.30),
        (3, "Design and usability", "Clarity of the operator experience", 10, 0.20),
        (4, "Presentation", "Communication of the solution", 10, 0.20),
    )
    for order, name, description, max_score, weight in rubric_specs:
        _get_or_create(
            RubricCriterion,
            event_id=event.id,
            name=name,
            defaults={
                "description": description,
                "max_score": max_score,
                "weight": weight,
                "display_order": order,
                "is_active": True,
            },
        )

    for team, has_submission in teams:
        if not has_submission:
            continue
        leader = (
            TeamMember.query.filter_by(team_id=team.id, member_role="leader")
            .order_by(TeamMember.joined_at.asc())
            .first()
        )
        updated_by = leader.participant.user_id if leader else organizer.id
        _get_or_create(
            Submission,
            event_id=event.id,
            team_id=team.id,
            defaults={
                "project_title": f"{team.name} operations console",
                "description": (
                    "Synthetic sample project for the HACKOS demo. "
                    "Not a real hackathon submission."
                ),
                "repository_url": "https://github.com/example/hackos-sample",
                "demo_url": "https://example.com/hackos-sample",
                "status": "submitted",
                "submitted_at": now,
                "updated_by": updated_by,
            },
        )

    announcements = (
        (
            "Welcome to the sample event",
            "This is synthetic demo copy for HACKOS operations.",
            "published",
            now,
        ),
        (
            "Submission window reminder",
            "Teams should submit before the configured deadline.",
            "published",
            now,
        ),
        (
            "Internal staff note",
            "Draft announcement — not visible to participants.",
            "draft",
            None,
        ),
        (
            "Judging starts after freeze",
            "Assigned judges will receive their queues after submissions lock.",
            "published",
            now,
        ),
    )
    for title, body, status, published_at in announcements:
        _get_or_create(
            Announcement,
            event_id=event.id,
            title=title,
            defaults={
                "body": body,
                "status": status,
                "published_at": published_at,
                "created_by": organizer.id,
            },
        )

    schedule = (
        ("Opening briefing", now, now + timedelta(hours=1), "Hall A", "published"),
        ("Build sprint", now + timedelta(hours=1), now + timedelta(hours=12), "Labs", "published"),
        ("Mentor hours", now + timedelta(hours=6), now + timedelta(hours=8), "Mentor desk", "published"),
        ("Submission freeze", now + timedelta(hours=16), now + timedelta(hours=16, minutes=30), "Portal", "published"),
        ("Judging", now + timedelta(hours=17), now + timedelta(hours=20), "Judging rooms", "published"),
        ("Draft social", now + timedelta(hours=21), now + timedelta(hours=22), "TBD", "draft"),
    )
    for title, starts_at, ends_at, location, status in schedule:
        _get_or_create(
            ScheduleItem,
            event_id=event.id,
            title=title,
            defaults={
                "description": "Synthetic sample schedule item.",
                "starts_at": starts_at,
                "ends_at": ends_at,
                "location": location,
                "status": status,
                "created_by": organizer.id,
            },
        )

    if created_participants:
        sample = created_participants[0]
        existing = Attendance.query.filter_by(
            event_id=event.id, participant_id=sample.id
        ).first()
        if existing is None:
            db.session.add(
                Attendance(
                    event_id=event.id,
                    participant_id=sample.id,
                    checked_in_at=now,
                    checked_in_by=organizer.id,
                    operation_id="seed-checkin-1",
                    source="manual",
                )
            )

    _get_or_create(
        AuditLog,
        event_id=event.id,
        action="event.seeded",
        entity_type="event",
        entity_id=event.id,
        defaults={
            "actor_user_id": organizer.id,
            "before_json": None,
            "after_json": json.dumps({"is_synthetic_sample": True}),
        },
    )
    _get_or_create(
        AutomationOutbox,
        event_id=event.id,
        event_type="registration.created",
        defaults={
            "payload_json": json.dumps(
                {
                    "event_slug": event.slug,
                    "notice": "synthetic-sample",
                }
            ),
            "status": "pending",
            "attempt_count": 0,
        },
    )

    db.session.commit()
    return {
        "event_id": event.id,
        "users": User.query.filter_by(event_id=event.id).count(),
        "participants": Participant.query.filter_by(event_id=event.id).count(),
        "teams": Team.query.filter_by(event_id=event.id).count(),
        "submissions": Submission.query.filter_by(event_id=event.id).count(),
        "judges": Judge.query.filter_by(event_id=event.id).count(),
    }
