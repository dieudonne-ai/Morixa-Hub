"""
services/ai.py — Couche d'accès à l'IA.

Provider configurable via AI_PROVIDER (openai | groq | anthropic | gemini | none).
Aucune clé côté frontend : tout passe par le serveur.
"""
import os
import requests
from config import Config

SYSTEM_PROMPT = (
    "You are the assistant of Morixa Hub, a professional network for doctors. "
    "Answer concisely, in the same language as the user (French or English). "
    "Never invent clinical facts; remind the user to verify critical information. "
    "You are NOT a substitute for professional medical judgment."
)


def ai_available() -> bool:
    return Config.AI_PROVIDER != "none" and bool(Config.AI_API_KEY)


def _model(default: str) -> str:
    return Config.AI_MODEL or default


def _chat_openai(messages, base_url, api_key, model, max_tokens):
    res = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"].strip()


def _chat_anthropic(messages, api_key, model, max_tokens):
    res = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={"model": model, "max_tokens": max_tokens, "system": SYSTEM_PROMPT,
              "messages": [{"role": m["role"], "content": m["content"]} for m in messages
                            if m["role"] != "system"]},
        timeout=60,
    )
    res.raise_for_status()
    return "".join(b.get("text", "") for b in res.json()["content"]).strip()


def _chat_gemini(messages, api_key, model, max_tokens):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
           f":generateContent?key={api_key}")
    contents = [{"role": "user" if m["role"] != "model" else "model",
                 "parts": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
    res = requests.post(url, json={
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens},
    }, timeout=60)
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def chat(messages: list, max_tokens: int = None) -> str:
    """Point d'entrée unique. messages = [{"role": "system"|"user"|"assistant", "content": str}]"""
    if not ai_available():
        raise RuntimeError("AI is not configured on this server (AI_PROVIDER / AI_API_KEY).")

    max_tokens = max_tokens or Config.AI_MAX_TOKENS

    if Config.AI_PROVIDER == "openai":
        return _chat_openai(messages, "https://api.openai.com/v1",
                            Config.AI_API_KEY, _model("gpt-4o-mini"), max_tokens)
    if Config.AI_PROVIDER == "groq":
        return _chat_openai(messages, "https://api.groq.com/openai/v1",
                            Config.AI_API_KEY, _model("llama-3.1-8b-instant"), max_tokens)
    if Config.AI_PROVIDER == "anthropic":
        return _chat_anthropic(messages, Config.AI_API_KEY,
                               _model("claude-3-5-haiku-latest"), max_tokens)
    if Config.AI_PROVIDER == "gemini":
        return _chat_gemini(messages, Config.AI_API_KEY,
                            _model("gemini-1.5-flash"), max_tokens)

    raise RuntimeError(f"Unknown AI provider: {Config.AI_PROVIDER}")


# ── Helpers métier ───────────────────────────────────────────
def summarize_post(title: str, body: str) -> str:
    return chat([
        {"role": "user", "content":
         f"Summarize this medical post in 4-6 bullet points (keep key facts, "
         f"drop redundant details). Title: {title}\n\n{body}"}
    ], max_tokens=500)


def suggest_reply(context: list, my_name: str) -> str:
    """context = liste de {sender_name, body} — propose une réponse de médecin à médecin."""
    convo = "\n".join(f"{m['sender_name']}: {m['body'][:500]}" for m in context[-10:])
    return chat([
        {"role": "user", "content":
         f"Here is a private conversation between doctors. Draft a short, "
         f"professional reply as Dr. {my_name}. Reply in the conversation's language, "
         f"max 4 sentences, no placeholders.\n\n{convo}"}
    ], max_tokens=300)


def moderate(text: str) -> dict:
    """Retourne {'safe': bool, 'reason': str}. Complète le scanner regex de privacy.py."""
    raw = chat([
        {"role": "user", "content":
         "Analyze this medical text for (1) patient-identifying information, "
         "(2) offensive/toxic content. Answer ONLY with JSON: "
         '{"safe": true/false, "reason": "short explanation"}\n\n' + text[:8000]}
    ], max_tokens=200)
    import json, re as _re
    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if not m:
        return {"safe": True, "reason": ""}
    try:
        out = json.loads(m.group())
        return {"safe": bool(out.get("safe", True)),
                "reason": str(out.get("reason", ""))[:300]}
    except Exception:
        return {"safe": True, "reason": ""}