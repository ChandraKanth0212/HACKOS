import os
from datetime import timedelta
from pathlib import Path


def _env_flag(name, default=False):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _debug_enabled():
    flask_env = os.environ.get("FLASK_ENV", "production").strip().lower()
    if flask_env == "production":
        return False
    if flask_env == "development":
        return _env_flag("FLASK_DEBUG", default=True)
    return _env_flag("FLASK_DEBUG", default=False)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DEBUG = _debug_enabled()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Kolkata")

    N8N_WEBHOOK_BASE_URL = os.environ.get("N8N_WEBHOOK_BASE_URL", "")
    N8N_WEBHOOK_SECRET = os.environ.get("N8N_WEBHOOK_SECRET", "")

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag("SESSION_COOKIE_SECURE", default=False)
    SESSION_REFRESH_EACH_REQUEST = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    @staticmethod
    def resolve_database_uri(instance_path):
        configured = os.environ.get("DATABASE_URL")
        if configured:
            if configured == "sqlite:///hackos.db":
                db_path = Path(instance_path) / "hackos.db"
                return "sqlite:///" + db_path.resolve().as_posix()
            return configured
        db_path = Path(instance_path) / "hackos.db"
        return "sqlite:///" + db_path.resolve().as_posix()


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret-key-not-for-production"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
