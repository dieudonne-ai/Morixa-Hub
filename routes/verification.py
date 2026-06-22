from flask import Blueprint, request, jsonify, g
from models import db, User, VerificationRequest, Notification, VerifLevel
from werkzeug.utils import secure_filename
import os
from datetime import datetime

verif_bp = Blueprint("verification", __name__, url_prefix="/api/verification")

# Domaines email institutionnels reconnus (à enrichir)
INSTITUTIONAL_DOMAINS = {
    ".ac.", ".edu", ".gov", ".hospital", ".sante.",
    "mulago", "mak.ac.ug", "uon.ac.ke", "chu-", "univ-",
    "health.gov", "ministry", "ihvn.org", "who.int", "msf.org"
}

ALLOWED_DOCS = {"pdf", "jpg", "jpeg", "png"}


def detect_institutional_email(email: str) -> bool:
    """Vérifie si l'email ressemble à un domaine institutionnel médical."""
    email_lower = email.lower()
    return any(marker in email_lower for marker in INSTITUTIONAL_DOMAINS)


@verif_bp.post("/check-email")
def check_email():
    """
    Appelé juste après l'inscription pour attribuer automatiquement
    le badge EMAIL si le domaine est reconnu.
    """
    d    = request.get_json()
    uid  = d.get("user_id")
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if detect_institutional_email(user.email) and user.verif_level == VerifLevel.NONE:
        user.verif_level = VerifLevel.EMAIL
        db.session.add(Notification(
            user_id=uid, type="points",
            message="Your email was recognized as institutional. "
                    "You have been awarded the <strong>Email Verified</strong> badge."
        ))
        db.session.commit()

    return jsonify({
        "verif_level": user.verif_level,
        "upgraded":    user.verif_level == VerifLevel.EMAIL
    })


@verif_bp.post("/submit")
def submit_verification():
    """
    Le médecin soumet son numéro de licence + un document justificatif.
    Crée une demande en attente de review manuelle.
    """
    user_id        = request.form.get("user_id", type=int)
    license_number = request.form.get("license_number", "").strip()
    country        = request.form.get("country", "").strip()
    doc            = request.files.get("document")

    if not user_id or not license_number or not doc:
        return jsonify({"error": "user_id, license_number and document are required"}), 400

    ext = doc.filename.rsplit(".", 1)[-1].lower() if "." in doc.filename else ""
    if ext not in ALLOWED_DOCS:
        return jsonify({"error": "Document must be PDF, JPG or PNG"}), 400

    from config import Config
    upload_dir = os.path.join(Config.UPLOAD_FOLDER, "verifications")
    os.makedirs(upload_dir, exist_ok=True)
    fname = secure_filename(f"verif_{user_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}")
    path  = os.path.join(upload_dir, fname)
    doc.save(path)

    # Annuler toute demande précédente en attente
    prev = VerificationRequest.query.filter_by(user_id=user_id, status="pending").first()
    if prev:
        db.session.delete(prev)

    req = VerificationRequest(
        user_id        = user_id,
        license_number = license_number,
        country        = country,
        document_path  = path,
        status         = "pending",
    )
    db.session.add(req)

    # Passer le niveau à DOCUMENT (en attente) si pas encore vérifié
    user = db.session.get(User, user_id)
    if user and user.verif_level in (VerifLevel.NONE, VerifLevel.EMAIL):
        user.verif_level = VerifLevel.DOCUMENT

    db.session.add(Notification(
        user_id=user_id, type="points",
        message="Your verification request has been submitted and is under review. "
                "We will notify you within 48 hours."
    ))
    db.session.commit()
    return jsonify({"message": "Verification request submitted", "status": "pending"}), 201


@verif_bp.get("/status/<int:user_id>")
def verification_status(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    req = VerificationRequest.query.filter_by(user_id=user_id).order_by(
        VerificationRequest.created_at.desc()
    ).first()

    return jsonify({
        "verif_level":    user.verif_level or "none",
        "license_number": user.license_number,
        "request": {
            "status":        req.status,
            "reviewer_note": req.reviewer_note,
            "created_at":    req.created_at.isoformat(),
        } if req else None,
    })


# ── Routes d'administration (à protéger avec un middleware admin) ──

@verif_bp.get("/admin/pending")
def admin_list_pending():
    """Liste toutes les demandes en attente."""
    reqs = VerificationRequest.query.filter_by(status="pending")\
                                    .order_by(VerificationRequest.created_at).all()
    result = []
    for r in reqs:
        user = db.session.get(User, r.user_id)
        result.append({
            "request_id":     r.id,
            "user":           user.to_dict() if user else {},
            "license_number": r.license_number,
            "country":        r.country,
            "document_path":  r.document_path,
            "created_at":     r.created_at.isoformat(),
        })
    return jsonify(result)


@verif_bp.post("/admin/review/<int:request_id>")
def admin_review(request_id):
    """Approuver ou rejeter une demande."""
    d      = request.get_json()
    action = d.get("action")          # "approve" ou "reject"
    note   = d.get("reviewer_note", "")

    req = VerificationRequest.query.get_or_404(request_id)
    req.status        = "approved" if action == "approve" else "rejected"
    req.reviewer_note = note
    req.reviewed_at   = datetime.utcnow()

    user = db.session.get(User, req.user_id)
    if user:
        if action == "approve":
            user.verif_level    = VerifLevel.VERIFIED
            user.license_number = req.license_number
            msg = "🎉 Your account has been <strong>verified</strong>. " \
                  "The <strong>Verified Physician</strong> badge is now visible on your profile."
        else:
            user.verif_level = VerifLevel.EMAIL  # recule au niveau précédent
            msg = f"Your verification request was not approved. " \
                  f"Reason: {note or 'Document could not be validated.'} " \
                  f"You may submit a new request with a clearer document."

        db.session.add(Notification(user_id=user.id, type="points", message=msg))

    db.session.commit()
    return jsonify({"message": f"Request {req.status}", "verif_level": user.verif_level if user else None})


@verif_bp.get("/admin/all")
def admin_list_all():
    """Liste toutes les demandes (pending + approved + rejected)."""
    reqs = VerificationRequest.query.order_by(
        VerificationRequest.created_at.desc()
    ).all()
    result = []
    for r in reqs:
        user = db.session.get(User, r.user_id)
        result.append({
            "request_id":     r.id,
            "status":         r.status,
            "user":           user.to_dict() if user else {},
            "license_number": r.license_number,
            "country":        r.country,
            "document_path":  r.document_path,
            "reviewer_note":  r.reviewer_note,
            "created_at":     r.created_at.isoformat(),
            "reviewed_at":    r.reviewed_at.isoformat() if r.reviewed_at else None,
        })
    return jsonify(result)


@verif_bp.get("/document/<int:request_id>")
def serve_document(request_id):
    """
    Sert le document justificatif d'une demande de vérification.
    Protégé : seul un admin devrait appeler cette route.
    Dans une vraie prod, ajoutez @require_admin ici.
    """
    from flask import send_file
    req = VerificationRequest.query.get_or_404(request_id)
    if not req.document_path or not os.path.exists(req.document_path):
        return jsonify({"error": "Document not found"}), 404
    return send_file(req.document_path, as_attachment=False)