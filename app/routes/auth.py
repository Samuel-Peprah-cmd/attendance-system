from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_user, logout_user, login_required
from app.models.school_profile import SchoolProfile
from app.models.user import User
import secrets
from app.extensions import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # 🚨 REFRESH: Pull latest data from DB (Plan ID, etc)
            db.session.refresh(user)

            # ✅ LOG THEM IN FIRST! Give them a valid session token.
            login_user(user)

            # Now that they are logged in, check where to send them
            if user.role != 'super_admin' and user.school:
                if not user.school.is_active:
                    # 🚨 SOFT REDIRECT: Send them to the payment/billing page
                    flash("Subscription Expired. Please renew to continue using ATOM Gate.", "warning")
                    return redirect(url_for('billing.pricing_page')) # Make sure this matches your actual billing route name!
            
            # If they are active (or a super_admin), let them into the dashboard
            if user.role == 'super_admin':
                return redirect(url_for("schools.manage_schools"))
            return redirect(url_for("dashboard.index"))
        
        flash("Invalid credentials.", "danger")
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
    school_profile = None

    # 🚨 FIX 1: Safely check if the user is an admin or school_admin
    if current_user.role in ["admin", "school_admin"] and current_user.school_id:
        school_profile = SchoolProfile.query.filter_by(school_id=current_user.school_id).first()
        if not school_profile:
            school_profile = SchoolProfile(school_id=current_user.school_id)
            db.session.add(school_profile)
            db.session.commit()

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "password":
            new_password = request.form.get("new_password")
            confirm_password = request.form.get("confirm_password")

            if new_password and new_password == confirm_password:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Security credentials updated successfully!", "success")
                return redirect(url_for("auth.profile"))
            else:
                flash("Passwords do not match.", "danger")

        # 🚨 FIX 2: Allow BOTH 'admin' and 'school_admin' to save the profile!
        elif form_type == "school_profile" and current_user.role in ["admin", "school_admin"] and school_profile:
            school_profile.email_primary = request.form.get("email_primary")
            school_profile.email_secondary = request.form.get("email_secondary")
            school_profile.phone_primary = request.form.get("phone_primary")
            school_profile.phone_secondary = request.form.get("phone_secondary")
            school_profile.website = request.form.get("website")
            school_profile.address_line_1 = request.form.get("address_line_1")
            school_profile.address_line_2 = request.form.get("address_line_2")
            school_profile.city = request.form.get("city")
            school_profile.region_state = request.form.get("region_state")
            school_profile.postal_code = request.form.get("postal_code")
            school_profile.country = request.form.get("country") or "Ghana"

            db.session.commit()
            flash("School contact profile updated successfully!", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", school_profile=school_profile)

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