from app.extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="school_admin")

    students = db.relationship(
        'Student',
        primaryjoin="User.email == Student.guardian_one_email",
        foreign_keys="Student.guardian_one_email",
        backref='parent_user',
        viewonly=True
    )

    passkeys = db.relationship(
        "UserPasskey",
        backref="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    def is_super_admin(self):
        return self.role == 'super_admin'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserPasskey(db.Model):
    __tablename__ = "user_passkeys"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    credential_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    public_key = db.Column(db.Text, nullable=False)
    sign_count = db.Column(db.Integer, default=0)

    transports = db.Column(db.Text, nullable=True)
    device_name = db.Column(db.String(120), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)








# from app.extensions import db, login_manager
# from flask_login import UserMixin
# from werkzeug.security import generate_password_hash, check_password_hash

# @login_manager.user_loader
# def load_user(user_id):
#     return User.query.get(int(user_id))

# class User(UserMixin, db.Model):
#     __tablename__ = "users"
#     id = db.Column(db.Integer, primary_key=True)
#     role = db.Column(db.String(20), default="school_admin")
#     # Change nullable to True so Super Admins don't need a school_id
#     school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True) 
#     email = db.Column(db.String(150), unique=True, nullable=False)
#     password_hash = db.Column(db.String(256), nullable=False)
#     role = db.Column(db.String(20), default="school_admin")
#     webauthn_id = db.Column(db.String(255), nullable=True)
#     webauthn_public_key = db.Column(db.Text, nullable=True)
#     webauthn_sign_count = db.Column(db.Integer, default=0)

#     def is_super_admin(self):
#         return self.role == 'super_admin'
    
#     def set_password(self, password):
#         self.password_hash = generate_password_hash(password)

#     def check_password(self, password):
#         return check_password_hash(self.password_hash, password)
    
#     students = db.relationship(
#         'Student',
#         primaryjoin="User.email == Student.guardian_one_email",
#         foreign_keys="Student.guardian_one_email",
#         backref='parent_user',
#         viewonly=True # This ensures we don't accidentally delete kids if we delete a user
#     )
