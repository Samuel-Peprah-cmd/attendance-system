from datetime import datetime, timedelta
import io
import os
from flask import Blueprint, abort, render_template, request, send_file, make_response, url_for
from flask_login import login_required, current_user
from app.models.attendance import Attendance
from app.models.student import Student
from sqlalchemy import func
import pdfkit

# The name here MUST be 'attendance' to match 'attendance.parent_logs'
attendance_bp = Blueprint('attendance', __name__)

# @attendance_bp.route('/admin-logs')
# @login_required
# def admin_logs():
#     if current_user.role not in ('admin', 'school_admin'):
#         return "Unauthorized", 403
#     logs = Attendance.query.filter_by(school_id=current_user.school_id).order_by(Attendance.timestamp.desc()).all()
#     return render_template('attendance/admin_logs.html', logs=logs)

# @attendance_bp.route('/admin-logs')
# @login_required
# def admin_logs():
#     if current_user.role not in ('admin', 'school_admin'):
#         abort(403)

#     search = request.args.get('search', '')
#     s_id = current_user.school_id

#     # 1. Base Query
#     query = Attendance.query.join(Student).filter(Attendance.school_id == s_id)
    
#     if search:
#         query = query.filter(Student.full_name.ilike(f'%{search}%'))

#     logs = query.order_by(Attendance.timestamp.desc()).all()

#     # 2. Widget Logic (Calculated from today's data)
#     today = datetime.utcnow().date()
#     # Simple logic: count everyone who scanned "IN" today but hasn't scanned "OUT" yet
#     # For MVP: We will count today's unique Check-Ins
#     current_in = Attendance.query.filter_by(school_id=s_id, status='IN')\
#         .filter(func.date(Attendance.timestamp) == today).count()
    
#     total_students = Student.query.filter_by(school_id=s_id, is_active=True).count()

#     stats = {
#         "current_in": current_in,
#         "total_students": total_students
#     }

#     return render_template('attendance/admin_logs.html', 
#                            logs=logs, 
#                            stats=stats, 
#                            search=search)

@attendance_bp.route('/admin-logs')
@login_required
def admin_logs():
    if current_user.role not in ('admin', 'school_admin'):
        abort(403)

    search = request.args.get('search', '')
    s_id = current_user.school_id
    
    # 1. Base Query for the table
    query = Attendance.query.join(Student).filter(Attendance.school_id == s_id)
    if search:
        query = query.filter(Student.full_name.ilike(f'%{search}%'))
    
    logs = query.order_by(Attendance.timestamp.desc()).all()

    # 2. Advanced Stats Logic
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    start_of_week = today - timedelta(days=today.weekday())

    stats = {
        "today_count": Attendance.query.filter(Attendance.school_id == s_id, func.date(Attendance.timestamp) == today).count(),
        "yesterday_count": Attendance.query.filter(Attendance.school_id == s_id, func.date(Attendance.timestamp) == yesterday).count(),
        "weekly_count": Attendance.query.filter(Attendance.school_id == s_id, Attendance.timestamp >= start_of_week).count(),
        "total_students": Student.query.filter_by(school_id=s_id, is_active=True).count(),
        "current_in": Attendance.query.filter_by(school_id=s_id, status='IN').filter(func.date(Attendance.timestamp) == today).count()
    }

    return render_template('attendance/admin_logs.html', logs=logs, stats=stats, search=search)

@attendance_bp.route('/parent-logs')
@login_required
def parent_logs():
    if current_user.role != 'parent':
        return "Unauthorized", 403
    # Logic to show scans for this parent's specific children
    logs = Attendance.query.join(Student).filter(Student.guardian_one_email == current_user.email).order_by(Attendance.timestamp.desc()).all()
    return render_template('attendance/parent_logs.html', logs=logs)

import os
import pdfkit
import io
from flask import Blueprint, render_template, request, make_response, current_app
from flask_login import login_required, current_user
from app.models.attendance import Attendance
from datetime import datetime, timedelta

@attendance_bp.route('/export-weekly-pdf')
@login_required
def export_weekly():
    if current_user.role not in ('admin', 'school_admin'):
        return "Unauthorized", 403

    # 1. Date Logic
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    
    # 2. Fetch Logs
    logs = Attendance.query.filter(
        Attendance.school_id == current_user.school_id,
        Attendance.timestamp >= start_of_week
    ).order_by(Attendance.timestamp.asc()).all()

    # 3. 🚨 PRE-PROCESS IMAGES (Convert to Absolute Paths)
    # for log in logs:
    #     if log.student.photo_path:
    #         log.abs_photo_path = os.path.join(
    #             current_app.root_path, 'static', 'uploads', 'students', log.student.photo_path
    #         )
    #     else:
    #         log.abs_photo_path = None

    # # Absolute path for School Logo
    # abs_logo_path = None
    # if current_user.school.logo_path:
    #     abs_logo_path = os.path.join(
    #         current_app.root_path, 'static', 'uploads', 'logos', current_user.school.logo_path
    #     )
    
    # We no longer use local OS paths. We just ensure the template gets a full HTTP link.
    for log in logs:
        if log.student.photo_path:
            # If it's already a Cloudflare URL, great! If not, make it a full web link.
            if log.student.photo_path.startswith("http"):
                log.abs_photo_path = log.student.photo_path
            else:
                # Fallback for old local images
                log.abs_photo_path = request.host_url.rstrip('/') + url_for('static', filename=f'uploads/students/{log.student.photo_path}')
        else:
            log.abs_photo_path = None

    # Handle School Logo
    abs_logo_path = None
    if current_user.school.logo_path:
        if current_user.school.logo_path.startswith("http"):
            abs_logo_path = current_user.school.logo_path
        else:
            # Fallback for old local images
            abs_logo_path = request.host_url.rstrip('/') + url_for('static', filename=f'uploads/logos/{current_user.school.logo_path}')

    # 4. Render HTML
    rendered_html = render_template(
        'exports/weekly_report_pdf.html',
        logs=logs,
        school=current_user.school,
        abs_logo_path=abs_logo_path,
        start_date=start_of_week.strftime('%d %b'),
        end_date=today.strftime('%d %b %Y'),
        now=datetime.now()
    )

    # 5. PDF Configuration
    # path_to_wkhtmltopdf = os.getenv('WKHTMLTOPDF_PATH')
    # config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
    
    path_to_wkhtmltopdf = os.getenv('WKHTMLTOPDF_PATH', 'wkhtmltopdf') 
    
    try:
        # Some servers require specifying the exact binary path
        if path_to_wkhtmltopdf != 'wkhtmltopdf':
            config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        else:
            config = None

        options = {
            'page-size': 'A4',
            'margin-top': '0in', # We handle margins in CSS padding for letterhead look
            'margin-right': '0in',
            'margin-bottom': '0in',
            'margin-left': '0in',
            'encoding': "UTF-8",
            'enable-local-file-access': None, # 🚨 Required to see local photos
            'quiet': ''
        }

    # try:
    #     pdf = pdfkit.from_string(rendered_html, False, options=options, configuration=config)
        
    #     response = make_response(pdf)
    #     response.headers['Content-Type'] = 'application/pdf'
    #     response.headers['Content-Disposition'] = f'attachment; filename=Security_Audit_{today.strftime("%Y-%m-%d")}.pdf'
    #     return response
    
        # Generate the PDF!
        if config:
            pdf = pdfkit.from_string(rendered_html, False, options=options, configuration=config)
        else:
            pdf = pdfkit.from_string(rendered_html, False, options=options)
            
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Security_Audit_{today.strftime("%Y-%m-%d")}.pdf'
        return response
    except Exception as e:
        print(f"❌ PDF GENERATION FAILED: {str(e)}")
        return f"Audit Error: {str(e)}", 500