# ============================================================
# routes/auth.py
# ============================================================
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime
from config import Config
from models import db, User

import secrets
from datetime import datetime, timedelta
from models import PasswordReset
from services.email import send_password_reset_email
from werkzeug.security import generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email déjà utilisé"}), 409
    user = User(
        full_name=data["full_name"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
        specialty=data.get("specialty"),
        hospital=data.get("hospital"),
        country=data.get("country"),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Compte créé", "user": user.to_dict()}), 201


@auth_bp.post("/login")
def login():
    d = request.get_json()
    u = User.query.filter_by(email=d["email"]).first()
    if not u or not check_password_hash(u.password_hash, d["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode(
        {
            "user_id": u.id,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRES_HOURS)
        },
        Config.JWT_SECRET,
        algorithm="HS256"
    )
    return jsonify({"token": token, "user": u.to_dict()})


@auth_bp.post("/forgot-password")
def forgot_password():
    d     = request.get_json()
    email = d.get("email", "").strip().lower()

    user = User.query.filter_by(email=email).first()

    # Réponse identique que l'email existe ou non (sécurité — évite l'énumération)
    generic_response = jsonify({
        "message": "If an account exists with this email, a reset link has been sent."
    })

    if not user:
        return generic_response

    # Invalider les anciens tokens non utilisés
    PasswordReset.query.filter_by(user_id=user.id, used=False).delete()

    token = secrets.token_urlsafe(32)
    reset = PasswordReset(
        user_id    = user.id,
        token      = token,
        expires_at = datetime.utcnow() + timedelta(hours=1),
    )
    db.session.add(reset)
    db.session.commit()

    frontend_url = os.environ.get("FRONTEND_URL", "https://morixa-hub-api.onrender.com")
    reset_link   = f"{frontend_url}/reset-password.html?token={token}"

    send_password_reset_email(user.email, user.full_name, reset_link)

    return generic_response


@auth_bp.post("/reset-password")
def reset_password():
    d        = request.get_json()
    token    = d.get("token", "")
    password = d.get("password", "")

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

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