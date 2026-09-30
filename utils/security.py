# ============================================================
# utils/security.py
#
# Shared input-validation and abuse-prevention helpers used across
# routes/auth.py, routes/messages.py and routes/ai.py.
#
# Rate limiting is in-memory (per gunicorn worker). That's enough for
# a free-tier deployment running WEB_CONCURRENCY=1 — no Redis needed.
# If the app ever runs multiple workers, move _HITS to a shared store.
# ============================================================
import re
import time
import functools
from flask import request, jsonify, g

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')


def clean_str(value, max_len=None):
    """Strip whitespace and truncate. Always returns a string, even for None."""
    if value is None:
        return ""
    s = str(value).strip()
    if max_len:
        s = s[:max_len]
    return s


def is_valid_email(email):
    return bool(email) and bool(EMAIL_RE.match(email))


def password_errors(password):
    """Returns a list of unmet requirements (empty list = password is valid)."""
    errors = []
    if not password or len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r'[A-Za-z]', password or ""):
        errors.append("a letter")
    if not re.search(r'[0-9]', password or ""):
        errors.append("a number")
    return errors


def require_json(required_fields=None):
    """
    Parses the JSON body and checks that required_fields are present
    and non-empty. Returns (data, None) on success, or (None, response)
    on failure — call sites do:
        d, err = require_json(["a", "b"])
        if err: return err
    """
    data = request.get_json(silent=True) or {}
    missing = [f for f in (required_fields or [])
               if data.get(f) is None or data.get(f) == ""]
    if missing:
        return None, (jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400)
    return data, None


# ── Rate limiting ──────────────────────────────────────────────
_HITS = {}  # key -> list[timestamp]


def _client_key(key_prefix):
    uid = getattr(g, "user_id", None)
    if uid:
        return f"{key_prefix}:user:{uid}"
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    return f"{key_prefix}:ip:{ip}"


def rate_limit(max_calls=10, window_seconds=60, key_prefix="default"):
    """Decorator factory: limits an endpoint to max_calls per window_seconds,
    keyed by the authenticated user (if any) or the caller's IP."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            key = _client_key(key_prefix)
            now = time.time()
            hits = [t for t in _HITS.get(key, []) if now - t < window_seconds]
            if len(hits) >= max_calls:
                return jsonify({"error": "Too many requests. Please slow down and try again shortly."}), 429
            hits.append(now)
            _HITS[key] = hits
            return f(*args, **kwargs)
        return wrapped
    return decorator
