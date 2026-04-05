import os
import uuid
from flask import Blueprint, abort, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.student import Student
from app.models.attendance import Attendance
from app.extensions import db  # <--- This fixes the yellow underline
from datetime import datetime, time, timedelta
from app.models.school import School
from app.models.class_room import ClassRoom
from datetime import datetime, timedelta, time as dt_time
from app.services.storage_helper import upload_file_to_r2
from app.models.staff import Staff
from datetime import datetime, date

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    # 🚨 1. SUPER ADMIN REDIRECT 
    if current_user.role == 'super_admin':
        return redirect(url_for('schools.manage_schools')) 
        
    school_id = current_user.school_id
    school = School.query.get(school_id)
    
    # 🚨 2. SAFETY CATCH
    if not school:
        return "Error: Your account is not linked to a school. Please contact support.", 403

    # 🚨 3. BILLING CATCH
    if not school.is_active:
        flash("Subscription Expired. Please renew to access your dashboard.", "warning")
        return redirect(url_for('billing.pricing_page')) # Send them to the payment page

    # 4. Setup Exact Timeframes (the rest of your logic stays the same)
    now = datetime.utcnow()
    today = now.date()
    yesterday = today - timedelta(days=1)
    
    # Get Monday of the current week at exactly 00:00:00
    start_of_week_date = today - timedelta(days=today.weekday())
    start_of_week = datetime.combine(start_of_week_date, dt_time.min) 

    # 4. Build the 'stats' dictionary
    stats = {
        "today_count": Attendance.query.filter(
            Attendance.school_id == school_id, 
            db.func.date(Attendance.timestamp) == today
        ).count(),
        
        "yesterday_count": Attendance.query.filter(
            Attendance.school_id == school_id, 
            db.func.date(Attendance.timestamp) == yesterday
        ).count(),
        
        "weekly_count": Attendance.query.filter(
            Attendance.school_id == school_id, 
            Attendance.timestamp >= start_of_week # Now compares datetime to datetime accurately!
        ).count(),
        
        "current_in": Attendance.query.filter(
            Attendance.school_id == school_id,
            Attendance.status == 'IN',
            db.func.date(Attendance.timestamp) == today
        ).count()
    }

    # 5. Global Stats
    total_students = Student.query.filter_by(school_id=school_id).count()
    
    # 6. Geofence Violations
    violations = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.is_within_boundary == False,
        db.func.date(Attendance.timestamp) == today
    ).order_by(Attendance.timestamp.desc()).limit(5).all()

    # 7. Top Late Arrivals (Dynamic calculation based on school settings)
    opening = school.opening_time if school.opening_time else dt_time(7, 30)
    late_threshold = datetime.combine(today, opening)
    late_arrivals = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.status == 'IN',
        Attendance.timestamp > late_threshold,
        db.func.date(Attendance.timestamp) == today
    ).order_by(Attendance.timestamp.desc()).limit(5).all()

    # 8. Final Data Hand-off
    return render_template("dashboard/index.html", 
                           total_students=total_students, 
                           stats=stats,  
                           violations=violations,
                           late_arrivals=late_arrivals)


# @dashboard_bp.route("/settings", methods=["GET", "POST"])
# @login_required
# def settings():
#     school = School.query.get(current_user.school_id)
    
#     if request.method == "POST":
#         # SAFETY CHECK: Get the name, but if it's empty, keep the old name
#         new_name = request.form.get("name")
#         if new_name:
#             school.name = new_name
            
#         school.primary_color = request.form.get("primary_color")
#         school.secondary_color = request.form.get("secondary_color")
        
#         # 📍 NEW: Geofencing Data Capture
#         # We use float() and int() to ensure we aren't saving "strings" to numeric columns
#         school.latitude = float(request.form.get("latitude", 0.0))
#         school.longitude = float(request.form.get("longitude", 0.0))
#         school.radius_meters = int(request.form.get("radius_meters", 200))
        
#         # Handle Logo Update
#         logo = request.files.get('logo')
#         if logo and logo.filename != '':
#             filename = secure_filename(f"logo_{school.id}_{logo.filename}")
#             # Ensure the logos folder exists!
#             logo_path = os.path.join(current_app.root_path, 'static/uploads/logos')
#             if not os.path.exists(logo_path):
#                 os.makedirs(logo_path)
            
#             logo.save(os.path.join(logo_path, filename))
#             school.logo_path = filename
            
#         db.session.commit()
#         flash("Branding updated for the entire system!", "success")
#         return redirect(url_for("dashboard.settings"))
        
#     return render_template("dashboard/settings.html", school=school)


@dashboard_bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    school = School.query.get(current_user.school_id)
    
    if request.method == "POST":
        # SAFETY CHECK: Get the name, but if it's empty, keep the old name
        new_name = request.form.get("name")
        if new_name:
            school.name = new_name
            
        school.primary_color = request.form.get("primary_color")
        school.secondary_color = request.form.get("secondary_color")
        
        # 📍 Geofencing Data Capture
        school.latitude = float(request.form.get("latitude", 0.0))
        school.longitude = float(request.form.get("longitude", 0.0))
        school.radius_meters = int(request.form.get("radius_meters", 200))
        
        # ⏱️ NEW: Time Settings Capture
        # HTML time inputs send data as strings like "07:30" or "15:00"
        opening_str = request.form.get("opening_time")
        closing_str = request.form.get("closing_time")
        
        if opening_str:
            school.opening_time = datetime.strptime(opening_str, "%H:%M").time()
        if closing_str:
            school.closing_time = datetime.strptime(closing_str, "%H:%M").time()
        
       # --- ☁️ CLOUDFLARE R2 LOGO UPLOAD ---
        logo = request.files.get('logo')
        if logo and logo.filename != '':
            ext = logo.filename.rsplit('.', 1)[1].lower()
            # We add a uuid so the browser doesn't aggressively cache the old logo
            logo_filename = f"logos/logo_{school.id}_{uuid.uuid4().hex[:8]}.{ext}"
            
            file_bytes = logo.read()
            logo_url = upload_file_to_r2(file_bytes, logo_filename, content_type=logo.mimetype)
            
            if logo_url:
                school.logo_path = logo_url
            
        db.session.commit()
        flash("Settings and schedule updated for the entire system!", "success")
        return redirect(url_for("dashboard.settings"))
        
    return render_template("dashboard/settings.html", school=school)


@dashboard_bp.route("/classes", methods=["GET", "POST"])
@login_required
def manage_classes():
    if request.method == "POST":
        class_name = request.form.get("class_name")
        if class_name:
            new_class = ClassRoom(name=class_name, school_id=current_user.school_id)
            db.session.add(new_class)
            db.session.commit()
            flash(f"Class {class_name} added!", "success")
            return redirect(url_for("dashboard.manage_classes"))
            
    classes = ClassRoom.query.filter_by(school_id=current_user.school_id).all()
    return render_template("dashboard/classes.html", classes=classes)

@dashboard_bp.route("/my-children")
@login_required
def parent_dashboard():
    if current_user.role != 'parent':
        abort(403)
    
    # 'students' relationship in the User model automatically finds their kids
    children = current_user.students 
    return render_template("dashboard/parent_view.html", children=children)

admin_bp = Blueprint('admin', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def overview():
    # 🚨 BILLING CATCH
    if current_user.role != 'super_admin' and current_user.school and not current_user.school.is_active:
        flash("Subscription Expired. Please renew to access your dashboard.", "warning")
        return redirect(url_for('billing.pricing_page'))

    school_id = current_user.school_id
    today = date.today()

    # 1. High-Level Stats (the rest of your logic stays the same)
    total_students = Student.query.filter_by(school_id=school_id, is_active=True).count()
    total_staff = Staff.query.filter_by(school_id=school_id, is_active=True).count()
    
    # 2. Activity Today
    scans_today = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.timestamp >= today
    ).count()

    # 3. Security Alerts (Out of Bounds scans today)
    gps_alerts = Attendance.query.filter(
        Attendance.school_id == school_id,
        Attendance.timestamp >= today,
        Attendance.is_within_boundary == False
    ).count()

    # 4. Recent Activity (Last 5)
    recent_logs = Attendance.query.filter_by(school_id=school_id)\
        .order_by(Attendance.timestamp.desc()).limit(5).all()

    return render_template('admin/overview.html', 
                           total_students=total_students,
                           total_staff=total_staff,
                           scans_today=scans_today,
                           gps_alerts=gps_alerts,
                           recent_logs=recent_logs)

@dashboard_bp.route('/terminal')
def web_scanner():
    """
    Serves the Security Terminal (Web Scanner).
    No need for an API_URL variable anymore because it's the same server!
    """
    # Grab the device key from config (if you have it set in .env)
    # This allows you to 'pre-activate' the node if you want.
    device_key = current_app.config.get('SCANNER_DEVICE_KEY', '')
    
    return render_template('scanner.html', device_key=device_key)

@dashboard_bp.route('/privacy')
def privacy():
    return render_template('privacy.html', title="Privacy Policy - ATOM Gate")

@dashboard_bp.route('/terms')
def terms():
    return render_template('terms.html', title="Terms of Service - ATOM Gate")

@dashboard_bp.route('/about')
def about():
    return render_template('about.html', title="About Us - ATOM Gate")