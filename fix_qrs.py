import os
import qrcode
from app import create_app
from app.extensions import db
from app.models.staff import Staff
from app.models.student import Student

app = create_app()
with app.app_context():
    qr_dir = os.path.join(app.root_path, 'static', 'qr_codes')
    os.makedirs(qr_dir, exist_ok=True)

    # Fix Staff
    for s in Staff.query.all():
        path = os.path.join(qr_dir, f"qr_{s.qr_token}.png")
        if not os.path.exists(path):
            qrcode.make(s.qr_token).save(path)
            print(f"✅ Generated QR for Staff: {s.full_name}")

    # Fix Students
    for s in Student.query.all():
        path = os.path.join(qr_dir, f"qr_{s.qr_token}.png")
        if not os.path.exists(path):
            qrcode.make(s.qr_token).save(path)
            print(f"✅ Generated QR for Student: {s.full_name}")