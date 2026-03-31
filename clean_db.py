from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        # Combining them into one command makes it blazing fast.
        # CASCADE ensures any dependent tables (like attendance or users) are also cleared.
        # Note: Change 'staff' to 'staffs' if that is your exact database table name!
        db.session.execute(text("TRUNCATE TABLE students, staff, schools RESTART IDENTITY CASCADE;"))
        db.session.commit()
        
        print("---------------------------------------------------------")
        print("🛑 SUCCESS: Database wiped clean!")
        print("Cleared: Students, Staff, and Schools.")
        print("Note: CASCADE also cleared related Attendance, Users, etc.")
        print("---------------------------------------------------------")
        print("🛠️  Next step: Run 'flask db upgrade' in your terminal.")
        print("---------------------------------------------------------")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error: {e}")
        print("Hint: If it says a table doesn't exist, double-check if your table is named 'staff' or 'staffs', and 'school' or 'schools'.")