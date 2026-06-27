from flask import Blueprint, request, jsonify
from models import db, Repository, File, User, RepoStar, Comment
from services.points import award_points


repos_bp = Blueprint("repos", __name__, url_prefix="/api/repos")


@repos_bp.get("/")
def list_repos():
    page     = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 12, type=int)
    rtype    = request.args.get("type")
    mine     = request.args.get("user_id", type=int)
    viewer   = request.args.get("viewer_id", type=int)   # qui regarde (pour savoir s'il a déjà starré)

    q = Repository.query.filter_by(is_public=True)
    if rtype: q = q.filter_by(repo_type=rtype)
    if mine:  q = Repository.query.filter_by(user_id=mine)

    p = q.order_by(Repository.stars.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "repos": [_repo_dict(r, viewer_id=viewer) for r in p.items],
        "total": p.total,
        "pages": p.pages,
    })

@repos_bp.get("/<int:repo_id>")
def get_repo(repo_id):
    viewer = request.args.get("viewer_id", type=int)
    r = Repository.query.get_or_404(repo_id)
    return jsonify(_repo_dict(r, detail=True, viewer_id=viewer))


@repos_bp.post("/")
def create_repo():
    d = request.get_json()
    r = Repository(
        user_id     = d["user_id"],
        name        = d["name"],
        description = d.get("description"),
        repo_type   = d.get("repo_type", "guide"),
        is_public   = d.get("is_public", True),
    )
    db.session.add(r)
    db.session.flush()
    user = db.session.get(User, d["user_id"])
    award_points(user, "repo_cree", ref_type="repo", ref_id=r.id)
    db.session.commit()
    return jsonify(_repo_dict(r)), 201

@repos_bp.post("/<int:repo_id>/star")
def star_repo(repo_id):
    """
    Toggle star : premier clic = star, second clic = unstar.
    Un seul star par utilisateur, garanti par la contrainte unique
    sur (user_id, repo_id) dans RepoStar.
    """
    d    = request.get_json()
    uid  = d.get("user_id")
    repo = Repository.query.get_or_404(repo_id)

    existing = RepoStar.query.filter_by(user_id=uid, repo_id=repo_id).first()

    if existing:
        db.session.delete(existing)
        repo.stars = max((repo.stars or 0) - 1, 0)
        db.session.commit()
        return jsonify({"stars": repo.stars, "is_starred": False})

    db.session.add(RepoStar(user_id=uid, repo_id=repo_id))
    repo.stars = (repo.stars or 0) + 1
    db.session.commit()

    # Pas de points si on starre son propre dépôt
    if repo.user_id != uid:
        owner = db.session.get(User, repo.user_id)
        if owner:
            award_points(owner, "repo_star", ref_type="repo", ref_id=repo_id)
            db.session.commit()

    return jsonify({"stars": repo.stars, "is_starred": True})


@repos_bp.post("/<int:repo_id>/fork")
def fork_repo(repo_id):
    d   = request.get_json()
    uid = d.get("user_id")
    src = Repository.query.get_or_404(repo_id)

    fork = Repository(
        user_id     = uid,
        name        = src.name + "-fork",
        description = f"Forked from {src.name}. {src.description or ''}".strip(),
        repo_type   = src.repo_type,
        is_public   = src.is_public,
        stars       = 0,
        forks       = 0,
    )
    db.session.add(fork)
    src.forks = (src.forks or 0) + 1
    db.session.flush()

    for f in src.files:
        db.session.add(File(
            user_id   = uid,
            repo_id   = fork.id,
            file_name = f.file_name,
            file_path = f.file_path,
            file_size = f.file_size,
            file_type = f.file_type,
        ))

    db.session.commit()
    return jsonify({
        "message":   "Repository forked successfully",
        "fork_id":   fork.id,
        "fork_name": fork.name,
        "forks":     src.forks,
    }), 201


@repos_bp.delete("/<int:repo_id>")
def delete_repo(repo_id):
    repo = Repository.query.get_or_404(repo_id)
    db.session.delete(repo)
    db.session.commit()
    return jsonify({"message": "Repository deleted"})


def _repo_dict(r, detail=False, viewer_id=None):
    owner = db.session.get(User, r.user_id)
    d = {
        "id": r.id, "name": r.name, "description": r.description,
        "repo_type": r.repo_type, "stars": r.stars, "forks": r.forks,
        "is_public": r.is_public,
        "files_count": len(r.files),
        "created_at": r.created_at.isoformat(),
        "owner": owner.to_dict() if owner else {},
        "is_starred": False,
    }
    if viewer_id:
        d["is_starred"] = RepoStar.query.filter_by(user_id=viewer_id, repo_id=r.id).first() is not None
    if detail:
        d["files"] = [{
            "id": f.id, "file_name": f.file_name,
            "file_type": f.file_type, "file_size": f.file_size,
            "created_at": f.created_at.isoformat(),
        } for f in r.files]
    return d

    
@repos_bp.get("/<int:repo_id>/comments")
def get_repo_comments(repo_id):
    """Commentaires spécifiques à un dépôt."""
    comments = Comment.query.filter_by(repo_id=repo_id)\
                            .order_by(Comment.created_at.asc()).all()
    return jsonify([{
        "id":         c.id,
        "body":       c.body,
        "created_at": c.created_at.isoformat(),
        "author": {
            "id":        c.author.id,
            "full_name": c.author.full_name,
            "specialty": c.author.specialty,
        } if c.author else {}
    } for c in comments])


@repos_bp.post("/<int:repo_id>/comments")
def add_repo_comment(repo_id):
    """Ajouter un commentaire à un dépôt (sans affecter les posts)."""
    d       = request.get_json()
    uid     = d.get("user_id")
    comment = Comment(
        repo_id = repo_id,     # ← repo_id, PAS post_id
        post_id = None,        # ← explicitement NULL
        user_id = uid,
        body    = d["body"],
    )
    db.session.add(comment)

    user = db.session.get(User, uid)
    if user:
        award_points(user, "commentaire", ref_type="repo", ref_id=repo_id)

    db.session.commit()
    return jsonify({"message": "Comment added", "id": comment.id}), 201
