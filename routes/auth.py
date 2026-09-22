from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, PasswordReset
from services.email import send_password_reset_email, send_welcome_email
from utils.security import rate_limit, is_valid_email, password_errors, clean_str
from datetime import datetime, timedelta
import jwt
import secrets
import os

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
@rate_limit(max_calls=5, window_seconds=300, key_prefix="register")
def register():
    d     = request.get_json(silent=True) or {}
    email = clean_str(d.get("email"), 150).lower()

    if not is_valid_email(email):
        return jsonify({"error": "Invalid email address"}), 400

    errors = password_errors(d.get("password", ""))
    if errors:
        return jsonify({"error": "Password must contain: " + ", ".join(errors)}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already used"}), 409

    u = User(
        full_name     = clean_str(d.get("full_name"), 100),
        email         = email,
        password_hash = generate_password_hash(d["password"]),
        specialty     = clean_str(d.get("specialty"), 100),
        hospital      = clean_str(d.get("hospital"), 150),
        country       = clean_str(d.get("country"), 80),
    )
    db.session.add(u)
    db.session.commit()

    send_welcome_email(u.email, u.full_name)
    return jsonify({"message": "Account created", "user": u.to_dict()}), 201


@auth_bp.post("/login")
@rate_limit(max_calls=10, window_seconds=300, key_prefix="login")
def login():
    d     = request.get_json(silent=True) or {}
    email = clean_str(d.get("email"), 150).lower()

    u = User.query.filter_by(email=email).first()
    if not u or not check_password_hash(u.password_hash, d.get("password", "")):
        return jsonify({"error": "Invalid credentials"}), 401

    from config import Config
    token = jwt.encode(
        {"user_id": u.id,
         "exp": datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRES_HOURS)},
        Config.JWT_SECRET, algorithm="HS256"
    )
    return jsonify({"token": token, "user": u.to_dict()})


@auth_bp.post("/forgot-password")
@rate_limit(max_calls=5, window_seconds=600, key_prefix="forgot")
def forgot_password():
    email = clean_str(request.get_json(silent=True, {}).get("email"), 150).lower()
    generic = jsonify({"message": "If an account exists with this email, a reset link has been sent."})

    user = User.query.filter_by(email=email).first()
    if not user:
        return generic

    PasswordReset.query.filter_by(user_id=user.id, used=False).delete()
    token = secrets.token_urlsafe(32)
    db.session.add(PasswordReset(
        user_id=user.id, token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1),
    ))
    db.session.commit()

    frontend_url = os.environ.get("FRONTEND_URL", "https://morixa-hub-api.onrender.com")
    send_password_reset_email(user.email, user.full_name,
                              f"{frontend_url}/reset-password.html?token={token}")
    return generic


@auth_bp.post("/reset-password")
@rate_limit(max_calls=5, window_seconds=600, key_prefix="reset")
def reset_password():
    d        = request.get_json(silent=True) or {}
    token    = d.get("token", "")
    password = d.get("password", "")

    errors = password_errors(password)
    if errors:
        return jsonify({"error": "Password must contain: " + ", ".join(errors)}), 400

    reset = PasswordReset.query.filter_by(token=token, used=False).first()
    if not reset or reset.expires_at < datetime.utcnow():
        return jsonify({"error": "This reset link is invalid or has expired."}), 400

    user = db.session.get(User, reset.user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    user.password_hash = generate_password_hash(password)
    reset.used = True
    db.session.commit()
    return jsonify({"message": "Password updated successfully. You can now sign in."})