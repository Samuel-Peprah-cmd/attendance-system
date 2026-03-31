from app.extensions import db

class ClassRoom(db.Model):
    __tablename__ = "class_rooms"
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False) # e.g., "Grade 10A"
    # students = db.relationship('Student', backref='classroom', lazy=True)
    students = db.relationship('Student', back_populates='student_class')