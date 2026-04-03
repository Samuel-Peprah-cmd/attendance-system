from datetime import datetime
from app.extensions import db

class BillingAuditLog(db.Model):
    __tablename__ = 'billing_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id')) # Who did it?
    action = db.Column(db.String(100)) # 'manual_upgrade', 'grace_period_extended'
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)