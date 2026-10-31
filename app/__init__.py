import os

from flask import Flask, jsonify
from sqlalchemy import event

from config import Config
from app.cli import register_cli
from app.extensions import csrf, db, login_manager, migrate


def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or Config)

    os.makedirs(app.instance_path, exist_ok=True)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = Config.resolve_database_uri(
            app.instance_path
        )

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is not set")

    flask_env = os.environ.get("FLASK_ENV", "").strip().lower()
    if flask_env == "production":
        app.config["DEBUG"] = False

    from app import models as _models  # noqa: F401

    db.init_app(app)
    migrate.init_app(app, db, directory="migrations", render_as_batch=True)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to continue."
    login_manager.login_message_category = "info"
    csrf.init_app(app)
    register_cli(app)
    from app.auth import auth
    from app.routes import register_routes

    app.register_blueprint(auth)
    register_routes(app)

    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with app.app_context():
            event.listen(db.engine, "connect", _enable_sqlite_foreign_keys)
            db.engine.dispose()

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "hackos"}), 200

    return app
