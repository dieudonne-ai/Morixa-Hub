# ============================================================
# models.py
# ============================================================
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import enum

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    full_name     = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    specialty     = db.Column(db.String(100))
    hospital      = db.Column(db.String(150))
    country       = db.Column(db.String(80))
    bio           = db.Column(db.String(500))
    avatar_url    = db.Column(db.String(255))
    level         = db.Column(db.String(50), default="Interne")
    total_points  = db.Column(db.Integer, default=0)
    is_verified   = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    verif_level = db.Column(db.String(20), default="none")
    license_number = db.Column(db.String(100))

    posts         = db.relationship("Post", backref="author", lazy=True)

    def to_dict(self):
        return {
            "id": self.id, "full_name": self.full_name,
            "specialty": self.specialty, "hospital": self.hospital,
            "country": self.country, "level": self.level,
            "total_points": self.total_points, "avatar_url": self.avatar_url,
            "verif_level":    self.verif_level or "none",
            "license_number": self.license_number,

        }

class Post(db.Model):
    __tablename__ = "posts"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title      = db.Column(db.String(255), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    post_type  = db.Column(db.String(50), nullable=False)
    specialty  = db.Column(db.String(100))
    views      = db.Column(db.Integer, default=0)
    likes      = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments   = db.relationship("Comment", backref="post", lazy=True)
    files      = db.relationship("File", backref="post", lazy=True)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title, "body": self.body,
            "post_type": self.post_type, "specialty": self.specialty,
            "views": self.views, "likes": self.likes,
            "author": self.author.to_dict(),
            "created_at": self.created_at.isoformat(),
        }


class Comment(db.Model):
    __tablename__ = "comments"
    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey("posts.id"),         nullable=True)  # ← était False
    repo_id    = db.Column(db.Integer, db.ForeignKey("repositories.id"),  nullable=True)  # ← NOUVEAU
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),         nullable=False)
    body       = db.Column(db.Text,    nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author     = db.relationship("User")

class Like(db.Model):
    __tablename__ = "likes"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id"),)

class Repository(db.Model):
    __tablename__ = "repositories"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name        = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500))
    repo_type   = db.Column(db.String(50))
    stars       = db.Column(db.Integer, default=0)
    forks       = db.Column(db.Integer, default=0)
    is_public   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    files       = db.relationship("File", backref="repo", lazy=True)


class RepoStar(db.Model):
    __tablename__ = "repo_stars"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    repo_id    = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "repo_id", name="uq_user_repo_star"),)

class File(db.Model):
    __tablename__ = "files"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey("posts.id"), nullable=True)
    repo_id    = db.Column(db.Integer, db.ForeignKey("repositories.id"), nullable=True)
    file_name  = db.Column(db.String(255), nullable=False)
    file_path  = db.Column(db.String(500), nullable=False)
    file_size  = db.Column(db.BigInteger)
    file_type  = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    __tablename__ = "messages"
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    sender      = db.relationship("User", foreign_keys=[sender_id])
    receiver    = db.relationship("User", foreign_keys=[receiver_id])

class PointsLog(db.Model):
    __tablename__ = "points_log"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action     = db.Column(db.String(100), nullable=False)
    points     = db.Column(db.Integer, nullable=False)
    ref_type   = db.Column(db.String(50))
    ref_id     = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = "notifications"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type       = db.Column(db.String(50), nullable=False)
    message    = db.Column(db.String(300), nullable=False)
    ref_type   = db.Column(db.String(50))
    ref_id     = db.Column(db.Integer)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Follow(db.Model):
    __tablename__ = "follows"
    id           = db.Column(db.Integer, primary_key=True)
    follower_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),)
    
class VerifLevel(str, enum.Enum):
    NONE         = "none"          # compte non vérifié
    EMAIL        = "email"         # email institutionnel détecté
    DOCUMENT     = "document"      # document uploadé, en attente de review
    VERIFIED     = "verified"      # vérifié manuellement par l'équipe
    REGISTRY     = "registry"      # croisé avec un registre officiel (futur)

class VerificationRequest(db.Model):
    __tablename__ = "verification_requests"
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status        = db.Column(db.String(20), default="pending")  # pending|approved|rejected
    document_path = db.Column(db.String(500))
    license_number= db.Column(db.String(100))
    country       = db.Column(db.String(80))
    notes         = db.Column(db.String(500))           # notes de l'équipe
    reviewer_note = db.Column(db.String(500))           # retour au médecin
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at   = db.Column(db.DateTime)