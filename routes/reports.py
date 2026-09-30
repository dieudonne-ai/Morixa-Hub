"""
routes/reports.py — Signalements (posts, dépôts, messages, utilisateurs).

Tout médecin authentifié peut signaler un contenu. Seuls les admins
(Config.ADMIN_EMAILS) peuvent lister, résoudre ou supprimer le contenu
signalé — voir routes/admin.py::require_admin.
"""
from flask import Blueprint, request, jsonify, g
from models import db, Report, User, Post, Repository, Message
from utils.auth import require_auth
from utils.security import clean_str, require_json, rate_limit
from routes.admin import require_admin
from datetime import datetime

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

TARGET_TYPES = {"user", "post", "repo", "message"}
TARGET_MODELS = {
    "user":    User,
    "post":    Post,
    "repo":    Repository,
    "message": Message,
}


@reports_bp.post("/")
@require_auth
@rate_limit(max_calls=20, window_seconds=600, key_prefix="report_create")
def create_report():
    d, err = require_json(["target_type", "target_id", "reason"])
    if err:
        return err

    target_type = clean_str(d["target_type"], 20).lower()
    if target_type not in TARGET_TYPES:
        return jsonify({"error": f"target_type must be one of {sorted(TARGET_TYPES)}"}), 400

    try:
        target_id = int(d["target_id"])
    except (TypeError, ValueError):
        return jsonify({"error": "target_id must be an integer"}), 400

    reason = clean_str(d["reason"], 1000)
    if not reason:
        return jsonify({"error": "Please describe the issue"}), 400

    model = TARGET_MODELS[target_type]
    if not db.session.get(model, target_id):
        return jsonify({"error": "Reported content was not found"}), 404

    report = Report(
        reporter_id=g.user_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
    )
    db.session.add(report)
    db.session.commit()
    return jsonify({"message": "Report submitted", "id": report.id}), 201


def _resolve_target(target_type, target_id):
    """Résumé lisible du contenu signalé pour l'écran admin."""
    model = TARGET_MODELS.get(target_type)
    if not model:
        return {"exists": False}
    obj = db.session.get(model, target_id)
    if not obj:
        return {"exists": False, "note": "Content was deleted"}

    if target_type == "user":
        return {"exists": True, "label": f"Dr. {obj.full_name}", "detail": obj.specialty or ""}
    if target_type == "post":
        return {"exists": True, "label": obj.title, "detail": (obj.body or "")[:150]}
    if target_type == "repo":
        return {"exists": True, "label": obj.name, "detail": obj.description or ""}
    if target_type == "message":
        return {"exists": True, "label": "Direct message", "detail": (obj.body or "")[:150]}
    return {"exists": False}


@reports_bp.get("/admin/all")
@require_admin
def admin_all_reports():
    status_filter = request.args.get("status")
    q = Report.query.order_by(Report.created_at.desc())
    if status_filter:
        q = q.filter_by(status=status_filter)
    reports = q.all()

    result = []
    for r in reports:
        reporter = db.session.get(User, r.reporter_id)
        result.append({
            "id": r.id,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            "reporter": reporter.to_dict() if reporter else {},
            "target_preview": _resolve_target(r.target_type, r.target_id),
        })
    return jsonify(result)


@reports_bp.post("/admin/<int:report_id>/dismiss")
@require_admin
def admin_dismiss(report_id):
    r = Report.query.get_or_404(report_id)
    r.status = "dismissed"
    r.reviewed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Report dismissed"})


@reports_bp.delete("/admin/content/<target_type>/<int:target_id>")
@require_admin
def admin_delete_reported_content(target_type, target_id):
    if target_type not in TARGET_MODELS or target_type == "user":
        return jsonify({"error": "Cannot delete this content type directly"}), 400

    model = TARGET_MODELS[target_type]
    obj = db.session.get(model, target_id)
    if obj:
        db.session.delete(obj)

    Report.query.filter_by(target_type=target_type, target_id=target_id).update(
        {"status": "reviewed", "reviewed_at": datetime.utcnow()}
    )
    db.session.commit()
    return jsonify({"message": "Content deleted and related reports resolved"})
