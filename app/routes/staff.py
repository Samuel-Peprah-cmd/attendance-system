from datetime import datetime, time, timedelta
import os
import io
import uuid
import qrcode
import threading
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from app.extensions import db, limiter
from app.models.staff import Staff
from app.models.attendance import Attendance
from math import radians, cos, sin, asin, sqrt
from app.services.storage_helper import upload_file_to_r2

staff_bp = Blueprint("staff", __name__, url_prefix="/staff")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@staff_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_staff():
    if request.method == 'POST':
        # file = request.files.get('photo')
        # photo_filename = "default_avatar.png"

        # if file and allowed_file(file.filename):
        #     ext = file.filename.rsplit('.', 1)[1].lower()
        #     photo_filename = f"{uuid.uuid4().hex}.{ext}"
        #     upload_path = os.path.join(current_app.root_path, 'static', 'uploads', 'staff', photo_filename)
        #     os.makedirs(os.path.dirname(upload_path), exist_ok=True)
        #     file.save(upload_path)
        
        # try:
        #     # Generate Unique Security Token
        #     qr_token = str(uuid.uuid4().hex[:12]).upper()
            
        #     # 🚩 GENERATE PHYSICAL QR FILE FOR ID CARD
        #     qr_dir = os.path.join(current_app.root_path, 'static', 'qr_codes')
        #     os.makedirs(qr_dir, exist_ok=True)
        #     qr_path = os.path.join(qr_dir, f"qr_{qr_token}.png")
            
        #     qr_img = qrcode.make(qr_token)
        #     qr_img.save(qr_path)
        staff_code = request.form.get('staff_code')
        email = request.form.get('email')

        # 🚨 THE PRE-CHECK: Look before we leap!
        if Staff.query.filter_by(staff_code=staff_code).first():
            flash(f"Error: The Staff Code '{staff_code}' is already registered.", "danger")
            return render_template('staff/staff_register.html')
            
        if Staff.query.filter_by(email=email).first():
            flash(f"Error: The Email '{email}' is already in use.", "danger")
            return render_template('staff/staff_register.html')
        
        file = request.files.get('photo')
        photo_url = None

        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"staff/{uuid.uuid4().hex}.{ext}"
            
            # Read into memory and upload
            file_bytes = file.read()
            photo_url = upload_file_to_r2(file_bytes, photo_filename, content_type=file.mimetype)
        
        try:
            # --- 2. GENERATE & UPLOAD QR CODE TO R2 ---
            qr_token = str(uuid.uuid4().hex[:12]).upper()
            
            qr_img = qrcode.make(qr_token)
            img_bytes = io.BytesIO()
            qr_img.save(img_bytes, format='PNG')
            
            qr_filename = f"qr_codes/staff_qr_{qr_token}.png"
            upload_file_to_r2(img_bytes.getvalue(), qr_filename, content_type="image/png")

            new_staff = Staff(
                school_id=current_user.school_id,
                staff_code=request.form.get('staff_code'),
                full_name=request.form.get('full_name'),
                designation=request.form.get('designation'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                photo_path=photo_url,
                qr_token=qr_token
            )
            
            db.session.add(new_staff)
            db.session.commit()
            
            flash(f"Personnel {new_staff.full_name} onboarded successfully.", "success")
            return redirect(url_for('staff.print_card', staff_id=new_staff.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"System Error: {str(e)}", "danger")

    return render_template('staff/staff_register.html')

@staff_bp.route('/print/<int:staff_id>')
@login_required
def print_card(staff_id):
    staff = Staff.query.filter_by(id=staff_id, school_id=current_user.school_id).first_or_404()

    today = datetime.utcnow()
    issued_date = today.strftime("%d %b %Y")
    expiry_date = (today + timedelta(days=365)).strftime("%d %b %Y")
    session_text = f"{today.year}/{today.year + 1}"

    return render_template(
        'staff/print_id.html',
        staff=staff,
        issued_date=issued_date,
        expiry_date=expiry_date,
        session_text=session_text
    )

@staff_bp.route('/list')
@login_required
def list_staff():
    staff_members = Staff.query.filter_by(school_id=current_user.school_id).order_by(Staff.created_at.desc()).all()
    return render_template('staff/staff_list.html', staff_members=staff_members)

@staff_bp.route('/toggle/<int:staff_id>', methods=['POST'])
@login_required
def toggle_status(staff_id):
    staff = Staff.query.filter_by(id=staff_id, school_id=current_user.school_id).first_or_404()
    staff.is_active = not staff.is_active
    db.session.commit()
    
    status_text = "activated" if staff.is_active else "revoked"
    flash(f"Access for {staff.full_name} has been {status_text}.", "success")
    return redirect(url_for('staff.list_staff'))

@staff_bp.route('/security-monitor')
@login_required
@limiter.limit("1000 per hour") # 🚩 Raise limit for the dashboard
def security_dashboard():
    # Initial load of logs
    logs = Attendance.query.filter_by(school_id=current_user.school_id)\
           .order_by(Attendance.timestamp.desc()).limit(20).all()
    return render_template('dashboard/security_dashboard.html', logs=logs, config=current_app.config)

@staff_bp.route('/api/security-data')
@login_required
def security_data_api():
    """Returns only JSON data to avoid full page reloads"""
    logs = Attendance.query.filter_by(school_id=current_user.school_id)\
           .order_by(Attendance.timestamp.desc()).limit(20).all()
    
    return jsonify([{
        'name': log.resolved_name,
        'lat': float(log.latitude) if log.latitude else None,
        'lng': float(log.longitude) if log.longitude else None,
        'status': log.status,
        'is_safe': log.is_within_boundary,
        'time': log.timestamp.strftime('%I:%M %p'),
        'place': log.place_name or "Campus Node"
    } for log in logs])

# @staff_bp.route('/reports')
# @login_required
# def attendance_report():
#     school_id = current_user.school_id
    
#     # 1. Date Filters
#     start_date_str = request.args.get('start_date')
#     end_date_str = request.args.get('end_date')
    
#     if start_date_str:
#         start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
#     else:
#         start_date = datetime.utcnow() - timedelta(days=30)
        
#     if end_date_str:
#         end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
#     else:
#         end_date = datetime.utcnow()

#     # 2. 🚩 FIXED: Query Attendance for logs, filtering by participant_type
#     logs = Attendance.query.filter(
#         Attendance.school_id == school_id,
#         Attendance.participant_type == 'staff',
#         Attendance.timestamp >= start_date,
#         Attendance.timestamp <= end_date + timedelta(days=1)
#     ).order_by(Attendance.timestamp.desc()).all()

#     # 3. Analytics Logic
#     late_threshold = time(8, 0) # 8:00 AM
#     total_scans = len(logs)
    
#     # Using safety checks for timestamps
#     late_count = len([l for l in logs if l.status == 'IN' and l.timestamp and l.timestamp.time() > late_threshold])
#     violation_count = len([l for l in logs if not l.is_within_boundary])

#     return render_template(
#         'staff/reports.html',
#         logs=logs,
#         start_date=start_date.strftime('%Y-%m-%d'),
#         end_date=end_date.strftime('%Y-%m-%d'),
#         total_scans=total_scans,
#         late_count=late_count,
#         violation_count=violation_count
#     )

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points on the earth."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r * 1000 # Return meters

@staff_bp.route('/reports')
@login_required
def attendance_report():
    school = current_user.school
    
    # 1. DATE FILTERS (Re-added)
    start_str = request.args.get('start_date', datetime.utcnow().strftime('%Y-%m-%d'))
    end_str = request.args.get('end_date', datetime.utcnow().strftime('%Y-%m-%d'))
    
    start_date = datetime.strptime(start_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)

    # Thresholds
    MORNING_LATE = time(8, 0) 

    # 2. FETCH DATA
    logs = Attendance.query.filter(
        Attendance.school_id == school.id,
        Attendance.timestamp >= start_date,
        Attendance.timestamp < end_date
    ).order_by(Attendance.timestamp.asc()).all()
    
    morning_scans = Attendance.query.filter_by(
        school_id=school.id, status='IN', participant_type='student'
    ).filter(db.func.date(Attendance.timestamp) == start_date.date()).all()

    afternoon_scans = Attendance.query.filter_by(
        school_id=school.id, status='OUT', participant_type='student'
    ).filter(db.func.date(Attendance.timestamp) == start_date.date()).all()

    # 2. Extract IDs to compare
    morning_student_ids = {log.student_id for log in morning_scans if log.student_id}
    afternoon_student_ids = {log.student_id for log in afternoon_scans if log.student_id}

    # 3. Find the "Missing" students (In the morning, but not in the afternoon)
    missing_ids = morning_student_ids - afternoon_student_ids
    
    # Fetch student objects for the missing list
    from app.models.student import Student
    missing_students = Student.query.filter(Student.id.in_(missing_ids)).all() if missing_ids else []

    # 3. CATEGORIZATION
    tables = {
        'student_morning': [], 'student_closing': [],
        'staff_morning': [], 'staff_closing': []
    }
    
    stats = {'s_on_time': 0, 's_late': 0, 'st_on_time': 0, 'st_late': 0, 'breaches': 0}

    for log in logs:
        # Geofence Validation (Double Check)
        if not log.is_within_boundary:
            stats['breaches'] += 1

        # Determine if Late
        log.is_late = False
        if log.status == 'IN' and log.timestamp.time() > MORNING_LATE:
            log.is_late = True

        # Assign to specific table
        prefix = 'student' if log.participant_type == 'student' else 'staff'
        suffix = 'morning' if log.status == 'IN' else 'closing'
        table_key = f"{prefix}_{suffix}"
        
        if table_key in tables:
            tables[table_key].append(log)
            
            # Analytics counting
            if log.status == 'IN':
                stat_key = f"{'s' if log.participant_type == 'student' else 'st'}_{'late' if log.is_late else 'on_time'}"
                stats[stat_key] += 1

    return render_template(
        'staff/reports.html',
        tables=tables,
        stats=stats,
        start_date=start_str,
        end_date=end_str,
        missing_students=missing_students,
        completion_rate=int((len(afternoon_student_ids)/len(morning_student_ids)*100)) if morning_student_ids else 0
    )
    

@staff_bp.route('/edit/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def edit_staff(staff_id):
    # Security: Ensure they can only edit staff from their own school
    staff = Staff.query.filter_by(id=staff_id, school_id=current_user.school_id).first_or_404()

    if request.method == 'POST':
        # 1. Update standard text fields
        staff.staff_code = request.form.get('staff_code')
        staff.full_name = request.form.get('full_name')
        staff.designation = request.form.get('designation')
        staff.email = request.form.get('email')
        staff.phone = request.form.get('phone')

        # --- 2. ☁️ CLOUDFLARE R2 PHOTO UPDATE LOGIC ---
        file = request.files.get('photo')
        
        # Only process if a new file was actually selected
        if file and allowed_file(file.filename):
            # Generate a new unique filename so browsers don't cache the old image
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"staff/{uuid.uuid4().hex}.{ext}"
            
            # Read into memory and upload straight to R2!
            file_bytes = file.read()
            photo_url = upload_file_to_r2(file_bytes, photo_filename, content_type=file.mimetype)
            
            # If the upload succeeds, overwrite the old URL with the new Cloudflare link
            if photo_url:
                staff.photo_path = photo_url

        try:
            db.session.commit()
            flash("Personnel profile updated successfully.", "success")
            return redirect(url_for("staff.list_staff"))
        except Exception as e:
            db.session.rollback()
            flash(f"Database Error: Could not update profile.", "danger")
            print(f"Error: {e}")

    return render_template("staff/edit.html", staff=staff)

@staff_bp.route('/delete/<int:staff_id>', methods=['POST'])
@login_required
def delete_staff(staff_id):
    # Ensure the staff belongs to the current user's school
    staff = Staff.query.filter_by(id=staff_id, school_id=current_user.school_id).first_or_404()
    
    try:
        # Note: If you want to delete their photo/QR from Cloudflare R2, you would trigger that here!
        db.session.delete(staff)
        db.session.commit()
        flash(f"{staff.full_name} has been permanently deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Cannot delete this staff member because they have associated attendance logs.", "danger")
        
    return redirect(url_for('staff.list_staff'))

from flask import send_file
from app.services.staff_id_export_service import generate_staff_id_png

@staff_bp.route('/id-card/<int:staff_id>/download')
@login_required
def download_staff_id_card(staff_id):
    staff = Staff.query.filter_by(id=staff_id, school_id=current_user.school_id).first_or_404()

    today = datetime.utcnow()
    issued_date = today.strftime("%d %b %Y")
    expiry_date = (today + timedelta(days=365)).strftime("%d %b %Y")
    session_text = f"{today.year}/{today.year + 1}"

    card_file = generate_staff_id_png(
        staff=staff,
        issued_date=issued_date,
        expiry_date=expiry_date,
        session_text=session_text,
        public_r2_base_url=current_app.config["CF_PUBLIC_URL_PREFIX"],
    )

    safe_name = (staff.full_name or "staff").replace(" ", "_")
    filename = f"{safe_name}_Staff_ID_Card.png"

    return send_file(
        card_file,
        mimetype="image/png",
        as_attachment=True,
        download_name=filename,
        max_age=0
    )