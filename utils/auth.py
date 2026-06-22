import jwt
import functools
from flask import request, jsonify, g


def require_auth(f):
    """Décorateur à placer sur les routes qui exigent un token JWT valide.
    Extrait l'ID utilisateur du token et le rend disponible via g.user_id."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Missing token"}), 401

        try:
            from config import Config
            payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
            g.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated