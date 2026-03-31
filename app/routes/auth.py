from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_user, logout_user, login_required
from app.models.user import User
import secrets
from app.extensions import db

auth_bp = Blueprint("auth", __name__)


# @auth_bp.route("/login", methods=["GET", "POST"])
# def login():
#     if request.method == "POST":
#         email = request.form.get("email")
#         password = request.form.get("password")
#         user = User.query.filter_by(email=email).first()
        
#         if user and user.check_password(password):
#             login_user(user)
#             # LOGIC: If Super Admin, go to School Management. If School Admin, go to Dashboard.
#             if user.role == 'super_admin':
#                 return redirect(url_for("schools.manage_schools"))
#             return redirect(url_for("dashboard.index"))
        
#         flash("Invalid credentials", "danger")
#     return render_template("auth/login.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # 1. SECURITY CHECK: If School Admin or Parent, check School Status
            if user.role != 'super_admin' and user.school:
                if not user.school.is_active:
                    flash("Access Denied: Your school's subscription is inactive. Contact AtomDev.", "danger")
                    return redirect(url_for('auth.login'))
            
            # 2. LOG THEM IN
            login_user(user)
            
            # 3. STRATEGIC REDIRECTION
            if user.role == 'super_admin':
                return redirect(url_for("schools.manage_schools"))
            elif user.role == 'parent':
                return redirect(url_for("parents.dashboard")) # The Family Portal
            else:
                return redirect(url_for("dashboard.index")) # School Admin Dashboard
        
        flash("Invalid email or security password.", "danger")
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    # This calls the "login" function inside the "auth" blueprint
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        if new_password and new_password == confirm_password:
            current_user.set_password(new_password)
            db.session.commit()
            flash("Security credentials updated successfully!", "success")
            return redirect(url_for('dashboard.index'))
        else:
            flash("Passwords do not match.", "danger")
            
    return render_template("auth/profile.html")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        user = User.query.filter_by(email=email).first()
        if user:
            # Generate a temp password
            temp_pass = secrets.token_hex(4).upper()
            user.set_password(temp_pass)
            db.session.commit()
            
            # Use our existing notification service to send it
            from app.services.notification_service import send_parent_welcome
            # We reuse this function as it handles the branding and logo perfectly
            send_parent_welcome(user.email, temp_pass, user.school)
            
            flash("A new temporary password has been sent to your email.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Email not found in our security database.", "danger")
            
    return render_template("auth/forgot_password.html")