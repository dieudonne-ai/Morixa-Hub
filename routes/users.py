from flask import Blueprint, request, jsonify
from models import db, User, PointsLog, Notification

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

@users_bp.get("/leaderboard")
def leaderboard():
    top = User.query.order_by(User.total_points.desc()).limit(20).all()
    return jsonify([u.to_dict() for u in top])

@users_bp.get("/<int:uid>")
def get_profile(uid):
    u = User.query.get_or_404(uid)
    return jsonify({
        **u.to_dict(),
        "bio": u.bio,
        "hospital": u.hospital,
        "created_at": u.created_at.isoformat(),
        "posts_count": len(u.posts),
    })

@users_bp.put("/<int:uid>")
def update_profile(uid):
    u = User.query.get_or_404(uid)
    d = request.get_json()
    u.bio       = d.get("bio", u.bio)
    u.specialty = d.get("specialty", u.specialty)
    u.hospital  = d.get("hospital", u.hospital)
    u.country   = d.get("country", u.country)
    db.session.commit()
    return jsonify(u.to_dict())

@users_bp.get("/<int:uid>/points")
def user_points(uid):
    logs = PointsLog.query.filter_by(user_id=uid)\
                          .order_by(PointsLog.created_at.desc()).limit(50).all()
    return jsonify([{
        "action": l.action, "points": l.points,
        "ref_type": l.ref_type, "created_at": l.created_at.isoformat(),
    } for l in logs])

@users_bp.get("/<int:uid>/notifications")
def get_notifications(uid):
    notifs = Notification.query.filter_by(user_id=uid)\
                               .order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify([{
        "id": n.id, "type": n.type, "message": n.message,
        "is_read": n.is_read, "ref_type": n.ref_type, "ref_id": n.ref_id,
        "created_at": n.created_at.isoformat(),
    } for n in notifs])

@users_bp.post("/notifications/<int:nid>/read")
def mark_notif_read(nid):
    n = Notification.query.get_or_404(nid)
    n.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"})

@users_bp.get("/search")
def search_users():
    """Recherche de médecins par nom, spécialité ou hôpital."""
    q        = request.args.get("q", "").strip()
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if not q:
        return jsonify({"users": [], "total": 0})

    results = User.query.filter(
        User.full_name.ilike(f"%{q}%") |
        User.specialty.ilike(f"%{q}%")  |
        User.hospital.ilike(f"%{q}%")   |
        User.country.ilike(f"%{q}%")
    ).order_by(
        User.total_points.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "users": [{
            **u.to_dict(),
            "posts_count": len(u.posts),
        } for u in results.items],
        "total": results.total,
        "pages": results.pages,
    })