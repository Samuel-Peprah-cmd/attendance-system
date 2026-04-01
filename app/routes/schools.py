import os
import secrets
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.school import School
from app.models.user import User
from app.extensions import db
from functools import wraps
from app.models.scanner_device import ScannerDevice
from app.models.attendance import Attendance
from app.models.student import Student
from app.models.staff import Staff
from app.models.class_room import ClassRoom
from app.models.scanner_device import ScannerDevice

# ☁️ CLOUDFLARE UPLOADER IMPORTED
from app.services.storage_helper import upload_file_to_r2

schools_bp = Blueprint("schools", __name__)

# --- SECURITY: SUPER ADMIN DECORATOR ---
def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only allow AtomDev Studios (super_admin) to access these routes
        if not current_user.is_authenticated or current_user.role != 'super_admin':
            flash("Access Denied: Super Admin privileges required.", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTE: MANAGE ALL SCHOOLS ---
@schools_bp.route("/manage")
@login_required
@super_admin_required
def manage_schools():
    """AtomDev Dashboard to see all client schools."""
    all_schools = School.query.all()
    return render_template("schools/manage.html", schools=all_schools)

# --- ROUTE: CREATE NEW SCHOOL & ADMIN ---
@schools_bp.route("/create", methods=["GET", "POST"])
@login_required
@super_admin_required
def create_school():
    """AtomDev creates a new school and its first admin account."""
    if request.method == "POST":
        # 1. Handle School Logo Upload to R2
        logo_file = request.files.get('school_logo')
        logo_url = None
        
        if logo_file and logo_file.filename != '':
            ext = logo_file.filename.rsplit('.', 1)[1].lower()
            logo_filename = f"logos/logo_{uuid.uuid4().hex}.{ext}"
            
            # Read into memory and upload straight to R2
            file_bytes = logo_file.read()
            logo_url = upload_file_to_r2(file_bytes, logo_filename, content_type=logo_file.mimetype)

        # 2. Create the School Object
        new_school = School(
            name=request.form.get("school_name"),
            slug=request.form.get("school_name").lower().replace(" ", "-"),
            api_key=str(uuid.uuid4())[:18], # Unique key for the tablet scanner
            primary_color=request.form.get("primary_color", "#2563eb"),
            secondary_color=request.form.get("secondary_color", "#1e40af"),
            logo_path=logo_url  # <--- Now saves the https://cloudflare... link!
        )
        
        try:
            db.session.add(new_school)
            db.session.flush() # Flushes to DB to generate the new_school.id

            # 3. Create the School's First Admin User
            school_admin = User(
                email=request.form.get("admin_email"),
                school_id=new_school.id,
                role='school_admin'
            )
            school_admin.set_password(request.form.get("admin_password"))
            
            db.session.add(school_admin)
            db.session.commit()
            
            flash(f"Successfully onboarded {new_school.name}!", "success")
            return redirect(url_for("schools.manage_schools"))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating school: {str(e)}", "danger")

    return render_template("schools/create.html")

@schools_bp.route('/edit/<int:school_id>', methods=['GET', 'POST'])
@login_required
def edit_school(school_id):
    # Security: ONLY the Super Admin (Master Account) can edit a school
    if current_user.role != 'super_admin':
        abort(403)
        
    school = School.query.get_or_404(school_id)
    
    if request.method == 'POST':
        # 1. BULLETPROOF NAME CHECK: 
        # Tries to get 'school_name', falls back to 'name' if HTML differs
        new_name = request.form.get('school_name') or request.form.get('name')
        
        if not new_name or new_name.strip() == "":
            flash("Error: Official School Name cannot be empty.", "danger")
            return redirect(url_for('schools.edit_school', school_id=school.id))
            
        # Update text/color fields
        school.name = new_name.strip()
        school.primary_color = request.form.get('primary_color')
        school.secondary_color = request.form.get('secondary_color')
        
        # 2. HANDLE CLOUDFLARE R2 LOGO UPLOAD
        file = request.files.get('school_logo')
        if file and file.filename != '':
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"schools/logo_{uuid.uuid4().hex}.{ext}"
            
            # Read into memory and upload
            file_bytes = file.read()
            photo_url = upload_file_to_r2(file_bytes, photo_filename, content_type=file.mimetype)
            
            if photo_url:
                school.logo_path = photo_url
        
        # 3. SAVE TO DATABASE
        try:
            db.session.commit()
            flash(f"'{school.name}' identity updated successfully.", "success")
            return redirect(url_for('schools.manage_schools')) # Adjust if your route is named differently
        except Exception as e:
            db.session.rollback()
            flash(f"Database Error: Could not update school.", "danger")
            print(f"Error: {e}")
            
    return render_template('schools/edit.html', school=school)

@schools_bp.route('/delete/<int:school_id>', methods=['POST'])
@login_required
def delete_school(school_id):
    # Security: ONLY the Super Admin
    if current_user.role != 'super_admin':
        abort(403)
        
    school = School.query.get_or_404(school_id)
    
    try:
        # 1. Wipe all Attendance Logs for this school
        Attendance.query.filter_by(school_id=school_id).delete()
        
        # 2. Wipe all Students and Staff
        Student.query.filter_by(school_id=school_id).delete()
        Staff.query.filter_by(school_id=school_id).delete()
        
        ScannerDevice.query.filter_by(school_id=school_id).delete()
        # 🚨 THE FIX: Uncomment these so they actually get deleted!
        # 3. Wipe all Classrooms
        ClassRoom.query.filter_by(school_id=school_id).delete()
        
        # 4. Wipe all School Admins and Parents (Except Super Admins)
        User.query.filter(User.school_id == school_id, User.role != 'super_admin').delete() 
        
        # 5. FINALLY, delete the empty school
        db.session.delete(school)
        db.session.commit()
        
        flash(f"School '{school.name}' and ALL associated data have been permanently wiped.", "success")
        
    except Exception as e:
        db.session.rollback()
        print(f"Delete Error: {e}")
        flash("System Error: Could not wipe the school data. Check the terminal.", "danger")
        
    return redirect(url_for('schools.manage_schools'))

@schools_bp.route("/reset-key/<int:school_id>")
@login_required
@super_admin_required
def reset_api_key(school_id):
    school = School.query.get_or_404(school_id)
    school.api_key = str(uuid.uuid4())[:18]
    db.session.commit()
    flash(f"API Key for {school.name} has been rotated.", "success")
    return redirect(url_for("schools.manage_schools"))

@schools_bp.route("/toggle-status/<int:school_id>")
@login_required
@super_admin_required
def toggle_school_status(school_id):
    school = School.query.get_or_404(school_id)
    school.is_active = not school.is_active
    db.session.commit()
    status = "Activated" if school.is_active else "Deactivated"
    flash(f"{school.name} has been {status}.", "info")
    return redirect(url_for("schools.manage_schools"))

@schools_bp.route('/master/manage-devices')
@login_required
def manage_devices():
    # Only YOU (Super Admin) can enter this room
    if current_user.role != 'super_admin':
        abort(403)
    
    devices = ScannerDevice.query.all() # See EVERY device from EVERY school
    schools = School.query.all() # For the "Assign to School" dropdown
    return render_template('schools/manage_scanners.html', devices=devices, schools=schools)

@schools_bp.route('/master/add-device', methods=['POST'])
@login_required
def add_device():
    if current_user.role != 'super_admin':
        abort(403)

    school_id = request.form.get('school_id') # Pick the school
    name = request.form.get('device_name')
    location = request.form.get('location')
    
    new_device = ScannerDevice(
        school_id=school_id,
        device_name=name,
        location_name=location,
        device_code=f"DEV-{secrets.token_hex(3).upper()}"
    )
    db.session.add(new_device)
    db.session.commit()
    flash(f"Device deployed to School ID {school_id}!", "success")
    return redirect(url_for('schools.manage_devices'))

@schools_bp.route('/scans/toggle-device/<int:id>')
@login_required
def toggle_device(id):
    device = ScannerDevice.query.get_or_404(id)
    device.is_active = not device.is_active
    db.session.commit()
    return redirect(url_for('schools.manage_devices'))

@schools_bp.route('/master/reassign-device/<int:id>', methods=['POST'])
@login_required
def reassign_device(id):
    if current_user.role != 'super_admin':
        abort(403)
        
    device = ScannerDevice.query.get_or_404(id)
    new_school_id = request.form.get('new_school_id')
    
    # Update school
    device.school_id = new_school_id
    # Reset Key (This forces the 'Unauthorized' reset on the tablet)
    import secrets
    device.api_key = f"NODE-{secrets.token_hex(8).upper()}"
    
    db.session.commit()
    return redirect(url_for('schools.manage_devices'))








# import os
# import secrets
# import uuid
# from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
# from flask_login import login_required, current_user
# from werkzeug.utils import secure_filename
# from app.models.school import School
# from app.models.user import User
# from app.extensions import db
# from functools import wraps
# from app.models.scanner_device import ScannerDevice
# from app.services.storage_helper import upload_file_to_r2

# schools_bp = Blueprint("schools", __name__)

# # --- SECURITY: SUPER ADMIN DECORATOR ---
# def super_admin_required(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         # Only allow AtomDev Studios (super_admin) to access these routes
#         if not current_user.is_authenticated or current_user.role != 'super_admin':
#             flash("Access Denied: Super Admin privileges required.", "danger")
#             return redirect(url_for('auth.login'))
#         return f(*args, **kwargs)
#     return decorated_function

# # --- ROUTE: MANAGE ALL SCHOOLS ---
# @schools_bp.route("/manage")
# @login_required
# @super_admin_required
# def manage_schools():
#     """AtomDev Dashboard to see all client schools."""
#     all_schools = School.query.all()
#     return render_template("schools/manage.html", schools=all_schools)

# # --- ROUTE: CREATE NEW SCHOOL & ADMIN ---
# @schools_bp.route("/create", methods=["GET", "POST"])
# @login_required
# @super_admin_required
# def create_school():
#     """AtomDev creates a new school and its first admin account."""
#     if request.method == "POST":
#         # 1. Handle School Logo Upload
#         logo_file = request.files.get('school_logo')
#         logo_filename = None
        
#         if logo_file and logo_file.filename != '':
#             ext = logo_file.filename.rsplit('.', 1)[1].lower()
#             logo_filename = f"logo_{uuid.uuid4().hex}.{ext}"
            
#             # Ensure folder exists
#             logo_folder = os.path.join(current_app.root_path, 'static/uploads/logos')
#             if not os.path.exists(logo_folder):
#                 os.makedirs(logo_folder)
                
#             logo_file.save(os.path.join(logo_folder, logo_filename))

#         # 2. Create the School Object
#         new_school = School(
#             name=request.form.get("school_name"),
#             slug=request.form.get("school_name").lower().replace(" ", "-"),
#             api_key=str(uuid.uuid4())[:18], # Unique key for the tablet scanner
#             primary_color=request.form.get("primary_color", "#2563eb"),
#             secondary_color=request.form.get("secondary_color", "#1e40af"),
#             logo_path=logo_filename
#         )
        
#         try:
#             db.session.add(new_school)
#             db.session.flush() # Flushes to DB to generate the new_school.id

#             # 3. Create the School's First Admin User
#             school_admin = User(
#                 email=request.form.get("admin_email"),
#                 school_id=new_school.id,
#                 role='school_admin'
#             )
#             school_admin.set_password(request.form.get("admin_password"))
            
#             db.session.add(school_admin)
#             db.session.commit()
            
#             flash(f"Successfully onboarded {new_school.name}!", "success")
#             return redirect(url_for("schools.manage_schools"))
            
#         except Exception as e:
#             db.session.rollback()
#             flash(f"Error creating school: {str(e)}", "danger")

#     return render_template("schools/create.html")

# @schools_bp.route("/reset-key/<int:school_id>")
# @login_required
# @super_admin_required
# def reset_api_key(school_id):
#     school = School.query.get_or_404(school_id)
#     school.api_key = str(uuid.uuid4())[:18]
#     db.session.commit()
#     flash(f"API Key for {school.name} has been rotated.", "success")
#     return redirect(url_for("schools.manage_schools"))

# @schools_bp.route("/toggle-status/<int:school_id>")
# @login_required
# @super_admin_required
# def toggle_school_status(school_id):
#     school = School.query.get_or_404(school_id)
#     school.is_active = not school.is_active
#     db.session.commit()
#     status = "Activated" if school.is_active else "Deactivated"
#     flash(f"{school.name} has been {status}.", "info")
#     return redirect(url_for("schools.manage_schools"))

# @schools_bp.route('/master/manage-devices')
# @login_required
# def manage_devices():
#     # Only YOU (Super Admin) can enter this room
#     if current_user.role != 'super_admin':
#         abort(403)
    
#     devices = ScannerDevice.query.all() # See EVERY device from EVERY school
#     schools = School.query.all() # For the "Assign to School" dropdown
#     return render_template('schools/manage_scanners.html', devices=devices, schools=schools)

# @schools_bp.route('/master/add-device', methods=['POST'])
# @login_required
# def add_device():
#     if current_user.role != 'super_admin':
#         abort(403)

#     school_id = request.form.get('school_id') # Pick the school
#     name = request.form.get('device_name')
#     location = request.form.get('location')
    
#     new_device = ScannerDevice(
#         school_id=school_id,
#         device_name=name,
#         location_name=location,
#         device_code=f"DEV-{secrets.token_hex(3).upper()}"
#     )
#     db.session.add(new_device)
#     db.session.commit()
#     flash(f"Device deployed to School ID {school_id}!", "success")
#     return redirect(url_for('schools.manage_devices'))

# @schools_bp.route('/scans/toggle-device/<int:id>')
# @login_required
# def toggle_device(id):
#     device = ScannerDevice.query.get_or_404(id)
#     device.is_active = not device.is_active
#     db.session.commit()
#     return redirect(url_for('schools.manage_devices'))

# @schools_bp.route('/master/reassign-device/<int:id>', methods=['POST'])
# @login_required
# def reassign_device(id):
#     if current_user.role != 'super_admin':
#         abort(403)
        
#     device = ScannerDevice.query.get_or_404(id)
#     new_school_id = request.form.get('new_school_id')
    
#     # Update school
#     device.school_id = new_school_id
#     # Reset Key (This forces the 'Unauthorized' reset on the tablet)
#     import secrets
#     device.api_key = f"NODE-{secrets.token_hex(8).upper()}"
    
#     db.session.commit()
#     return redirect(url_for('schools.manage_devices'))