import pytest
from flask_migrate import upgrade

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "hackos.db"

    class IsolatedTestingConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + db_path.resolve().as_posix()

    application = create_app(IsolatedTestingConfig)
    with application.app_context():
        upgrade()
        yield application
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()
