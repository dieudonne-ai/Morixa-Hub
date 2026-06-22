# ============================================================
# routes/auth.py
# ============================================================
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, datetime
from config import Config
from models import db, User

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

