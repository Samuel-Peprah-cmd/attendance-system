from app.extensions import db
from datetime import datetime

class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    # 🚩 Identity Links (Single definition for each)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('staff.id'), nullable=True)
    
    student = db.relationship('Student', back_populates='attendance')
    staff = db.relationship('Staff', back_populates='attendance')
    
    remarks = db.Column(db.String(50), nullable=True, default="ON TIME")
    
    # 🚩 GPS Data (FIXED TYPO HERE)
    latitude = db.Column(db.Float, nullable=True) 
    longitude = db.Column(db.Float, nullable=True)
    is_within_boundary = db.Column(db.Boolean, default=True)
    
    # 🚩 Address Information
    street = db.Column(db.String(150), nullable=True)
    town = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    place_name = db.Column(db.String(255), nullable=True)
    
    participant_type = db.Column(db.String(20), nullable=False, server_default="student")
    status = db.Column(db.String(10), nullable=False) # 'IN' or 'OUT'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Attendance {self.id}: {self.participant_type} - {self.status}>"
    
    @property
    def resolved_name(self):
        """Automatically resolves the name for Reports and Dashboards"""
        if self.participant_type == 'staff' and self.staff:
            return self.staff.full_name
        if self.participant_type == 'student' and self.student:
            return self.student.full_name
        return "Unknown Identity"

@db.event.listens_for(Attendance, "before_delete")
def block_deletion(mapper, connection, target):
    raise RuntimeError("Security Policy Violation: Attendance logs cannot be deleted.")