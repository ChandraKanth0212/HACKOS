import re
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.models import AuditLog, Event, Participant, Team, TeamMember, User
from app.services.passwords import hash_password
from app.services.teams import (
    MembershipError,
    add_member,
    create_team,
    remove_member,
    transfer_member,
)


def _token(response):
    match = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


@pytest.fixture
def team_fixture(app):
    with app.app_context():
        event = Event(
            name="Team Event",
            slug="team-event",
            timezone="UTC",
            status="active",
            team_size_min=2,
            team_size_max=3,
        )
        other_event = Event(
            name="Other Team Event",
            slug="other-team-event",
            timezone="UTC",
            status="active",
            team_size_min=1,
            team_size_max=3,
        )
        db.session.add_all([event, other_event])
        db.session.flush()
        organizer = User(
            event_id=event.id,
            email="team-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        participant_user = User(
            event_id=event.id,
            email="team-participant@test.example",
            password_hash=hash_password("password"),
            role="participant",
        )
        judge = User(
            event_id=event.id,
            email="team-judge@test.example",
            password_hash=hash_password("password"),
            role="judge",
        )
        other_organizer = User(
            event_id=other_event.id,
            email="other-team-organizer@test.example",
            password_hash=hash_password("password"),
            role="organizer",
        )
        db.session.add_all([organizer, participant_user, judge, other_organizer])
        db.session.flush()
        participants = []
        for index in range(5):
            participant = Participant(
                event_id=event.id,
                participant_code=f"TEAM-CODE-{index}",
                full_name=f"Team Participant {index}",
                email_normalized=f"team-participant-{index}@test.example",
                registration_status="confirmed",
            )
            db.session.add(participant)
            participants.append(participant)
        db.session.flush()
        participants[0].user_id = participant_user.id
        db.session.commit()
        return {
            "event": event.id,
            "other_event": other_event.id,
            "organizer": organizer.email,
            "participant": participant_user.email,
            "judge": judge.email,
            "other_organizer": other_organizer.email,
            "participants": [participant.id for participant in participants],
        }


def _login(client, email):
    page = client.get("/login")
    response = client.post(
        "/login",
        data={"email": email, "password": "password", "csrf_token": _token(page)},
    )
    assert response.status_code == 302


def test_team_creation_edit_and_unique_codes(app, team_fixture):
    with app.app_context():
        event = db.session.get(Event, team_fixture["event"])
        organizer = User.query.filter_by(email=team_fixture["organizer"]).one()
        first = create_team(organizer, event, {"name": "Alpha", "status": "active"})
        second = create_team(organizer, event, {"name": "Beta", "status": "active"})
        assert first.team_code != second.team_code
        first.name = "Alpha Updated"
        db.session.commit()
        assert AuditLog.query.filter_by(
            action="team.created", entity_type="team"
        ).count() == 2


def test_add_remove_preserves_membership_history_and_audit(app, team_fixture):
    with app.app_context():
        event = db.session.get(Event, team_fixture["event"])
        organizer = User.query.filter_by(email=team_fixture["organizer"]).one()
        team = create_team(organizer, event, {"name": "History Team"})
        first = add_member(organizer, team, team_fixture["participants"][0], "leader")
        second = add_member(organizer, team, team_fixture["participants"][1], "member")
        third = add_member(organizer, team, team_fixture["participants"][2], "member")
        removed = remove_member(
            organizer, team, team_fixture["participants"][2]
        )
        db.session.expire_all()
        assert removed.left_at is not None
        assert TeamMember.query.filter_by(
            team_id=team.id, participant_id=team_fixture["participants"][2]
        ).count() == 1
        assert AuditLog.query.filter_by(action="team.member_added").count() == 3
        assert AuditLog.query.filter_by(action="team.member_removed").count() == 1


def test_minimum_and_maximum_team_sizes_are_enforced(app, team_fixture):
    with app.app_context():
        event = db.session.get(Event, team_fixture["event"])
        organizer = User.query.filter_by(email=team_fixture["organizer"]).one()
        team = create_team(organizer, event, {"name": "Bounded Team"})
        add_member(organizer, team, team_fixture["participants"][0])
        with pytest.raises(MembershipError, match="below its minimum"):
            remove_member(organizer, team, team_fixture["participants"][0])
        add_member(organizer, team, team_fixture["participants"][1])
        add_member(organizer, team, team_fixture["participants"][2])
        with pytest.raises(MembershipError, match="maximum size"):
            add_member(organizer, team, team_fixture["participants"][3])


def test_transfer_closes_old_membership_and_creates_new_one(app, team_fixture):
    with app.app_context():
        event = db.session.get(Event, team_fixture["event"])
        organizer = User.query.filter_by(email=team_fixture["organizer"]).one()
        source = create_team(organizer, event, {"name": "Source"})
        target = create_team(organizer, event, {"name": "Target"})
        add_member(organizer, source, team_fixture["participants"][0])
        add_member(organizer, source, team_fixture["participants"][1])
        add_member(organizer, source, team_fixture["participants"][2])
        new_membership = transfer_member(
            organizer, source, target, team_fixture["participants"][0]
        )
        db.session.expire_all()
        history = TeamMember.query.filter_by(
            participant_id=team_fixture["participants"][0]
        ).order_by(TeamMember.joined_at.asc()).all()
        assert len(history) == 2
        assert history[0].left_at is not None
        assert new_membership.team_id == target.id
        assert AuditLog.query.filter_by(
            action="team.member_transferred"
        ).count() == 1


def test_cross_event_and_duplicate_active_membership_rejected(app, team_fixture):
    with app.app_context():
        event = db.session.get(Event, team_fixture["event"])
        other_event = db.session.get(Event, team_fixture["other_event"])
        organizer = User.query.filter_by(email=team_fixture["organizer"]).one()
        first = create_team(organizer, event, {"name": "First"})
        second = create_team(organizer, event, {"name": "Second"})
        other = Team(
            event_id=other_event.id,
            team_code="OTHER-TEAM",
            name="Other",
            status="active",
        )
        db.session.add(other)
        db.session.commit()
        add_member(organizer, first, team_fixture["participants"][0])
        with pytest.raises(MembershipError, match="already has"):
            add_member(organizer, second, team_fixture["participants"][0])
        with pytest.raises(MembershipError, match="does not belong"):
            add_member(organizer, other, team_fixture["participants"][1])


def test_team_routes_rbac_csrf_and_event_isolation(client, app, team_fixture):
    assert client.get("/organizer/teams").status_code == 302
    _login(client, team_fixture["organizer"])
    assert client.get("/organizer/teams").status_code == 200
    response = client.post(
        "/organizer/teams/new",
        data={"name": "Route Team", "status": "active"},
    )
    assert response.status_code == 400
    response = client.post(
        "/organizer/teams/new",
        data={
            "csrf_token": _token(client.get("/organizer/teams/new")),
            "name": "Route Team",
            "status": "active",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        team = Team.query.filter_by(name="Route Team").one()
        team_id = team.id
    assert client.get(f"/organizer/teams/{team_id}").status_code == 200
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/organizer/dashboard"))},
    )
    _login(client, team_fixture["participant"])
    assert client.get("/organizer/teams").status_code == 403
    assert client.get("/participant/team").status_code == 200
    client.post(
        "/logout",
        data={"csrf_token": _token(client.get("/participant/dashboard"))},
    )
    _login(client, team_fixture["judge"])
    assert client.get("/organizer/teams").status_code == 403
