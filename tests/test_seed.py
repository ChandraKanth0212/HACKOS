from flask_migrate import upgrade

from app.extensions import db
from app.models import Event, Participant, Team, TeamMember, User
from app.services.passwords import verify_password
from app.services.seed import SEED_EVENT_SLUG, seed_database


def test_seed_creates_labelled_synthetic_records(app, monkeypatch):
    monkeypatch.setenv("HACKOS_SEED_PASSWORD", "local-only-seed-password")
    summary = seed_database()

    event = Event.query.filter_by(slug=SEED_EVENT_SLUG).one()
    assert "Sample" in event.name
    assert event.timezone == "Asia/Kolkata"
    assert event.team_size_min == 3
    assert event.team_size_max == 5
    assert "is_synthetic_sample" in (event.settings_json or "")

    assert summary["users"] >= 1 + 3 + 18
    assert User.query.filter_by(event_id=event.id, role="organizer").count() == 1
    assert User.query.filter_by(event_id=event.id, role="judge").count() == 3
    assert Team.query.filter_by(event_id=event.id).count() == 6
    assert 18 <= Participant.query.filter_by(event_id=event.id).count() <= 30
    assert summary["submissions"] == 4
    assert summary["judges"] == 3

    for team in Team.query.filter_by(event_id=event.id):
        active = TeamMember.query.filter_by(team_id=team.id, left_at=None).count()
        assert 3 <= active <= 5


def test_seed_is_idempotent(app, monkeypatch):
    monkeypatch.setenv("HACKOS_SEED_PASSWORD", "local-only-seed-password")
    first = seed_database()
    second = seed_database()
    assert first == second
    assert Event.query.filter_by(slug=SEED_EVENT_SLUG).count() == 1
    assert User.query.filter_by(email="organizer@hackos.example").count() == 1


def test_seed_passwords_are_hashed(app, monkeypatch):
    password = "local-only-seed-password"
    monkeypatch.setenv("HACKOS_SEED_PASSWORD", password)
    seed_database()
    user = User.query.filter_by(email="organizer@hackos.example").one()
    assert user.password_hash
    assert password not in user.password_hash
    assert not user.password_hash.startswith(password)
    assert verify_password(user.password_hash, password)


def test_seed_requires_password_env(app, monkeypatch):
    monkeypatch.delenv("HACKOS_SEED_PASSWORD", raising=False)
    try:
        seed_database()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "HACKOS_SEED_PASSWORD" in str(exc)


def test_upgrade_creates_fresh_database(tmp_path, monkeypatch):
    from app import create_app
    from config import TestingConfig

    db_path = tmp_path / "fresh.db"

    class FreshConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path.resolve().as_posix()

    application = create_app(FreshConfig)
    with application.app_context():
        upgrade()
        assert db_path.exists()
        from sqlalchemy import inspect

        tables = set(inspect(db.engine).get_table_names())
        assert "events" in tables
        assert "automation_outbox" in tables
