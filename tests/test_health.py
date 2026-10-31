def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.is_json

    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "hackos"


def test_render_postgres_url_is_normalized():
    from config import _normalize_database_url

    assert (
        _normalize_database_url("postgres://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert (
        _normalize_database_url("postgresql://user:pass@host/db")
        == "postgresql+psycopg://user:pass@host/db"
    )
    assert _normalize_database_url("sqlite:///hackos.db") == "sqlite:///hackos.db"


def test_create_app_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")

    from config import Config
    from app import create_app

    class IncompleteConfig(Config):
        SECRET_KEY = None
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        DEBUG = False

    try:
        create_app(IncompleteConfig)
        assert False, "expected RuntimeError when SECRET_KEY is missing"
    except RuntimeError as exc:
        assert "SECRET_KEY" in str(exc)
