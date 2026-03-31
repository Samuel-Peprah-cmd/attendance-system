from app.extensions import db
from datetime import datetime
import secrets
from app.models.school import School

class ScannerDevice(db.Model):
    __tablename__ = 'scanner_devices'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    device_name = db.Column(db.String(100), nullable=False) # e.g., "Main Gate Tablet"
    device_code = db.Column(db.String(50), unique=True, nullable=False) # Unique ID for the app
    api_key = db.Column(db.String(100), unique=True, nullable=False)
    location_name = db.Column(db.String(100)) # e.g., "North Entry"
    is_active = db.Column(db.Boolean, default=True)
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    school = db.relationship('School', backref='devices')

    def __init__(self, **kwargs):
        super(ScannerDevice, self).__init__(**kwargs)
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(32)

    def update_last_seen(self):
        self.last_seen_at = datetime.utcnow()
        db.session.commit()