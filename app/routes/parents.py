from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.student import Student
from datetime import datetime

parents_bp = Blueprint("parents", __name__)

@parents_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != 'parent':
        flash("Access restricted to parents.", "danger")
        return redirect(url_for('dashboard.index'))

    # THE MAGIC: Find all students where the guardian email matches this logged-in parent
    my_children = Student.query.filter_by(guardian_one_email=current_user.email).all()
    
    return render_template("dashboard/parent_view.html", children=my_children)

@parents_bp.route("/child-id/<int:student_id>")
@login_required
def view_id_card(student_id):
    # SECURITY: Ensure this parent actually owns this student record
    student = Student.query.filter_by(id=student_id, guardian_one_email=current_user.email).first_or_404()
    issued_date = datetime.now().strftime("%d %b %Y")
    
    now = datetime.now()
    session_text = f"{now.year}-{now.year + 1}"
    
    return render_template("students/id_card.html", student=student, session_text=session_text, issued_date=issued_date)