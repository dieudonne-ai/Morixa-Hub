"""
routes/admin.py

Accès restreint aux utilisateurs dont l'email est dans ADMIN_EMAILS.

"""

from flask import Blueprint, request, jsonify, send_file, g
from models import db, User, VerificationRequest, Notification, Follow, Post
from datetime import datetime, timedelta
import os, functools, jwt

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# ── Middleware admin ──────────────────────────────────────────
def require_admin(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            from config import Config
            payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            user = db.session.get(User, payload["user_id"])
            if not user or user.email not in Config.ADMIN_EMAILS:
                return jsonify({"error": "Admin access required"}), 403
            g.admin = user
        except Exception:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Stats générales ───────────────────────────────────────────
@admin_bp.get("/stats")
@require_admin
def stats():
    from models import Post, Repository, Message
    return jsonify({
        "users":              User.query.count(),
        "verified":           User.query.filter_by(verif_level="verified").count(),
        "pending_verif":      VerificationRequest.query.filter_by(status="pending").count(),
        "posts":              Post.query.count(),
        "repos":              Repository.query.count(),
        "messages":           Message.query.count(),
    })


# ── Liste des demandes de vérification ───────────────────────
@admin_bp.get("/verifications")
@require_admin
def list_verifications():
    status = request.args.get("status", "pending")
    reqs   = VerificationRequest.query.filter_by(status=status)\
                                      .order_by(VerificationRequest.created_at).all()
    result = []
    for r in reqs:
        user = db.session.get(User, r.user_id)
        result.append({
            "request_id":     r.id,
            "status":         r.status,
            "license_number": r.license_number,
            "country":        r.country,
            "notes":          r.notes,
            "reviewer_note":  r.reviewer_note,
            "created_at":     r.created_at.isoformat(),
            "reviewed_at":    r.reviewed_at.isoformat() if r.reviewed_at else None,
            "has_document":   bool(r.document_path and os.path.exists(r.document_path)),
            "user": user.to_dict() if user else {},
        })
    return jsonify(result)


# ── Voir le document justificatif ────────────────────────────
@admin_bp.get("/verifications/<int:request_id>/document")
@require_admin
def view_document(request_id):
    req = VerificationRequest.query.get_or_404(request_id)
    if not req.document_path or not os.path.exists(req.document_path):
        return jsonify({"error": "Document not found"}), 404
    return send_file(req.document_path, as_attachment=False)


# ── Approuver ou rejeter ──────────────────────────────────────
@admin_bp.post("/verifications/<int:request_id>/review")
@require_admin
def review_verification(request_id):
    d      = request.get_json()
    action = d.get("action")           # "approve" | "reject"
    note   = d.get("reviewer_note", "").strip()

    if action not in ("approve", "reject"):
        return jsonify({"error": "action must be 'approve' or 'reject'"}), 400

    req = VerificationRequest.query.get_or_404(request_id)
    if req.status != "pending":
        return jsonify({"error": "This request has already been reviewed"}), 400

    req.status        = "approved" if action == "approve" else "rejected"
    req.reviewer_note = note
    req.reviewed_at   = datetime.utcnow()

    user = db.session.get(User, req.user_id)
    if user:
        if action == "approve":
            user.verif_level    = "verified"
            user.license_number = req.license_number
            msg = (f"Your account has been <strong>verified</strong>. "
                   f"The Verified Physician badge is now active on your profile.")
        else:
            user.verif_level = "email" if user.email else "none"
            reason = f" Reason: {note}" if note else ""
            msg = (f"Your verification request was not approved.{reason} "
                   f"You may submit a new request with a clearer document.")

        db.session.add(Notification(user_id=user.id, type="points", message=msg))

    db.session.commit()
    return jsonify({
        "message":     f"Request {req.status}",
        "verif_level": user.verif_level if user else None,
    })


# ── Liste de tous les utilisateurs ───────────────────────────
@admin_bp.get("/users")
@require_admin
def list_users():
    page = request.args.get("page", 1, type=int)
    q    = request.args.get("q", "")
    query = User.query.order_by(User.created_at.desc())
    if q:
        query = query.filter(User.full_name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    p = query.paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        "users": [u.to_dict() for u in p.items],
        "total": p.total, "pages": p.pages,
    })


# ── Digest hebdomadaire ────────────────────────────────────────
# Déclenché par un cron externe gratuit (cron-job.org, GitHub Actions...)
# puisque Render free tier n'a pas de cron intégré. Protégé par un secret
# partagé (Config.DIGEST_SECRET) plutôt qu'un token admin, pour rester
# appelable depuis un service externe sans session utilisateur.
#
# Exemple d'appel hebdomadaire (cron-job.org, dimanche 8h UTC) :
#   POST https://morixa-hub-api.onrender.com/api/admin/digest/run?secret=<DIGEST_SECRET>
@admin_bp.post("/digest/run")
def run_weekly_digest():
    from config import Config
    secret = request.args.get("secret", "")
    if not Config.DIGEST_SECRET or secret != Config.DIGEST_SECRET:
        return jsonify({"error": "Unauthorized"}), 403

    from services.email import send_digest_email

    since  = datetime.utcnow() - timedelta(days=7)
    users  = User.query.all()
    frontend_url = os.environ.get("FRONTEND_URL", "https://morixa-hub-api.onrender.com")

    sent, skipped = 0, 0
    for user in users:
        following_ids = [f.following_id for f in Follow.query.filter_by(follower_id=user.id).all()]
        if not following_ids:
            skipped += 1
            continue

        posts = Post.query.filter(
            Post.user_id.in_(following_ids),
            Post.created_at >= since,
        ).order_by(Post.created_at.desc()).limit(5).all()

        if not posts:
            skipped += 1
            continue

        items = [{
            "title":       p.title,
            "author_name": p.author.full_name if p.author else "Unknown",
            "post_type":   p.post_type,
            "url":         f"{frontend_url}/post.html?id={p.id}",
        } for p in posts]

        if send_digest_email(user.email, user.full_name, items):
            sent += 1
        else:
            skipped += 1

    return jsonify({"message": "Digest run complete", "sent": sent, "skipped": skipped})


# ── app.py — N'oubliez pas d'ajouter dans create_app() :
#
#
# config.py — Ajoutez :
#