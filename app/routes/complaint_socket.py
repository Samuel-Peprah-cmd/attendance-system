from datetime import datetime

from flask_login import current_user
from flask_socketio import emit, join_room

from app.extensions import socketio, db
from app.models.complaints import ComplaintThread, ComplaintMessage, ComplaintParticipant
from app.services.complaint_access import can_access_thread


def socket_serialize_message(msg):
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_email": msg.sender.email if msg.sender else "",
        "body": msg.body or "",
        "message_type": msg.message_type,
        "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "file_url": a.file_url,
                "mime_type": a.mime_type,
                "file_size": a.file_size,
                "media_kind": a.media_kind,
            }
            for a in msg.attachments.all()
        ],
    }


@socketio.on("join_complaint_thread")
def join_complaint_thread(data):
    if not current_user.is_authenticated:
        emit("complaint_error", {"message": "Authentication required."})
        return

    thread_id = data.get("thread_id")
    thread = ComplaintThread.query.get(thread_id)

    if not thread or not can_access_thread(current_user, thread):
        emit("complaint_error", {"message": "Access denied."})
        return

    join_room(f"complaint_{thread.id}")
    emit("joined_thread", {"thread_id": thread.id})


@socketio.on("send_complaint_message")
def send_complaint_message(data):
    if not current_user.is_authenticated:
        emit("complaint_error", {"message": "Authentication required."})
        return

    thread_id = data.get("thread_id")
    body = (data.get("body") or "").strip()

    thread = ComplaintThread.query.get(thread_id)
    if not thread or not can_access_thread(current_user, thread):
        emit("complaint_error", {"message": "Access denied."})
        return

    if not body:
        emit("complaint_error", {"message": "Message cannot be empty."})
        return

    msg = ComplaintMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body=body,
        message_type="text"
    )
    db.session.add(msg)
    thread.last_message_at = datetime.utcnow()
    db.session.commit()

    emit("new_complaint_message", socket_serialize_message(msg), room=f"complaint_{thread.id}")


@socketio.on("complaint_typing")
def complaint_typing(data):
    if not current_user.is_authenticated:
        return

    thread_id = data.get("thread_id")
    thread = ComplaintThread.query.get(thread_id)

    if not thread or not can_access_thread(current_user, thread):
        return

    emit(
        "complaint_typing_indicator",
        {
            "thread_id": thread.id,
            "user_id": current_user.id,
            "sender_email": current_user.email,
        },
        room=f"complaint_{thread.id}",
        include_self=False
    )


@socketio.on("mark_complaint_read")
def mark_complaint_read_socket(data):
    if not current_user.is_authenticated:
        return

    thread_id = data.get("thread_id")
    thread = ComplaintThread.query.get(thread_id)

    if not thread or not can_access_thread(current_user, thread):
        return

    membership = ComplaintParticipant.query.filter_by(
        thread_id=thread.id,
        user_id=current_user.id
    ).first()

    if membership:
        membership.last_read_at = datetime.utcnow()
        db.session.commit()