from datetime import datetime
from app.extensions import db

class Broadcast(db.Model):
    __tablename__ = "broadcasts"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    subject = db.Column(db.String(255), nullable=False)
    message_html = db.Column(db.Text, nullable=False)
    
    # Channels
    channel_email = db.Column(db.Boolean, default=False)
    channel_sms = db.Column(db.Boolean, default=False)
    channel_whatsapp = db.Column(db.Boolean, default=False)

    target_audience = db.Column(db.String(50), nullable=False) # 'all_parents', 'all_staff', etc.
    status = db.Column(db.String(30), nullable=False, default="draft") # draft, queued, sending, completed

    total_recipients = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    attachments = db.relationship("BroadcastAttachment", backref="broadcast", lazy=True, cascade="all, delete-orphan")
    recipients = db.relationship("BroadcastRecipient", backref="broadcast", lazy=True, cascade="all, delete-orphan")


class BroadcastAttachment(db.Model):
    __tablename__ = "broadcast_attachments"

    id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(db.Integer, db.ForeignKey("broadcasts.id"), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False)

    original_name = db.Column(db.String(255), nullable=False)
    file_url = db.Column(db.Text, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class BroadcastRecipient(db.Model):
    __tablename__ = "broadcast_recipients"

    id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(db.Integer, db.ForeignKey("broadcasts.id"), nullable=False)
    
    recipient_type = db.Column(db.String(30), nullable=False) # 'guardian', 'staff'
    name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(30), nullable=True)

    status = db.Column(db.String(30), default="pending") # pending, sent, failed