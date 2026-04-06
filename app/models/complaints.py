from datetime import datetime
from app.extensions import db


class ComplaintThread(db.Model):
    __tablename__ = "complaint_threads"

    id = db.Column(db.Integer, primary_key=True)

    # parent_school  -> parent(s) <-> school admins
    # school_support -> school admins <-> super admin
    thread_type = db.Column(db.String(30), nullable=False, index=True)

    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True, index=True)

    subject = db.Column(db.String(255), nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="normal")  # low, normal, high, urgent
    status = db.Column(db.String(20), nullable=False, default="open")      # open, pending, resolved, closed

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school = db.relationship("School", backref=db.backref("complaint_threads", lazy="dynamic"))
    student = db.relationship("Student", backref=db.backref("complaint_threads", lazy="dynamic"))
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])

    participants = db.relationship(
        "ComplaintParticipant",
        backref="thread",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    messages = db.relationship(
        "ComplaintMessage",
        backref="thread",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )


class ComplaintParticipant(db.Model):
    __tablename__ = "complaint_participants"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("complaint_threads.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    role_in_thread = db.Column(db.String(30), nullable=False)  # parent, school_admin, super_admin
    is_archived = db.Column(db.Boolean, default=False)
    last_read_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref=db.backref("complaint_memberships", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("thread_id", "user_id", name="uq_complaint_thread_user"),
    )


class ComplaintMessage(db.Model):
    __tablename__ = "complaint_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("complaint_threads.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    body = db.Column(db.Text, nullable=True)
    message_type = db.Column(db.String(20), nullable=False, default="text")  # text, file, system
    reply_to_id = db.Column(db.Integer, db.ForeignKey("complaint_messages.id"), nullable=True)

    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    edited_at = db.Column(db.DateTime, nullable=True)

    sender = db.relationship("User", foreign_keys=[sender_id])
    reply_to = db.relationship("ComplaintMessage", remote_side=[id])

    attachments = db.relationship(
        "ComplaintAttachment",
        backref="message",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="ComplaintAttachment.id.asc()"
    )


class ComplaintAttachment(db.Model):
    __tablename__ = "complaint_attachments"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("complaint_messages.id"), nullable=False, index=True)

    file_name = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(120), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    media_kind = db.Column(db.String(20), nullable=False)  # image, video, document

    created_at = db.Column(db.DateTime, default=datetime.utcnow)