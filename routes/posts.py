from flask import Blueprint, request, jsonify
from models import db, Post, User, Comment, Like
from services.points import award_points

posts_bp = Blueprint("posts", __name__, url_prefix="/api/posts")


# ── Liste des posts (avec recherche + comments_count) ────────

@posts_bp.get("/")
def get_posts():
    page      = request.args.get("page", 1, type=int)
    per_page  = request.args.get("per_page", 10, type=int)
    post_type = request.args.get("type")
    specialty = request.args.get("specialty")
    search    = request.args.get("search")
    user_id   = request.args.get("user_id", type=int)   # ← cette ligne manquait

    q = Post.query.order_by(Post.created_at.desc())
    if post_type: q = q.filter_by(post_type=post_type)
    if specialty: q = q.filter_by(specialty=specialty)
    if user_id:   q = q.filter_by(user_id=user_id)       # ← et cette ligne aussi
    if search:
        q = q.filter(
            Post.title.ilike(f"%{search}%") |
            Post.body.ilike(f"%{search}%")
        )

    p = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "posts": [{
            **post.to_dict(),
            "comments_count": Comment.query.filter_by(post_id=post.id).count(),
        } for post in p.items],
        "total": p.total,
        "pages": p.pages,
    })

# ── Détail d'un post ─────────────────────────────────────────
@posts_bp.get("/<int:pid>")
def get_post(pid):
    p = Post.query.get_or_404(pid)
    p.views = (p.views or 0) + 1
    db.session.commit()
    return jsonify({
        **p.to_dict(),
        "comments_count": Comment.query.filter_by(post_id=pid).count(),
        "files": [{
            "id":        f.id,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "file_size": f.file_size,
        } for f in p.files],
    })


# ── Créer un post ────────────────────────────────────────────
@posts_bp.post("/")
def create_post():
    d    = request.get_json()
    post = Post(
        user_id   = d["user_id"],
        title     = d["title"],
        body      = d["body"],
        post_type = d["post_type"],
        specialty = d.get("specialty"),
    )
    db.session.add(post)
    db.session.flush()
    user = User.query.get(d["user_id"])
    award_points(user, "publication", ref_type="post", ref_id=post.id)
    db.session.commit()
    return jsonify(post.to_dict()), 201


# ── Liker un post ────────────────────────────────────────────
@posts_bp.post("/<int:pid>/like")
def like_post(pid):
    d    = request.get_json()
    uid  = d["user_id"]
    post = Post.query.get_or_404(pid)

    if Like.query.filter_by(user_id=uid, post_id=pid).first():
        return jsonify({"error": "Already liked"}), 400

    db.session.add(Like(user_id=uid, post_id=pid))
    post.likes = (post.likes or 0) + 1
    award_points(post.author, "favori_recu", ref_type="post", ref_id=pid)
    db.session.commit()
    return jsonify({"likes": post.likes})


# ── Commenter un post ────────────────────────────────────────
@posts_bp.post("/<int:pid>/comment")
def comment_post(pid):
    d   = request.get_json()
    uid = d["user_id"]

    # 1. Vérifier que le post existe avant tout
    post = Post.query.get_or_404(pid)

    # 2. Créer et committer le commentaire d'abord
    comment = Comment(post_id=pid, user_id=uid, body=d["body"])
    db.session.add(comment)
    db.session.commit()   # ← commit séparé pour éviter l'autoflush conflict

    # 3. Ensuite attribuer les points (utilise db.session.get au lieu de User.query.get)
    user = db.session.get(User, uid)
    if user:
        award_points(user, "commentaire", ref_type="post", ref_id=pid)
        db.session.commit()

    return jsonify({"message": "Comment added", "id": comment.id}), 201


# ── Lire les commentaires d'un post ─────────────────────────
@posts_bp.get("/<int:pid>/comments")
def get_comments(pid):
    comments = Comment.query.filter_by(post_id=pid)\
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


# ── Supprimer un post ────────────────────────────────────────
@posts_bp.delete("/<int:pid>")
def delete_post(pid):
    post = Post.query.get_or_404(pid)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": "Post deleted"})


@posts_bp.put("/<int:pid>")
def update_post(pid):
    """Modifier un post (titre, corps, spécialité)."""
    post = Post.query.get_or_404(pid)
    d    = request.get_json()
    uid  = d.get("user_id")

    # Vérifier que c'est bien l'auteur
    if post.user_id != uid:
        return jsonify({"error": "Not authorized"}), 403

    post.title     = d.get("title",    post.title)
    post.body      = d.get("body",     post.body)
    post.specialty = d.get("specialty", post.specialty)
    db.session.commit()
    return jsonify(post.to_dict())


    # ── Supprimer un post ────────────────────────────────────────
@posts_bp.delete("/<int:pid>")
def delete_post(pid):
    """Supprimer un post (auteur seulement)."""
    post = Post.query.get_or_404(pid)
    d = request.get_json() or {}
    uid = d.get("user_id")

    if post.user_id != uid:
        return jsonify({"error": "Not authorized"}), 403

    db.session.delete(post)
    db.session.commit()
    return jsonify({"message": "Post deleted"})    