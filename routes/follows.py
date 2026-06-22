from flask import Blueprint, request, jsonify
from models import db, Follow, User, Notification

follows_bp = Blueprint("follows", __name__, url_prefix="/api/follows")


@follows_bp.get("/<int:user_id>")
def follow_status(user_id):
    """Renvoie le nombre d'abonnés/abonnements, et si le viewer suit déjà cette personne."""
    viewer_id = request.args.get("viewer_id", type=int)

    followers_count = Follow.query.filter_by(following_id=user_id).count()
    following_count = Follow.query.filter_by(follower_id=user_id).count()

    is_following = False
    if viewer_id:
        is_following = Follow.query.filter_by(
            follower_id=viewer_id, following_id=user_id
        ).first() is not None

    return jsonify({
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following": is_following,
    })


@follows_bp.post("/<int:user_id>/toggle")
def toggle_follow(user_id):
    """Premier clic = suivre, second clic = se désabonner. Impossible de se suivre soi-même."""
    d = request.get_json()
    follower_id = d.get("follower_id")

    if not follower_id or follower_id == user_id:
        return jsonify({"error": "You cannot follow yourself"}), 400

    User.query.get_or_404(user_id)

    existing = Follow.query.filter_by(follower_id=follower_id, following_id=user_id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({
            "is_following": False,
            "followers_count": Follow.query.filter_by(following_id=user_id).count(),
        })

    db.session.add(Follow(follower_id=follower_id, following_id=user_id))

    follower = db.session.get(User, follower_id)
    db.session.add(Notification(
        user_id=user_id,
        type="follow",
        message=f"<strong>Dr. {follower.full_name}</strong> started following you." if follower else "You have a new follower.",
    ))
    db.session.commit()

    return jsonify({
        "is_following": True,
        "followers_count": Follow.query.filter_by(following_id=user_id).count(),
    })


@follows_bp.get("/<int:user_id>/followers")
def list_followers(user_id):
    rows  = Follow.query.filter_by(following_id=user_id).all()
    users = [db.session.get(User, r.follower_id) for r in rows]
    return jsonify([u.to_dict() for u in users if u])


@follows_bp.get("/<int:user_id>/following")
def list_following(user_id):
    rows  = Follow.query.filter_by(follower_id=user_id).all()
    users = [db.session.get(User, r.following_id) for r in rows]
    return jsonify([u.to_dict() for u in users if u])
