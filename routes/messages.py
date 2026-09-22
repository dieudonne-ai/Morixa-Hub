from flask import Blueprint, request, jsonify, g
from models import db, Message, User, Notification
from sqlalchemy import or_
from utils.auth import require_auth
from utils.security import clean_str, require_json, rate_limit

messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")

MAX_BODY = 4000


def _msg_dict(m, my_id):
    return {
        "id":          m.id,
        "sender_id":   m.sender_id,
        "receiver_id": m.receiver_id,
        "body":        m.body,
        "is_read":     m.is_read,
        "is_mine":     m.sender_id == my_id,
        "created_at":  m.created_at.isoformat(),
    }


@messages_bp.post("/")
@require_auth
@rate_limit(max_calls=30, window_seconds=60, key_prefix="msg_send")
def send_message():
    d, err = require_json(["receiver_id", "body"])
    if err:
        return err

    receiver_id = int(d["receiver_id"])
    body = clean_str(d["body"], MAX_BODY)

    if receiver_id == g.user_id:
        return jsonify({"error": "You cannot message yourself"}), 400
    if not User.query.get(receiver_id):
        return jsonify({"error": "Recipient not found"}), 404

    msg = Message(sender_id=g.user_id, receiver_id=receiver_id, body=body)
    db.session.add(msg)
    db.session.flush()

    # Notification + points pour le destinataire/émetteur
    db.session.add(Notification(
        user_id=receiver_id,
        type="message",
        message=f"<strong>Dr. {g.user.full_name}</strong> sent you a message.",
        ref_type="user", ref_id=g.user_id,
    ))

    from services.points import award_points
    award_points(g.user, "message_envoye", ref_type="message", ref_id=msg.id)

    db.session.commit()
    return jsonify({"message": "Sent", "id": msg.id}), 201


@messages_bp.get("/conversation/<int:peer_id>")
@require_auth
def conversation(peer_id):
    """Messages entre l'utilisateur connecté et peer_id (paginé, marque comme lus)."""
    page     = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 100)

    q = Message.query.filter(
        or_(
            (Message.sender_id == g.user_id) & (Message.receiver_id == peer_id),
            (Message.sender_id == peer_id) & (Message.receiver_id == g.user_id),
        )
    ).order_by(Message.created_at.desc())

    p = q.paginate(page=page, per_page=per_page, error_out=False)

    # Marque comme lus les messages reçus (à la consultation)
    Message.query.filter_by(sender_id=peer_id, receiver_id=g.user_id, is_read=False)\
                 .update({"is_read": True}, synchronize_session=False)
    db.session.commit()

    msgs = list(reversed(p.items))
    return jsonify({
        "messages": [_msg_dict(m, g.user_id) for m in msgs],
        "total":    p.total,
        "pages":    p.pages,
        "peer":     User.query.get(peer_id).to_dict() if User.query.get(peer_id) else None,
    })


@messages_bp.get("/poll/<int:peer_id>")
@require_auth
def poll(peer_id):
    """Retourne uniquement les messages plus récents que after_id (temps réel léger)."""
    after_id = request.args.get("after_id", 0, type=int)
    msgs = Message.query.filter(
        or_(
            (Message.sender_id == peer_id) & (Message.receiver_id == g.user_id),
            (Message.sender_id == g.user_id) & (Message.receiver_id == peer_id),
        ),
        Message.id > after_id,
    ).order_by(Message.created_at.asc()).all()

    # Marque comme lus les nouveaux messages reçus
    for m in msgs:
        if m.receiver_id == g.user_id and not m.is_read:
            m.is_read = True
    db.session.commit()

    return jsonify([_msg_dict(m, g.user_id) for m in msgs])


@messages_bp.get("/inbox")
@require_auth
def inbox():
    """Dernière conversation par correspondant + compteurs de non-lus."""
    all_msgs = Message.query.filter(
        or_(Message.sender_id == g.user_id, Message.receiver_id == g.user_id)
    ).order_by(Message.created_at.desc()).all()

    seen, ordered = {}, []
    for m in all_msgs:
        peer_id = m.receiver_id if m.sender_id == g.user_id else m.sender_id
        if peer_id not in seen:
            seen[peer_id] = m
            ordered.append(peer_id)

    result = []
    for peer_id in ordered:
        m    = seen[peer_id]
        peer = db.session.get(User, peer_id)
        unread = Message.query.filter_by(
            sender_id=peer_id, receiver_id=g.user_id, is_read=False
        ).count()
        result.append({
            "peer":         peer.to_dict() if peer else {},
            "last_message": m.body[:100],
            "last_time":    m.created_at.isoformat(),
            "unread_count": unread,
        })
    return jsonify(result)


@messages_bp.get("/unread-summary")
@require_auth
def unread_summary():
    total = Message.query.filter_by(receiver_id=g.user_id, is_read=False).count()
    return jsonify({"unread": total})


@messages_bp.post("/read/<int:peer_id>")
@require_auth
def mark_read(peer_id):
    Message.query.filter_by(sender_id=peer_id, receiver_id=g.user_id, is_read=False)\
                 .update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"message": "Marked as read"})


@messages_bp.delete("/<int:mid>")
@require_auth
def delete_message(mid):
    """Seul l'émetteur peut supprimer son message."""
    m = Message.query.get_or_404(mid)
    if m.sender_id != g.user_id:
        return jsonify({"error": "Not authorized"}), 403
    db.session.delete(m)
    db.session.commit()
    return jsonify({"message": "Message deleted"})