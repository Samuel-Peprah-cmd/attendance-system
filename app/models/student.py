from app.extensions import db
import uuid

class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    class_room_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True)
    
    # Core Info
    student_code = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20))
    
    # Guardian 1 (Primary)
    guardian_one_name = db.Column(db.String(150), nullable=False)
    guardian_one_phone = db.Column(db.String(20), nullable=False)
    guardian_one_email = db.Column(db.String(150), nullable=False)
    guardian_one_relation = db.Column(db.String(50)) # e.g., Mother
    
    # Guardian 2 (Secondary/Emergency)
    guardian_two_name = db.Column(db.String(150))
    guardian_two_phone = db.Column(db.String(20))
    guardian_two_relation = db.Column(db.String(50)) # e.g., Father / Uncle

    # Safety & Medical
    blood_group = db.Column(db.String(5))
    medical_notes = db.Column(db.Text) # Allergies or conditions
    
    # System Data
    qr_token = db.Column(db.String(100), unique=True, nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    current_session = db.Column(db.String(20), default="2026-2027")
    
    # student_class = db.relationship('ClassRoom', backref='students_list')
    student_class = db.relationship('ClassRoom', back_populates='students')
    
    # attendance = db.relationship('Attendance', backref='student', lazy=True)
    attendance = db.relationship('Attendance', back_populates='student', lazy=True)