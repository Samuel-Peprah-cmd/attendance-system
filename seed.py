from app import create_app
from app.extensions import db
from app.models.school import School
from app.models.user import User
from app.models.class_room import ClassRoom

app = create_app()
with app.app_context():
    # 1. Create a Test School
    school = School.query.filter_by(slug="atomdev-academy").first()
    if not school:
        school = School(name="AtomDev Academy", slug="atomdev-academy", api_key="test-key-123")
        db.session.add(school)
        db.session.commit()

    # 2. Create a Test Class
    classroom = ClassRoom.query.filter_by(school_id=school.id, name="Grade 10").first()
    if not classroom:
        classroom = ClassRoom(name="Grade 10", school_id=school.id)
        db.session.add(classroom)
        db.session.commit()

    # 3. Create an Admin User
    user = User.query.filter_by(email="skapeprah@gmail.com").first()
    if not user:
        user = User(email="skapeprah@gmail.com", school_id=school.id)
        user.set_password("admin@12345") 
        db.session.add(user)
        db.session.commit()
    
    print("------------------------------------------")
    print("SUCCESS: AtomDev Studios Database Ready!")
    print("Login: skapeprah@gmail.com / Password: admin@12345")
    print("------------------------------------------")
    
with app.app_context():
    from app.models.school import School
    schools = School.query.all()
    for s in schools:
        if not s.secondary_color:
            s.secondary_color = "#1e40af"
    db.session.commit()