import os
import csv
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models.attendance import Attendance
from app.models.school import School

def run_backup():
    app = create_app()
    with app.app_context():
        # 1. Setup Backup Directory
        today_str = datetime.now().strftime('%Y-%m-%d')
        backup_dir = os.path.join(app.root_path, '..', 'backups', today_str)
        os.makedirs(backup_dir, exist_ok=True)

        print(f"📦 Starting Backup for {today_str}...")

        # 2. Export Logs per School (Audit-Friendly CSV)
        schools = School.query.all()
        for school in schools:
            logs = Attendance.query.filter_by(school_id=school.id).all()
            
            filename = f"{school.name.replace(' ', '_')}_audit_log.csv"
            filepath = os.path.join(backup_dir, filename)

            with open(filepath, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Timestamp', 'Student Name', 'ID Code', 'Status', 'Location'])
                
                for log in logs:
                    writer.writerow([
                        log.timestamp,
                        log.student.full_name,
                        log.student.student_code,
                        log.status,
                        log.device.location_name if log.device else 'Web Terminal'
                    ])
            
            print(f"✅ Exported {len(logs)} records for {school.name}")

        print(f"🚀 Backup Complete. Files stored in: {backup_dir}")

if __name__ == "__main__":
    run_backup()