from app.extensions import db
from datetime import datetime

class Coupon(db.Model):
    __tablename__ = 'coupons'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False) # e.g., 'ATOM50'
    discount_percentage = db.Column(db.Float, default=0.0) # e.g., 50.0 for 50% off
    is_active = db.Column(db.Boolean, default=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    usage_limit = db.Column(db.Integer, default=-1) # -1 means unlimited
    times_used = db.Column(db.Integer, default=0)