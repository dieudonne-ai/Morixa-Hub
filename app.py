"""
MedHub - Backend Flask + MS SQL Server
Structure du projet :
    medhub/
    ├── app.py
    ├── config.py
    ├── models.py
    ├── routes/
    │   ├── auth.py
    │   ├── posts.py
    │   ├── repos.py
    │   ├── messages.py
    │   ├── files.py
    │   └── users.py
    ├── services/
    │   └── points.py
    └── uploads/
"""


# ============================================================
# app.py  —  Point d'entrée principal
# ============================================================
from dotenv import load_dotenv
load_dotenv()
import os
from flask import Flask, app
from flask_cors import CORS
from models import db
from config import Config
from flask import send_from_directory
from flask_cors import CORS

    
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    # Expose app au niveau module pour gunicorn app:app
    app = create_app()

    # Blueprints
    from routes.auth         import auth_bp
    from routes.posts        import posts_bp
    from routes.files        import files_bp
    from routes.messages     import messages_bp
    from routes.users        import users_bp
    from routes.repos        import repos_bp
    from routes.follows      import follows_bp
    from routes.verification import verif_bp
    from routes.privacy      import privacy_bp

    for bp in [auth_bp, posts_bp, files_bp, messages_bp,
               users_bp, repos_bp, follows_bp, verif_bp, privacy_bp]:
        app.register_blueprint(bp)

    # Frontend statique
    @app.route("/")
    def index():
        return send_from_directory("frontend", "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        return send_from_directory("frontend", filename)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    # En local : debug activé. En prod, gunicorn gère ça.
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))