"""
routes/privacy.py — Détecteur d'identifiants patients avant publication.

Approche v1 : règles + expressions régulières.
- Rapide, gratuit, sans dépendance externe, fonctionne hors ligne.
- Volontairement permissif (mieux vaut un faux positif qu'un faux négatif
  sur ce sujet) — le médecin garde toujours le dernier mot via la case
  de confirmation côté frontend.

Limite connue : ne détecte pas les phrases qui identifient sans motif
structuré ("le patient est le maire de la ville"). Pour ce niveau de
nuance, il faudrait brancher un appel à un modèle de langage (voir note
en bas de fichier) — pas nécessaire pour ce prototype.
"""

import re
from flask import Blueprint, request, jsonify

privacy_bp = Blueprint("privacy", __name__, url_prefix="/api/privacy")

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

PHONE_RE = re.compile(r'(\+?\d{1,3}[\s.-]?)?(\(?\d{2,4}\)?[\s.-]?){2,4}\d{2,4}')

DATE_RE = re.compile(
    r'\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b'
    r'|\b(\d{1,2}\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|'
    r'january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{2,4})\b',
    re.IGNORECASE
)

LONGNUM_RE = re.compile(r'\b\d{8,}\b')

NAME_TRIGGER_RE = re.compile(
    r'\b(?:M\.|Mme|Mr\.|Mrs\.|Dr\.|nommé|nommée|appelé|appelée|named|called|patient[e]?\s*:?)\s+'
    r'([A-ZÉÈÀÂÎÔÛÇ][a-zéèàâîôûç]+(?:\s+[A-ZÉÈÀÂÎÔÛÇ][a-zéèàâîôûç]+){0,2})'
)

ADDRESS_RE = re.compile(
    r'\b\d{1,4}\s+(rue|avenue|boulevard|street|road|chemin|impasse)\s+[A-Za-zÀ-ÿ\s]{2,40}',
    re.IGNORECASE
)


def scan_text(text):
    issues = []

    for m in EMAIL_RE.finditer(text):
        issues.append({"type": "email", "text": m.group(),
                        "message": "Email address detected", "severity": "high"})

    for m in PHONE_RE.finditer(text):
        digits = re.sub(r'\D', '', m.group())
        if len(digits) >= 7:
            issues.append({"type": "phone", "text": m.group().strip(),
                            "message": "Possible phone number detected", "severity": "high"})

    for m in DATE_RE.finditer(text):
        issues.append({"type": "exact_date", "text": m.group(),
                        "message": "Exact date detected — consider an age range or year only",
                        "severity": "medium"})

    for m in LONGNUM_RE.finditer(text):
        issues.append({"type": "id_number", "text": m.group(),
                        "message": "Long number detected — possible ID or file number",
                        "severity": "high"})

    for m in NAME_TRIGGER_RE.finditer(text):
        issues.append({"type": "name", "text": m.group(1),
                        "message": "Possible patient name detected", "severity": "medium"})

    for m in ADDRESS_RE.finditer(text):
        issues.append({"type": "address", "text": m.group(),
                        "message": "Possible address detected", "severity": "medium"})

    # Déduplication des correspondances identiques
    seen, unique = set(), []
    for issue in issues:
        key = (issue["type"], issue["text"])
        if key not in seen:
            seen.add(key)
            unique.append(issue)

    return unique


@privacy_bp.post("/check")
def check_privacy():
    d    = request.get_json()
    text = f"{d.get('title','')} {d.get('body','')}"
    issues = scan_text(text)
    return jsonify({
        "has_issues": len(issues) > 0,
        "issues": issues,
        "count": len(issues),
    })


# ============================================================
# Note pour une v2 future (pas implémentée ici) :
#
# Pour attraper les cas que le regex ne peut pas voir (une phrase qui
# identifie quelqu'un sans motif structuré), on pourrait ajouter ici
# un appel serveur à l'API Anthropic avec un prompt strict du type
# "liste les passages qui pourraient identifier un patient, réponds
# uniquement en JSON". Ça nécessiterait une clé API Anthropic stockée
# en variable d'environnement côté serveur (jamais côté frontend),
# et ajouterait un coût + une latence par publication. À évaluer une
# fois que la version règles aura été testée par de vrais médecins.
# ============================================================