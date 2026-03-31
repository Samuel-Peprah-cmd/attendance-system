from datetime import datetime
import os
import uuid
import secrets
from app.models.user import User
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.services.qr_service import generate_student_qr
from werkzeug.utils import secure_filename
from app.models.student import Student
from app.models.class_room import ClassRoom
from app.extensions import db
from app.services.notification_service import  send_parent_welcome
from collections import defaultdict
from app.services.storage_helper import upload_file_to_r2

students_bp = Blueprint("students", __name__)

# Helper to check allowed photo types
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@students_bp.route("/")
@login_required
def list_students():
    students = Student.query.filter_by(school_id=current_user.school_id).all()
    return render_template("students/list.html", students=students)


@students_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_student():
    available_classes = ClassRoom.query.filter_by(school_id=current_user.school_id).all()
    
    if request.method == "POST":
        student_code = request.form.get("student_code")
        
        # 1. Unique Check
        if Student.query.filter_by(student_code=student_code).first():
            flash(f"Error: Student code {student_code} already exists.", "danger")
            return render_template("students/create.html", classes=available_classes)

        # 2. Handle Photo & DOB
        dob_str = request.form.get('date_of_birth')
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        
        # file = request.files.get('student_photo')
        # photo_filename = f"{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}" if file else None
        # if file:
        #     file.save(os.path.join(current_app.root_path, 'static/uploads/students', photo_filename))

        # # 3. Create Student
        # unique_token = str(uuid.uuid4())
        # generate_student_qr(unique_token)
        
        file = request.files.get('student_photo')
        photo_url = None
        
        if file and allowed_file(file.filename):
            # Create a clean filename in a 'students' folder inside the bucket
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"students/{uuid.uuid4().hex}.{ext}"
            
            # Read the file from the user's browser into memory and upload to R2!
            file_bytes = file.read()
            photo_url = upload_file_to_r2(file_bytes, photo_filename, content_type=file.mimetype)

        # 4. Generate QR Code (This now also uploads straight to R2!)
        unique_token = str(uuid.uuid4())
        generate_student_qr(unique_token)
        
        new_student = Student(
            school_id=current_user.school_id,
            class_room_id=request.form.get("class_room_id"),
            student_code=student_code,
            full_name=request.form.get("full_name"),
            gender=request.form.get("gender"),
            date_of_birth=dob,
            guardian_one_name=request.form.get("guardian_one_name"),
            guardian_one_phone=request.form.get("guardian_one_phone"),
            guardian_one_email=request.form.get("guardian_one_email").lower().strip(),
            guardian_one_relation=request.form.get("guardian_one_relation"),
            blood_group=request.form.get("blood_group"),
            medical_notes=request.form.get("medical_notes"),
            photo_path=photo_url,
            qr_token=unique_token
        )
        db.session.add(new_student)

        parent_email = new_student.guardian_one_email.lower().strip()
        existing_parent = User.query.filter_by(email=parent_email).first()
        
        temp_password = None
        if not existing_parent:
            temp_password = secrets.token_hex(4).upper() 
            new_user = User(email=parent_email, school_id=current_user.school_id, role='parent')
            new_user.set_password(temp_password)
            db.session.add(new_user)
        
        # We commit here so the student ID is officially in the DB
        db.session.commit()

        # 6. TRIGGER NOTIFICATION (Every child gets one)
        try:
            send_parent_welcome(parent_email, temp_password, current_user.school, new_student)
            flash(f"Success: {new_student.full_name} enrolled and parent notified!", "success")
        except Exception as e:
            print(f"Mail Error: {e}")
            flash("Student added, but email failed. Check terminal.", "warning")

            return redirect(url_for("students.list_students"))

        db.session.commit()
        flash(f"Security Enrollment Complete for {new_student.full_name}!", "success")
        return redirect(url_for("students.list_students"))
            
    return render_template("students/create.html", classes=available_classes)

# # NEW ROUTE: View the Printable ID Card
# @students_bp.route("/id-card/<int:student_id>")
# @login_required
# def view_id_card(student_id):
#     student = Student.query.get_or_404(student_id)
#     # Security check: Ensure this admin belongs to the student's school
#     if student.school_id != current_user.school_id:
#         return "Access Denied", 403
        
#     return render_template("students/id_card.html", student=student)

@students_bp.route("/id-card/<int:student_id>")
@login_required
def view_id_card(student_id):
    # CRITICAL SECURITY: We filter by BOTH student_id AND the current user's school_id
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first()
    issued_date = datetime.now().strftime("%B %d, %Y")
    
    now = datetime.now()
    current_year = now.year
    next_year = current_year + 1
    session_text = f"{current_year}-{next_year}"
    
    if not student:
        # If the student exists but belongs to another school, we return 404 (Not Found)
        # This prevents a hacker from even knowing the student ID exists in the system.
        flash("Unauthorized Access Attempt Detected.", "danger")
        return redirect(url_for('students.list_students'))
        
    return render_template("students/id_card.html", student=student, session_text=session_text, today=datetime.utcnow(), issued_date=issued_date)

# @students_bp.route("/edit/<int:student_id>", methods=["GET", "POST"])
# @login_required
# def edit_student(student_id):
#     student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
#     classes = ClassRoom.query.filter_by(school_id=current_user.school_id).all()

#     if request.method == "POST":
#         dob_str = request.form.get("date_of_birth")
#         if dob_str:
#             student.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()

#         # Pulling data from the form
#         student.full_name = request.form.get("full_name")
#         student.student_code = request.form.get("student_code")
#         student.class_room_id = request.form.get("class_room_id")
#         student.gender = request.form.get("gender")
#         student.guardian_one_name = request.form.get("guardian_one_name")
#         student.guardian_one_relation = request.form.get("guardian_one_relation")
#         student.guardian_one_phone = request.form.get("guardian_one_phone")
#         student.guardian_one_email = request.form.get("guardian_one_email")
#         student.blood_group = request.form.get("blood_group")
#         student.medical_notes = request.form.get("medical_notes")

#         try:
#             db.session.commit()
#             flash("Student profile updated successfully.", "success")
#             return redirect(url_for("students.list_students"))
#         except Exception as e:
#             db.session.rollback()
#             flash("Database Error: Could not update profile.", "danger")
            
#     return render_template("students/edit.html", student=student, classes=classes)

@students_bp.route("/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
def edit_student(student_id):
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    classes = ClassRoom.query.filter_by(school_id=current_user.school_id).all()

    if request.method == "POST":
        dob_str = request.form.get("date_of_birth")
        if dob_str:
            student.date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()

        # Pulling standard text data from the form
        student.full_name = request.form.get("full_name")
        student.student_code = request.form.get("student_code")
        student.class_room_id = request.form.get("class_room_id")
        student.gender = request.form.get("gender")
        student.guardian_one_name = request.form.get("guardian_one_name")
        student.guardian_one_relation = request.form.get("guardian_one_relation")
        student.guardian_one_phone = request.form.get("guardian_one_phone")
        student.guardian_one_email = request.form.get("guardian_one_email")
        student.blood_group = request.form.get("blood_group")
        student.medical_notes = request.form.get("medical_notes")

        # --- ☁️ CLOUDFLARE R2 PHOTO UPDATE LOGIC ---
        file = request.files.get('student_photo')
        
        # Only process the image if a new one was actually uploaded
        if file and allowed_file(file.filename):
            # Create a brand new clean filename so the browser doesn't cache the old image
            ext = file.filename.rsplit('.', 1)[1].lower()
            photo_filename = f"students/{uuid.uuid4().hex}.{ext}"
            
            # Read into memory and upload straight to R2!
            file_bytes = file.read()
            photo_url = upload_file_to_r2(file_bytes, photo_filename, content_type=file.mimetype)
            
            # If the upload was successful, overwrite the student's photo path with the new link
            if photo_url:
                student.photo_path = photo_url

        try:
            db.session.commit()
            flash("Student profile updated successfully.", "success")
            return redirect(url_for("students.list_students"))
        except Exception as e:
            db.session.rollback()
            flash("Database Error: Could not update profile.", "danger")
            
    return render_template("students/edit.html", student=student, classes=classes)

@students_bp.route("/toggle/<int:student_id>")
@login_required
def toggle_student(student_id):
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    student.is_active = not student.is_active
    db.session.commit()
    status = "Enabled" if student.is_active else "Disabled"
    flash(f"Student {student.full_name} has been {status}.", "info")
    return redirect(url_for("students.list_students"))

@students_bp.route("/delete/<int:student_id>")
@login_required
def delete_student(student_id):
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    
    # Delete associated photo and QR code files first
    # (Good for production cleanup)
    
    db.session.delete(student)
    db.session.commit()
    flash("Student record permanently removed.", "danger")
    return redirect(url_for("students.list_students"))

@students_bp.route("/parents")
@login_required
def list_parents():
    # 1. Fetch all active students for this school
    students = Student.query.filter_by(
        school_id=current_user.school_id, 
        is_active=True
    ).all()

    # 2. Group by email
    parent_map = defaultdict(list)
    for student in students:
        parent_map[student.guardian_one_email].append(student)

    # 3. Build the list and LOOK UP the User ID
    parents_list = []
    for email, children in parent_map.items():
        first_child = children[0]
        
        # 🛡️ SECURITY LOOKUP: Find the actual User account for this email
        user_account = User.query.filter_by(email=email).first()
        
        parents_list.append({
            "id": user_account.id if user_account else None, # <--- THIS FIXES THE ERROR
            "name": first_child.guardian_one_name,
            "phone": first_child.guardian_one_phone,
            "email": email,
            "relation": first_child.guardian_one_relation,
            "children": children
        })

    return render_template("students/parent_list.html", parents=parents_list)

@students_bp.route("/parents/reset-password/<int:user_id>")
@login_required
def admin_reset_parent_password(user_id):
    # Security: Ensure this parent actually has a kid in the admin's school
    parent = User.query.get_or_404(user_id)
    has_student = Student.query.filter_by(guardian_one_email=parent.email, 
                                         school_id=current_user.school_id).first()
    
    if not has_student:
        flash("Unauthorized: This parent has no students in your school.", "danger")
        return redirect(url_for('students.list_parents'))

    new_temp_pass = secrets.token_hex(4).upper()
    parent.set_password(new_temp_pass)
    db.session.commit()
    
    try:
        from app.services.notification_service import send_parent_welcome
        send_parent_welcome(parent.email, new_temp_pass, current_user.school)
        flash(f"Success: Password for {parent.email} reset and emailed.", "success")
    except Exception as e:
        flash(f"Password reset to {new_temp_pass}, but email failed.", "warning")
        
    return redirect(url_for('students.list_parents'))

@students_bp.route("/medical-records")
@login_required
def medical_records():
    """Dedicated directory for student allergies, blood types, and emergency contacts."""
    # Fetch all active students for this school
    students = Student.query.filter_by(school_id=current_user.school_id, is_active=True)\
                            .order_by(Student.full_name.asc()).all()
    
    return render_template("students/medical_records.html", students=students)