from flask import Blueprint, request, jsonify
from models import db, Message, User
from sqlalchemy import or_

messages_bp = Blueprint("messages", __name__, url_prefix="/api/messages")


@messages_bp.post("/")
def send_message():
    d = request.get_json()
    msg = Message(
        sender_id   = d["sender_id"],
        receiver_id = d["receiver_id"],
        body        = d["body"]
    )
    db.session.add(msg)
    db.session.commit()
    return jsonify({"message": "Sent", "id": msg.id}), 201


@messages_bp.get("/conversation/<int:a>/<int:b>")
def conversation(a, b):
    msgs = Message.query.filter(
        or_(
            (Message.sender_id == a) & (Message.receiver_id == b),
            (Message.sender_id == b) & (Message.receiver_id == a),
        )
    ).order_by(Message.created_at.asc()).all()

    # Mark received messages as read
    for m in msgs:
        if m.receiver_id == a and not m.is_read:
            m.is_read = True
    db.session.commit()

    return jsonify([{
        "id":          m.id,
        "sender_id":   m.sender_id,
        "receiver_id": m.receiver_id,
        "body":        m.body,
        "is_read":     m.is_read,
        "created_at":  m.created_at.isoformat(),
    } for m in msgs])


@messages_bp.get("/inbox/<int:uid>")
def inbox(uid):
    """
    Return the last message per conversation for a given user.
    Fixed: no longer uses func.case() which is version-dependent.
    """
    # Fetch all messages involving this user, newest first
    all_msgs = Message.query.filter(
        or_(Message.sender_id == uid, Message.receiver_id == uid)
    ).order_by(Message.created_at.desc()).all()

    # Keep only the most recent message per peer (first occurrence = newest)
    seen    = {}
    ordered = []
    for m in all_msgs:
        peer_id = m.receiver_id if m.sender_id == uid else m.sender_id
        if peer_id not in seen:
            seen[peer_id] = m
            ordered.append(peer_id)

    result = []
    for peer_id in ordered:
        m    = seen[peer_id]
        peer = User.query.get(peer_id)
        unread = Message.query.filter_by(
            sender_id=peer_id, receiver_id=uid, is_read=False
        ).count()
        result.append({
            "peer":         peer.to_dict() if peer else {},
            "last_message": m.body,
            "last_time":    m.created_at.isoformat(),
            "unread_count": unread,
        })

    return jsonify(result)