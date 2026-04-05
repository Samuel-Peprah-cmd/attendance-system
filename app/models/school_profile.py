from datetime import datetime
from app.extensions import db

class SchoolProfile(db.Model):
    __tablename__ = "school_profiles"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("schools.id"), nullable=False, unique=True)

    # Primary contact details
    email_primary = db.Column(db.String(150), nullable=True)
    email_secondary = db.Column(db.String(150), nullable=True)

    phone_primary = db.Column(db.String(30), nullable=True)
    phone_secondary = db.Column(db.String(30), nullable=True)

    website = db.Column(db.String(255), nullable=True)

    # Structured address
    address_line_1 = db.Column(db.String(255), nullable=True)
    address_line_2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    region_state = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True, default="Ghana")

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    school = db.relationship("School", backref=db.backref("profile", uselist=False))

    @property
    def full_address(self):
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.region_state,
            self.postal_code,
            self.country,
        ]
        return ", ".join([p for p in parts if p])