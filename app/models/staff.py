# app/models/staff.py
from app.extensions import db
from datetime import datetime

class Staff(db.Model):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    staff_code = db.Column(db.String(20), unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    designation = db.Column(db.String(50)) # e.g., 'Senior Housemaster', 'Teacher'
    photo_path = db.Column(db.String(255))
    qr_token = db.Column(db.String(100), unique=True)
    is_active = db.Column(db.Boolean, default=True)
    is_within_boundary = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    school = db.relationship('School', backref='staff_members')
    attendance = db.relationship('Attendance', back_populates='staff', lazy=True)