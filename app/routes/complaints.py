import uuid
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, abort, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models.user import User
from app.models.student import Student
from app.models.complaints import (
    ComplaintThread,
    ComplaintParticipant,
    ComplaintMessage,
    ComplaintAttachment,
)
from app.services.complaint_access import can_access_thread
from app.services.storage_helper import upload_file_to_r2
from werkzeug.utils import secure_filename

complaints_bp = Blueprint("complaints", __name__)


ALLOWED_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "webp",
    "pdf", "doc", "docx", "txt", "xlsx", "xls", "ppt", "pptx",
    "mp4", "mov", "avi", "webm", "mkv"
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

from flask import abort
from app.services.feature_gate_service import FeatureGateService


def ensure_complaints_enabled():
    if current_user.role == "super_admin":
        return

    if not getattr(current_user, "school_id", None):
        abort(403)

    if not FeatureGateService.can_use_feature(current_user.school_id, "complaints"):
        abort(403)

def detect_media_kind(filename):
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
        return "image"
    if ext in {"mp4", "mov", "avi", "webm", "mkv"}:
        return "video"
    return "document"


def serialize_attachment(att):
    return {
        "id": att.id,
        "file_name": att.file_name,
        "file_url": att.file_url,
        "mime_type": att.mime_type,
        "file_size": att.file_size,
        "media_kind": att.media_kind,
    }


def serialize_message(msg):
    return {
        "id": msg.id,
        "thread_id": msg.thread_id,
        "sender_id": msg.sender_id,
        "sender_email": msg.sender.email if msg.sender else "",
        "body": msg.body or "",
        "message_type": msg.message_type,
        "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "attachments": [serialize_attachment(a) for a in msg.attachments.order_by(ComplaintAttachment.id.asc()).all()],
    }


def build_thread_sidebar_item(thread, viewer_id):
    membership = ComplaintParticipant.query.filter_by(thread_id=thread.id, user_id=viewer_id).first()
    last_read_at = membership.last_read_at if membership else None

    last_message = thread.messages.order_by(ComplaintMessage.created_at.desc()).first()

    unread_count_query = ComplaintMessage.query.filter(
        ComplaintMessage.thread_id == thread.id,
        ComplaintMessage.sender_id != viewer_id,
        ComplaintMessage.is_deleted == False,
    )

    if last_read_at:
        unread_count_query = unread_count_query.filter(ComplaintMessage.created_at > last_read_at)

    unread_count = unread_count_query.count()

    if thread.thread_type == "parent_school":
        subtitle = f"{thread.student.full_name if thread.student else 'Student'} • {thread.school.name if thread.school else 'School'}"
    else:
        subtitle = f"{thread.school.name if thread.school else 'School'} • ATOM Gate Support"

    return {
        "id": thread.id,
        "subject": thread.subject,
        "subtitle": subtitle,
        "priority": thread.priority,
        "status": thread.status,
        "thread_type": thread.thread_type,
        "last_message_at": thread.last_message_at,
        "last_message_preview": (last_message.body[:80] + "...") if last_message and last_message.body and len(last_message.body) > 80 else (last_message.body if last_message else "No messages yet"),
        "unread_count": unread_count,
    }


@complaints_bp.route("/complaints")
@complaints_bp.route("/complaints/<int:thread_id>")
@login_required
def complaints_home(thread_id=None):
    ensure_complaints_enabled()
    memberships = ComplaintParticipant.query.filter_by(
        user_id=current_user.id,
        is_archived=False
    ).all()

    thread_ids = [m.thread_id for m in memberships]

    threads = []
    if thread_ids:
        threads = ComplaintThread.query.filter(
            ComplaintThread.id.in_(thread_ids)
        ).order_by(ComplaintThread.last_message_at.desc()).all()

    sidebar_threads = [build_thread_sidebar_item(t, current_user.id) for t in threads]

    selected_thread = None
    selected_messages = []
    children = []

    if current_user.role == "parent":
        children = Student.query.filter_by(
            guardian_one_email=current_user.email
        ).order_by(Student.full_name.asc()).all()

    if thread_id:
        selected_thread = ComplaintThread.query.get_or_404(thread_id)
        if not can_access_thread(current_user, selected_thread):
            abort(403)

        selected_messages = selected_thread.messages.order_by(ComplaintMessage.created_at.asc()).all()

        membership = ComplaintParticipant.query.filter_by(
            thread_id=selected_thread.id,
            user_id=current_user.id
        ).first()
        if membership:
            membership.last_read_at = datetime.utcnow()
            db.session.commit()

    return render_template(
        "complaints/index.html",
        threads=sidebar_threads,
        selected_thread=selected_thread,
        selected_messages=selected_messages,
        children=children,
    )


@complaints_bp.route("/parent/complaints/create", methods=["POST"])
@login_required
def create_parent_complaint():
    ensure_complaints_enabled()
    if current_user.role != "parent":
        abort(403)

    student_id = request.form.get("student_id", type=int)
    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("message") or "").strip()
    priority = (request.form.get("priority") or "normal").strip().lower()

    if not student_id or not subject or not body:
        return jsonify({"success": False, "message": "Student, subject, and message are required."}), 400

    student = Student.query.get_or_404(student_id)

    if student.guardian_one_email != current_user.email:
        return jsonify({"success": False, "message": "You cannot open a complaint for this child."}), 403

    thread = ComplaintThread(
        thread_type="parent_school",
        school_id=student.school_id,
        student_id=student.id,
        subject=subject,
        priority=priority,
        status="open",
        created_by_user_id=current_user.id,
        last_message_at=datetime.utcnow(),
    )
    db.session.add(thread)
    db.session.flush()

    db.session.add(ComplaintParticipant(
        thread_id=thread.id,
        user_id=current_user.id,
        role_in_thread="parent"
    ))

    school_admins = User.query.filter_by(role="school_admin", school_id=student.school_id).all()
    for admin in school_admins:
        db.session.add(ComplaintParticipant(
            thread_id=thread.id,
            user_id=admin.id,
            role_in_thread="school_admin"
        ))

    first_msg = ComplaintMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body=body,
        message_type="text",
    )
    db.session.add(first_msg)
    db.session.commit()

    return jsonify({
        "success": True,
        "thread_id": thread.id,
        "redirect_url": url_for("complaints.complaints_home", thread_id=thread.id)
    })


@complaints_bp.route("/school-admin/support/create", methods=["POST"])
@login_required
def create_school_support_thread():
    ensure_complaints_enabled()
    if current_user.role != "school_admin":
        abort(403)

    subject = (request.form.get("subject") or "").strip()
    body = (request.form.get("message") or "").strip()
    priority = (request.form.get("priority") or "normal").strip().lower()

    if not subject or not body:
        return jsonify({"success": False, "message": "Subject and message are required."}), 400

    thread = ComplaintThread(
        thread_type="school_support",
        school_id=current_user.school_id,
        student_id=None,
        subject=subject,
        priority=priority,
        status="open",
        created_by_user_id=current_user.id,
        last_message_at=datetime.utcnow(),
    )
    db.session.add(thread)
    db.session.flush()

    school_admins = User.query.filter_by(role="school_admin", school_id=current_user.school_id).all()
    for admin in school_admins:
        db.session.add(ComplaintParticipant(
            thread_id=thread.id,
            user_id=admin.id,
            role_in_thread="school_admin"
        ))

    super_admins = User.query.filter_by(role="super_admin").all()
    for sa in super_admins:
        db.session.add(ComplaintParticipant(
            thread_id=thread.id,
            user_id=sa.id,
            role_in_thread="super_admin"
        ))

    first_msg = ComplaintMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body=body,
        message_type="text",
    )
    db.session.add(first_msg)
    db.session.commit()

    return jsonify({
        "success": True,
        "thread_id": thread.id,
        "redirect_url": url_for("complaints.complaints_home", thread_id=thread.id)
    })


@complaints_bp.route("/complaints/<int:thread_id>/send", methods=["POST"])
@login_required
def send_complaint_message(thread_id):
    ensure_complaints_enabled()
    thread = ComplaintThread.query.get_or_404(thread_id)

    if not can_access_thread(current_user, thread):
        abort(403)

    body = (request.form.get("body") or "").strip()
    if not body:
        return jsonify({"success": False, "message": "Message cannot be empty."}), 400

    msg = ComplaintMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body=body,
        message_type="text"
    )
    db.session.add(msg)
    thread.last_message_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": serialize_message(msg)
    })


@complaints_bp.route("/complaints/<int:thread_id>/upload", methods=["POST"])
@login_required
def upload_complaint_attachment(thread_id):
    ensure_complaints_enabled()
    thread = ComplaintThread.query.get_or_404(thread_id)

    if not can_access_thread(current_user, thread):
        abort(403)

    uploaded_file = request.files.get("file")
    caption = (request.form.get("caption") or "").strip()

    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"success": False, "message": "No file selected."}), 400

    if not allowed_file(uploaded_file.filename):
        return jsonify({"success": False, "message": "File type not allowed."}), 400

    clean_name = secure_filename(uploaded_file.filename)
    key = f"complaints/{thread.school_id}/{thread.id}/{uuid.uuid4().hex}_{clean_name}"

    file_bytes = uploaded_file.read()
    file_url = upload_file_to_r2(file_bytes, key, content_type=uploaded_file.mimetype)

    if not file_url:
        return jsonify({"success": False, "message": "Upload failed."}), 500

    msg = ComplaintMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        body=caption or None,
        message_type="file"
    )
    db.session.add(msg)
    db.session.flush()

    attachment = ComplaintAttachment(
        message_id=msg.id,
        file_name=clean_name,
        file_url=file_url,
        mime_type=uploaded_file.mimetype,
        file_size=len(file_bytes),
        media_kind=detect_media_kind(clean_name),
    )
    db.session.add(attachment)

    thread.last_message_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": serialize_message(msg)
    })


@complaints_bp.route("/complaints/<int:thread_id>/mark-read", methods=["POST"])
@login_required
def mark_complaint_read(thread_id):
    ensure_complaints_enabled()
    thread = ComplaintThread.query.get_or_404(thread_id)

    if not can_access_thread(current_user, thread):
        abort(403)

    membership = ComplaintParticipant.query.filter_by(
        thread_id=thread.id,
        user_id=current_user.id
    ).first()

    if membership:
        membership.last_read_at = datetime.utcnow()
        db.session.commit()

    return jsonify({"success": True})


@complaints_bp.route("/complaints/<int:thread_id>/status", methods=["POST"])
@login_required
def update_thread_status(thread_id):
    ensure_complaints_enabled()
    thread = ComplaintThread.query.get_or_404(thread_id)

    if not can_access_thread(current_user, thread):
        abort(403)

    if current_user.role not in {"school_admin", "super_admin"}:
        abort(403)

    new_status = (request.form.get("status") or "").strip().lower()
    if new_status not in {"open", "pending", "resolved", "closed"}:
        return jsonify({"success": False, "message": "Invalid status."}), 400

    thread.status = new_status
    thread.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"success": True, "status": thread.status})