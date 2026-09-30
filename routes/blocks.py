from flask import Blueprint, jsonify, g
from models import db, Block, User
from utils.auth import require_auth
from sqlalchemy import or_, and_

blocks_bp = Blueprint("blocks", __name__, url_prefix="/api/blocks")


@blocks_bp.get("/<int:user_id>")
@require_auth
def block_status(user_id):
    is_blocked = Block.query.filter_by(blocker_id=g.user_id, blocked_id=user_id).first() is not None
    return jsonify({"is_blocked": is_blocked})


@blocks_bp.post("/<int:user_id>/toggle")
@require_auth
def toggle_block(user_id):
    if user_id == g.user_id:
        return jsonify({"error": "You cannot block yourself"}), 400

    User.query.get_or_404(user_id)

    existing = Block.query.filter_by(blocker_id=g.user_id, blocked_id=user_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"is_blocked": False})

    db.session.add(Block(blocker_id=g.user_id, blocked_id=user_id))
    db.session.commit()
    return jsonify({"is_blocked": True})


@blocks_bp.get("/")
@require_auth
def list_blocked():
    """Liste des utilisateurs que je bloque."""
    rows = Block.query.filter_by(blocker_id=g.user_id).all()
    users = [db.session.get(User, r.blocked_id) for r in rows]
    return jsonify([u.to_dict() for u in users if u])


def is_blocked_either_way(user_a, user_b):
    """True si l'un des deux a bloqué l'autre — utilisé par routes/messages.py."""
    return db.session.query(Block.id).filter(
        or_(
            and_(Block.blocker_id == user_a, Block.blocked_id == user_b),
            and_(Block.blocker_id == user_b, Block.blocked_id == user_a),
        )
    ).first() is not None
