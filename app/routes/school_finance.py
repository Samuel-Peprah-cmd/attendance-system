from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.billing import SchoolSubscription
from app.models.billing import PaymentTransaction
from app.models.billing import Plan
from app.models.student import Student
from app.models.scanner_device import ScannerDevice

# Registering under 'finance' to match your nav link
finance_bp = Blueprint('finance', __name__) 

@finance_bp.route('/billing-dashboard')
@login_required
def school_finance_page():
    # Get active subscription and current plan
    sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
    plan = Plan.query.get(sub.plan_id) if sub else None
    
    # Calculate limits/usage
    student_count = Student.query.filter_by(school_id=current_user.school_id).count()
    device_count = ScannerDevice.query.filter_by(school_id=current_user.school_id).count()
    
    # Get payment history
    transactions = PaymentTransaction.query.filter_by(school_id=current_user.school_id)\
                   .order_by(PaymentTransaction.paid_at.desc()).limit(10).all()
                   
    return render_template('school_admin/finance_dashboard.html',
                           subscription=sub,
                           current_plan=plan,
                           student_count=student_count,
                           device_count=device_count,
                           transactions=transactions)