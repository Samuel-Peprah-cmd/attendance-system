from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.billing import SchoolSubscription, PaymentTransaction, Plan
from app.models.student import Student
from app.models.scanner_device import ScannerDevice
from datetime import datetime
import calendar

finance_bp = Blueprint('finance', __name__)


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(dt: datetime, months_back: int) -> datetime:
    year = dt.year
    month = dt.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


@finance_bp.route('/billing-dashboard')
@login_required
def school_finance_page():
    sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
    plan = Plan.query.get(sub.plan_id) if sub else None

    student_count = Student.query.filter_by(school_id=current_user.school_id).count()
    device_count = ScannerDevice.query.filter_by(school_id=current_user.school_id).count()

    transactions = (
        PaymentTransaction.query
        .filter_by(school_id=current_user.school_id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(100)
        .all()
    )

    total_transactions = PaymentTransaction.query.filter_by(school_id=current_user.school_id).count()
    successful_transactions = PaymentTransaction.query.filter_by(
        school_id=current_user.school_id, status='success'
    ).count()
    pending_transactions = PaymentTransaction.query.filter_by(
        school_id=current_user.school_id, status='pending'
    ).count()
    failed_transactions = PaymentTransaction.query.filter_by(
        school_id=current_user.school_id, status='failed'
    ).count()

    total_spent = (
        db.session.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0))
        .filter(
            PaymentTransaction.school_id == current_user.school_id,
            PaymentTransaction.status == 'success'
        )
        .scalar()
        or 0.0
    )

    avg_payment = round(total_spent / successful_transactions, 2) if successful_transactions else 0.0

    last_successful_payment = (
        PaymentTransaction.query
        .filter_by(school_id=current_user.school_id, status='success')
        .order_by(PaymentTransaction.paid_at.desc(), PaymentTransaction.created_at.desc())
        .first()
    )

    days_remaining = None
    if sub and sub.end_date:
        days_remaining = max((sub.end_date.date() - datetime.utcnow().date()).days, 0)

    if plan and plan.student_limit not in (None, 0, -1):
        student_pct = min(round((student_count / plan.student_limit) * 100, 2), 100)
    elif plan and plan.student_limit == -1:
        student_pct = 100
    else:
        student_pct = 0

    if plan and plan.scanner_limit not in (None, 0, -1):
        device_pct = min(round((device_count / plan.scanner_limit) * 100, 2), 100)
    elif plan and plan.scanner_limit == -1:
        device_pct = 100
    else:
        device_pct = 0

    success_rate = round((successful_transactions / total_transactions) * 100, 2) if total_transactions else 0.0

    renewal_amount = None
    if plan and sub:
        if sub.billing_cycle == 'annual':
            renewal_amount = plan.price_annual
        else:
            renewal_amount = plan.price_monthly

    current_month_start = _month_start(datetime.utcnow())
    month_points = [_shift_month(current_month_start, i) for i in range(5, -1, -1)]
    month_keys = [(d.year, d.month) for d in month_points]
    monthly_spend_labels = [f"{calendar.month_abbr[d.month]} {str(d.year)[-2:]}" for d in month_points]
    spend_map = {key: 0.0 for key in month_keys}

    successful_chart_txns = (
        PaymentTransaction.query
        .filter(
            PaymentTransaction.school_id == current_user.school_id,
            PaymentTransaction.status == 'success',
            PaymentTransaction.created_at >= month_points[0]
        )
        .all()
    )

    for txn in successful_chart_txns:
        txn_date = txn.paid_at or txn.created_at
        key = (txn_date.year, txn_date.month)
        if key in spend_map:
            spend_map[key] += float(txn.amount or 0)

    monthly_spend_data = [round(spend_map[key], 2) for key in month_keys]

    channel_rows = (
        db.session.query(PaymentTransaction.channel, func.count(PaymentTransaction.id))
        .filter(PaymentTransaction.school_id == current_user.school_id)
        .group_by(PaymentTransaction.channel)
        .all()
    )
    channel_breakdown = {}
    for channel, count in channel_rows:
        label = channel.replace('_', ' ').title() if channel else 'Unknown'
        channel_breakdown[label] = count

    if not channel_breakdown:
        channel_breakdown = {'No Data': 1}

    channel_breakdown_labels = list(channel_breakdown.keys())
    channel_breakdown_data = list(channel_breakdown.values())

    status_breakdown_labels = ['Paid', 'Pending', 'Failed']
    status_breakdown_data = [
        successful_transactions,
        pending_transactions,
        failed_transactions
    ]

    return render_template(
        'school_admin/finance_dashboard.html',
        subscription=sub,
        current_plan=plan,
        student_count=student_count,
        device_count=device_count,
        student_pct=student_pct,
        device_pct=device_pct,
        days_remaining=days_remaining,
        renewal_amount=renewal_amount,
        total_spent=round(total_spent, 2),
        avg_payment=avg_payment,
        total_transactions=total_transactions,
        successful_transactions=successful_transactions,
        pending_transactions=pending_transactions,
        failed_transactions=failed_transactions,
        success_rate=success_rate,
        last_successful_payment=last_successful_payment,
        monthly_spend_labels=monthly_spend_labels,
        monthly_spend_data=monthly_spend_data,
        channel_breakdown_labels=channel_breakdown_labels,
        channel_breakdown_data=channel_breakdown_data,
        status_breakdown_labels=status_breakdown_labels,
        status_breakdown_data=status_breakdown_data,
        transactions=transactions
    )








# from flask import Blueprint, render_template
# from flask_login import login_required, current_user
# from app.models.billing import SchoolSubscription
# from app.models.billing import PaymentTransaction
# from app.models.billing import Plan
# from app.models.student import Student
# from app.models.scanner_device import ScannerDevice

# # Registering under 'finance' to match your nav link
# finance_bp = Blueprint('finance', __name__) 

# @finance_bp.route('/billing-dashboard')
# @login_required
# def school_finance_page():
#     # Get active subscription and current plan
#     sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
#     plan = Plan.query.get(sub.plan_id) if sub else None
    
#     # Calculate limits/usage
#     student_count = Student.query.filter_by(school_id=current_user.school_id).count()
#     device_count = ScannerDevice.query.filter_by(school_id=current_user.school_id).count()
    
#     # Get payment history
#     transactions = PaymentTransaction.query.filter_by(school_id=current_user.school_id)\
#                    .order_by(PaymentTransaction.paid_at.desc()).limit(10).all()
                   
#     return render_template('school_admin/finance_dashboard.html',
#                            subscription=sub,
#                            current_plan=plan,
#                            student_count=student_count,
#                            device_count=device_count,
#                            transactions=transactions)