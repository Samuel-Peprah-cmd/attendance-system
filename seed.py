from app import create_app
from app.extensions import db
from app.models.school import School
from app.models.user import User
from app.models.class_room import ClassRoom
from app.models.billing import Plan

def seed_database():
    app = create_app()
    with app.app_context():
        print("🚀 --- STARTING MASTER DATABASE SEED --- 🚀\n")

        # ==========================================
        # 1. CREATE MASTER SUPER ADMIN ACCOUNT
        # ==========================================
        print("🔹 Checking Master Account...")
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
            print("   ✅ MASTER ACCOUNT CREATED: ksapeprah@gmail.com")
        else:
            print("   👍 Master account already exists.")

        # ==========================================
        # 2. CREATE TEST SCHOOL, CLASS, & ADMIN
        # ==========================================
        print("\n🔹 Checking Test School & Admin...")
        school = School.query.filter_by(slug="atomdev-academy").first()
        if not school:
            school = School(name="AtomDev Academy", slug="atomdev-academy", api_key="test-key-123")
            db.session.add(school)
            db.session.commit()
            print("   ✅ Test School Created: AtomDev Academy")

        classroom = ClassRoom.query.filter_by(school_id=school.id, name="Grade 10").first()
        if not classroom:
            classroom = ClassRoom(name="Grade 10", school_id=school.id)
            db.session.add(classroom)
            db.session.commit()
            print("   ✅ Test Class Created: Grade 10")

        user = User.query.filter_by(email="skapeprah@gmail.com").first()
        if not user:
            user = User(email="skapeprah@gmail.com", school_id=school.id, role="admin")
            user.set_password("admin@12345") 
            db.session.add(user)
            db.session.commit()
            print("   ✅ Test Admin Created: skapeprah@gmail.com")
        else:
            print("   👍 Test school and admin already exist.")

        # ==========================================
        # 3. FIX MISSING BRANDING COLORS
        # ==========================================
        print("\n🔹 Verifying School Branding Colors...")
        schools = School.query.all()
        updated_colors = False
        for s in schools:
            if not s.secondary_color:
                s.secondary_color = "#1e40af"
                updated_colors = True
        
        if updated_colors:
            db.session.commit()
            print("   ✅ Updated missing secondary colors for schools.")
        else:
            print("   👍 All schools have secondary colors.")

        # ==========================================
        # 4. SEED SUBSCRIPTION PLANS
        # ==========================================
        print("\n🔹 Checking Billing Plans...")
        plans_data = [
            {
                "name": "Starter",
                "slug": "starter",
                "price_monthly": 100.0,
                "price_annual": 1000.0,
                "student_limit": 100,
                "admin_limit": 1,
                "scanner_limit": 1,
                "broadcast_limit": 0,
                "sms_enabled": True,
                "whatsapp_enabled": False,
                "gps_enabled": False,
                "advanced_analytics_enabled": False,
                "is_active": True # Ensuring it is active for the UI
            },
            {
                "name": "Growth",
                "slug": "growth",
                "price_monthly": 250.0,
                "price_annual": 2500.0,
                "student_limit": 500,
                "admin_limit": 3,
                "scanner_limit": 2,
                "broadcast_limit": 100,
                "sms_enabled": True,
                "whatsapp_enabled": False,
                "gps_enabled": False,
                "advanced_analytics_enabled": True,
                "is_active": True
            },
            {
                "name": "Premium",
                "slug": "premium",
                "price_monthly": 500.0,
                "price_annual": 5000.0,
                "student_limit": 2000,
                "admin_limit": 10,
                "scanner_limit": 5,
                "broadcast_limit": -1, # Unlimited
                "sms_enabled": True,
                "whatsapp_enabled": True,
                "gps_enabled": True,
                "advanced_analytics_enabled": True,
                "is_active": True
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "price_monthly": 1500.0,
                "price_annual": 15000.0,
                "student_limit": -1, # Unlimited
                "admin_limit": -1,
                "scanner_limit": -1,
                "broadcast_limit": -1,
                "sms_enabled": True,
                "whatsapp_enabled": True,
                "gps_enabled": True,
                "advanced_analytics_enabled": True,
                "custom_branding_enabled": True,
                "is_active": True
            }
        ]

        for data in plans_data:
            existing_plan = Plan.query.filter_by(slug=data['slug']).first()
            if existing_plan:
                print(f"   🔄 Updating existing plan: {data['name']}")
                for key, value in data.items():
                    setattr(existing_plan, key, value)
            else:
                print(f"   🌱 Creating new plan: {data['name']}")
                new_plan = Plan(**data)
                db.session.add(new_plan)
        
        db.session.commit()

        print("\n🎉 --- SEEDING COMPLETE! ALL SYSTEMS GO! --- 🎉")
        print("--------------------------------------------------")
        print("MASTER LOGIN: ksapeprah@gmail.com / AtomDevStudios2026")
        print("TEST ADMIN LOGIN: skapeprah@gmail.com / admin@12345")
        print("--------------------------------------------------")

if __name__ == "__main__":
    seed_database()