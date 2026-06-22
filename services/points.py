# ============================================================
# services/points.py  —  Système de gamification
# ============================================================
import datetime
from models import db, PointsLog, Notification

POINTS_CONFIG = {
    "publication":    15,
    "commentaire":     5,
    "fichier":        10,
    "favori_recu":     3,
    "repo_cree":      20,
    "repo_star":       3,
    "connexion_jour":  2,
}

LEVELS = [
    (0,    "Interne"),
    (500,  "Résident"),
    (2000, "Spécialiste"),
    (5000, "Professeur"),
]

def compute_level(pts):
    level = "Interne"
    for threshold, name in LEVELS:
        if pts >= threshold:
            level = name
    return level

def award_points(user, action, ref_type=None, ref_id=None):
    pts = POINTS_CONFIG.get(action, 0)
    if pts == 0:
        return
    log = PointsLog(user_id=user.id, action=action,
                    points=pts, ref_type=ref_type, ref_id=ref_id)
    user.total_points += pts
    user.level = compute_level(user.total_points)
    db.session.add(log)
    # Notifier l'utilisateur
    notif = Notification(
        user_id=user.id, type="points",
        message=f"+{pts} points pour : {action}",
        ref_type=ref_type, ref_id=ref_id
    )
    db.session.add(notif)
    db.session.commit()

