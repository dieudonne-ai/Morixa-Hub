import os
from flask import Blueprint, request, jsonify, g
from models import db, File, User, Repository
from werkzeug.utils import secure_filename
from services.storage import save_file, get_file_response
from services.points import award_points
from utils.auth import require_auth

files_bp = Blueprint("files", __name__, url_prefix="/api/files")

ALLOWED_EXT = {"pdf", "docx", "xlsx", "zip", "png", "jpg", "jpeg", "dicom"}


@files_bp.post("/upload")
def upload_file():
    f       = request.files.get("file")
    user_id = request.form.get("user_id", type=int)
    post_id = request.form.get("post_id", type=int)
    repo_id = request.form.get("repo_id", type=int)

    if not f:
        return jsonify({"error": "No file provided"}), 400

    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED_EXT:
        return jsonify({"error": f"File type .{ext} not allowed"}), 400

    fname = secure_filename(f.filename)

    # Détermine le sous-dossier selon le contexte
    subfolder = "verifications" if repo_id is None and post_id is None else "uploads"

    try:
        path_or_key, _ = save_file(f, fname, subfolder=subfolder)
    except Exception as e:
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500

    rec = File(
        user_id   = user_id,
        post_id   = post_id,
        repo_id   = repo_id,
        file_name = fname,
        file_path = path_or_key,
        file_size = f.content_length or 0,
        file_type = ext,
    )
    db.session.add(rec)
    db.session.flush()

    user = db.session.get(User, user_id)
    if user:
        award_points(user, "fichier", ref_type="file", ref_id=rec.id)

    db.session.commit()
    return jsonify({"message": "File uploaded", "file_id": rec.id}), 201


@files_bp.get("/post/<int:post_id>")
def files_by_post(post_id):
    files = File.query.filter_by(post_id=post_id).all()
    return jsonify([_file_dict(f) for f in files])


@files_bp.get("/repo/<int:repo_id>")
def files_by_repo(repo_id):
    files = File.query.filter_by(repo_id=repo_id).all()
    return jsonify([_file_dict(f) for f in files])


@files_bp.get("/download/<int:file_id>")
@require_auth
def download_file(file_id):
    f = File.query.get_or_404(file_id)

    # Vérification accès dépôt privé
    if f.repo_id:
        repo = db.session.get(Repository, f.repo_id)
        if repo and not repo.is_public and repo.user_id != g.user_id:
            return jsonify({"error": "Access denied"}), 403

    return get_file_response(f.file_path, f.file_name)


def _file_dict(f):
    return {
        "id":        f.id,
        "file_name": f.file_name,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "post_id":   f.post_id,
        "repo_id":   f.repo_id,
        "created_at": f.created_at.isoformat(),
    }