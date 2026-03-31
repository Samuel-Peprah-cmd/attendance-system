from datetime import datetime
from datetime import time as dt_time
from app.extensions import db

class School(db.Model):
    __tablename__ = "schools"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    api_key = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    country_prefix = db.Column(db.String(10), default='+233', nullable=False)
    latitude = db.Column(db.Float, nullable=False, server_default="0.0")
    longitude = db.Column(db.Float, nullable=False, server_default="0.0")
    radius_meters = db.Column(db.Integer, nullable=False, server_default="200")
    opening_time = db.Column(db.Time, default=dt_time(7, 30))  # 7:30 AM
    closing_time = db.Column(db.Time, default=dt_time(15, 0))  # 3:00 PM
    
    # Branding Fields
    logo_path = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(10), default="#2563eb") # Default Blue
    secondary_color = db.Column(db.String(10), default="#1e40af") 
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='school', lazy=True)
    students = db.relationship('Student', backref='school', lazy=True)
    class_rooms = db.relationship('ClassRoom', backref='school', lazy=True)








# from datetime import datetime
# from app.extensions import db

# class School(db.Model):
#     __tablename__ = "schools"
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(150), nullable=False)
#     slug = db.Column(db.String(150), unique=True, nullable=False)
#     api_key = db.Column(db.String(100), unique=True, nullable=False) # For the Kivy Scanner
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
#     students = db.relationship('Student', backref='school', lazy=True)