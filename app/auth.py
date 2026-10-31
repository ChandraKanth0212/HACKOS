from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length

from app.extensions import db, login_manager
from app.models import User
from app.services.passwords import verify_password

auth = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Length(max=320)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class LogoutForm(FlaskForm):
    pass


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)


def _normalized_email(value):
    return value.strip().casefold()


def _safe_next_url(value):
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return None
    return value


def role_required(role):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


organizer_required = role_required("organizer")
participant_required = role_required("participant")
judge_required = role_required("judge")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = _normalized_email(form.email.data)
        candidates = User.query.filter(db.func.lower(User.email) == email).all()
        user = candidates[0] if len(candidates) == 1 else None
        if user is not None and user.is_active and verify_password(
            user.password_hash, form.password.data
        ):
            next_url = _safe_next_url(request.args.get("next"))
            login_user(user, fresh=True)
            destination = next_url or url_for(f"{user.role}.dashboard")
            return redirect(destination)
        flash("We could not sign you in with those details.", "danger")
    elif request.method == "POST":
        flash("Enter a valid email and password.", "danger")
    return render_template("auth/login.html", form=form)


@auth.post("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
