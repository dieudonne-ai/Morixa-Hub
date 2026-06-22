import os
import secrets

class Config:
    # ── Sécurité ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
    JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", 24))

    # ── Base de données ────────────────────────────────────────
    # En production : variable DATABASE_URL fournie par Neon
    # En local      : DATABASE_URL dans votre .env ou fallback SQL Server
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    if DATABASE_URL.startswith("postgres://"):
        # Neon / Heroku fournissent parfois "postgres://" au lieu de "postgresql://"
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL or (
        # Fallback local SQL Server (uniquement pour le dev Windows)
        "mssql+pyodbc://DESKTOP-DNOL710/MedHub"
        "?driver=ODBC+Driver+17+for+SQL+Server"
        "&trusted_connection=yes"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # vérifie la connexion avant chaque requête
        "pool_recycle":  300,        # recycle les connexions toutes les 5 min
    }

    # ── Fichiers uploadés ──────────────────────────────────────
    # Stockage local en dev, Cloudflare R2 en production
    USE_R2 = os.environ.get("USE_R2", "false").lower() == "true"
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    # Cloudflare R2 (remplir après création du bucket)
    R2_ACCOUNT_ID        = os.environ.get("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID     = os.environ.get("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME       = os.environ.get("R2_BUCKET_NAME", "morixa-uploads")
    R2_PUBLIC_URL        = os.environ.get("R2_PUBLIC_URL", "")  # URL publique du bucket

    # ── Environnement ──────────────────────────────────────────
    DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    TESTING = False