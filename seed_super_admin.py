from app import create_app
from app.extensions import db
from app.models.user import User

app = create_app()
with app.app_context():
    # Create the Master Account for AtomDev Studios
    master = User.query.filter_by(email="ksapeprah@gmail.com").first()
    if not master:
        master = User(
            email="ksapeprah@gmail.com", 
            role="super_admin",
            school_id=None # Super Admins have no school_id
        )
        master.set_password("AtomDevStudios2026") # Use a very strong password
        db.session.add(master)
        db.session.commit()
        print("MASTER ACCOUNT CREATED: ksapeprah@gmail.com")
    else:
        print("Master account already exists.")