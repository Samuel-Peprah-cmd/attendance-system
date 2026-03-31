from app.extensions import db
from datetime import datetime

class SchoolNotice(db.Model):
    __tablename__ = 'school_notices' # Good practice to name the table explicitly
    id = db.Column(db.Integer, primary_key=True)
    
    # FIX: Point to 'schools.id' (plural) to match your School model
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Optional: Relationship for easier access in templates
    school = db.relationship('School', backref='notices')

    def __repr__(self):
        return f"<Notice {self.title[:20]}... for School {self.school_id}>"