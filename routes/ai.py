"""
routes/ai.py — Endpoints IA (tous authentifiés + rate-limités par utilisateur).
"""
import time
from flask import Blueprint, request, jsonify, g
from utils.auth import require_auth
from utils.security import rate_limit, clean_str
from services import ai

ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

# Rate limit par utilisateur : AI_RATE_LIMIT appels / heure
_user_hits = {}


def _user_rate_limit(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        from config import Config
        now = time.time()
        hits = [t for t in _user_hits.get(g.user_id, []) if now - t < 3600]
        if len(hits) >= Config.AI_RATE_LIMIT:
            return jsonify({"error": "AI quota exceeded, try again later."}), 429
        hits.append(now)
        _user_hits[g.user_id] = hits
        return f(*args, **kwargs)
    return wrapped


def _guard_body():
    from config import Config
    d    = request.get_json(silent=True) or {}
    body = clean_str(d.get("body") or d.get("text") or d.get("message"), Config.AI_BODY_MAXCHARS)
    if not body:
        return None, (jsonify({"error": "Empty content"}), 400)
    return body, None


@ai_bp.get("/status")
@require_auth
def status():
    return jsonify({"available": ai.ai_available(), "provider": ai.Config.AI_PROVIDER
                    if hasattr(ai, "Config") else None})


@ai_bp.post("/assistant")
@require_auth
@_user_rate_limit
def assistant():
    d, err = (request.get_json(silent=True) or {}), None
    message = clean_str(d.get("message"), 4000)
    history = d.get("history", [])[-10:]
    if not message:
        return jsonify({"error": "Empty message"}), 400

    messages = [{"role": "system", "content": ai.SYSTEM_PROMPT}]
    for h in history:
        role = h.get("role") if h.get("role") in ("user", "assistant") else "user"
        messages.append({"role": role, "content": clean_str(h.get("content"), 2000)})
    messages.append({"role": "user", "content": message})

    try:
        return jsonify({"reply": ai.chat(messages)})
    except Exception as e:
        return jsonify({"error": f"AI error: {e}"}), 502


@ai_bp.post("/summarize")
@require_auth
@_user_rate_limit
def summarize():
    body, err = _guard_body()
    if err:
        return err
    title = clean_str((request.get_json(silent=True) or {}).get("title"), 255) or "Untitled"
    try:
        return jsonify({"summary": ai.summarize_post(title, body)})
    except Exception as e:
        return jsonify({"error": f"AI error: {e}"}), 502


@ai_bp.post("/suggest-reply")
@require_auth
@_user_rate_limit
def suggest_reply():
    """Contexte : dernières lignes d'une conversation. Retourne un brouillon de réponse."""
    d = request.get_json(silent=True) or {}
    messages = d.get("messages", [])
    if not messages:
        return jsonify({"error": "Empty conversation"}), 400
    ctx = [{"sender_name": clean_str(m.get("sender_name"), 100) or "Doctor",
            "body": clean_str(m.get("body"), 1000)} for m in messages]
    try:
        return jsonify({"suggestion": ai.suggest_reply(ctx, g.user.full_name)})
    except Exception as e:
        return jsonify({"error": f"AI error: {e}"}), 502


@ai_bp.post("/moderate")
@require_auth
@_user_rate_limit
def moderate():
    """Modération IA (complète /api/privacy/check basé sur regex)."""
    body, err = _guard_body()
    if err:
        return err
    try:
        return jsonify(ai.moderate(body))
    except Exception as e:
        return jsonify({"error": f"AI error: {e}"}), 502