from datetime import datetime, timedelta
import calendar
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.billing import PaymentTransaction, SchoolSubscription, Plan
from app.models.school import School
from app.models.coupon import Coupon

superadmin_finance_bp = Blueprint('superadmin_finance', __name__)


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _shift_month(dt: datetime, months_back: int) -> datetime:
    year = dt.year
    month = dt.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


@superadmin_finance_bp.route('/admin/finance/dashboard', methods=['GET'])
@login_required
def finance_dashboard():
    if current_user.role != 'super_admin':
        return "Unauthorized", 403

    total_schools = School.query.count()
    active_subscriptions = SchoolSubscription.query.filter(
        SchoolSubscription.status.in_(['active', 'trialing'])
    ).count()
    paying_schools = SchoolSubscription.query.filter_by(status='active').count()

    total_revenue = (
        db.session.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0))
        .filter(PaymentTransaction.status == 'success')
        .scalar()
        or 0.0
    )

    total_transactions = PaymentTransaction.query.count()
    successful_transactions = PaymentTransaction.query.filter_by(status='success').count()
    failed_transactions = PaymentTransaction.query.filter_by(status='failed').count()
    pending_transactions = PaymentTransaction.query.filter_by(status='pending').count()

    conversion_rate = round((paying_schools / total_schools) * 100, 2) if total_schools else 0.0
    success_rate = round((successful_transactions / total_transactions) * 100, 2) if total_transactions else 0.0
    avg_revenue_per_paying_school = round(total_revenue / paying_schools, 2) if paying_schools else 0.0

    mrr = 0.0
    active_subs = SchoolSubscription.query.filter_by(status='active').all()
    for sub in active_subs:
        if sub.plan:
            if sub.billing_cycle == 'monthly':
                mrr += sub.plan.price_monthly
            elif sub.billing_cycle == 'annual':
                mrr += (sub.plan.price_annual / 12)
            elif sub.billing_cycle == 'termly':
                mrr += (sub.plan.price_monthly * 4) / 12

    current_month_start = _month_start(datetime.utcnow())
    month_points = [_shift_month(current_month_start, i) for i in range(5, -1, -1)]
    month_keys = [(d.year, d.month) for d in month_points]
    monthly_revenue_labels = [f"{calendar.month_abbr[d.month]} {str(d.year)[-2:]}" for d in month_points]
    revenue_map = {key: 0.0 for key in month_keys}

    revenue_transactions = PaymentTransaction.query.filter(
        PaymentTransaction.status == 'success',
        PaymentTransaction.created_at >= month_points[0]
    ).all()

    for txn in revenue_transactions:
        txn_date = txn.paid_at or txn.created_at
        key = (txn_date.year, txn_date.month)
        if key in revenue_map:
            revenue_map[key] += float(txn.amount or 0)

    monthly_revenue_data = [round(revenue_map[key], 2) for key in month_keys]

    current_month_revenue = monthly_revenue_data[-1] if monthly_revenue_data else 0.0
    previous_month_revenue = monthly_revenue_data[-2] if len(monthly_revenue_data) > 1 else 0.0
    if previous_month_revenue > 0:
        revenue_growth_pct = round(((current_month_revenue - previous_month_revenue) / previous_month_revenue) * 100, 2)
    else:
        revenue_growth_pct = 100.0 if current_month_revenue > 0 else 0.0

    channel_rows = (
        db.session.query(PaymentTransaction.channel, func.count(PaymentTransaction.id))
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

    status_breakdown_map = {
        'success': successful_transactions,
        'pending': pending_transactions,
        'failed': failed_transactions
    }
    status_breakdown_labels = ['Paid', 'Pending', 'Failed']
    status_breakdown_data = [
        status_breakdown_map['success'],
        status_breakdown_map['pending'],
        status_breakdown_map['failed']
    ]

    plan_distribution_rows = (
        db.session.query(Plan.name, func.count(SchoolSubscription.id))
        .join(SchoolSubscription, Plan.id == SchoolSubscription.plan_id)
        .filter(SchoolSubscription.status == 'active')
        .group_by(Plan.name)
        .all()
    )
    plan_distribution_labels = [row[0] for row in plan_distribution_rows] or ['No Active Plans']
    plan_distribution_data = [row[1] for row in plan_distribution_rows] or [1]

    top_school_rows = (
        db.session.query(
            School.name,
            func.coalesce(func.sum(PaymentTransaction.amount), 0.0).label('revenue_total')
        )
        .join(PaymentTransaction, PaymentTransaction.school_id == School.id)
        .filter(PaymentTransaction.status == 'success')
        .group_by(School.id, School.name)
        .order_by(func.sum(PaymentTransaction.amount).desc())
        .limit(5)
        .all()
    )
    top_school_labels = [row[0] for row in top_school_rows] or ['No Data']
    top_school_data = [round(float(row[1] or 0), 2) for row in top_school_rows] or [0.0]

    recent_transactions = (
        PaymentTransaction.query
        .options(joinedload(PaymentTransaction.school))
        .order_by(PaymentTransaction.created_at.desc())
        .limit(50)
        .all()
    )

    plans = Plan.query.order_by(Plan.price_monthly.asc()).all()
    coupons = Coupon.query.order_by(Coupon.id.desc()).all()

    return render_template(
        'superadmin/finance_dashboard.html',
        total_schools=total_schools,
        active_subscriptions=active_subscriptions,
        paying_schools=paying_schools,
        total_revenue=total_revenue,
        total_transactions=total_transactions,
        successful_transactions=successful_transactions,
        failed_transactions=failed_transactions,
        pending_transactions=pending_transactions,
        conversion_rate=conversion_rate,
        success_rate=success_rate,
        avg_revenue_per_paying_school=avg_revenue_per_paying_school,
        mrr=round(mrr, 2),
        revenue_growth_pct=revenue_growth_pct,
        current_month_revenue=current_month_revenue,
        previous_month_revenue=previous_month_revenue,
        monthly_revenue_labels=monthly_revenue_labels,
        monthly_revenue_data=monthly_revenue_data,
        channel_breakdown_labels=channel_breakdown_labels,
        channel_breakdown_data=channel_breakdown_data,
        status_breakdown_labels=status_breakdown_labels,
        status_breakdown_data=status_breakdown_data,
        plan_distribution_labels=plan_distribution_labels,
        plan_distribution_data=plan_distribution_data,
        top_school_labels=top_school_labels,
        top_school_data=top_school_data,
        recent_transactions=recent_transactions,
        plans=plans,
        coupons=coupons
    )


@superadmin_finance_bp.route('/admin/finance/plan/update/<int:plan_id>', methods=['POST'])
@login_required
def update_plan_pricing(plan_id):
    if current_user.role != 'super_admin':
        return "Unauthorized", 403

    plan = Plan.query.get_or_404(plan_id)

    plan.price_monthly = float(request.form.get('price_monthly'))
    plan.price_annual = float(request.form.get('price_annual'))
    plan.student_limit = int(request.form.get('student_limit', plan.student_limit))
    plan.scanner_limit = int(request.form.get('scanner_limit', plan.scanner_limit))

    plan.whatsapp_enabled = 'whatsapp_enabled' in request.form
    plan.sms_enabled = 'sms_enabled' in request.form
    plan.gps_enabled = 'gps_enabled' in request.form
    plan.complaints_enabled = 'complaints_enabled' in request.form

    db.session.commit()
    flash(f"{plan.name} Package updated successfully globally.", "success")
    return redirect(url_for('superadmin_finance.finance_dashboard'))


@superadmin_finance_bp.route('/admin/finance/coupon/create', methods=['POST'])
@login_required
def create_coupon():
    if current_user.role != 'super_admin':
        return "Unauthorized", 403

    new_coupon = Coupon(
        code=request.form.get('code').upper().strip(),
        discount_percentage=float(request.form.get('discount_percentage')),
        usage_limit=int(request.form.get('usage_limit', -1))
    )
    db.session.add(new_coupon)
    db.session.commit()
    flash(f"Promo Code {new_coupon.code} created and live!", "success")
    return redirect(url_for('superadmin_finance.finance_dashboard'))


















# from datetime import datetime, timedelta
# from flask import Blueprint, render_template
# from flask_login import current_user, login_required
# from sqlalchemy import func
# from app.extensions import db
# # Strictly adhering to your structure
# from app.models.billing import PaymentTransaction
# from app.models.billing import SchoolSubscription
# from app.models.billing import Plan
# from app.models.school import School
# from flask import request, redirect, url_for, flash
# from app.models.coupon import Coupon
# from sqlalchemy.orm import joinedload


# superadmin_finance_bp = Blueprint('superadmin_finance', __name__)

# # Add a decorator here if you have a @superadmin_required custom wrapper
# # @superadmin_finance_bp.route('/admin/finance/dashboard', methods=['GET'])
# # @login_required
# # def finance_dashboard():
# #     # 1. Active & Paying Schools
# #     total_schools = School.query.count()
# #     active_subscriptions = SchoolSubscription.query.filter(
# #         SchoolSubscription.status.in_(['active', 'trialing'])
# #     ).count()
# #     paying_schools = SchoolSubscription.query.filter_by(status='active').count()

# #     # 2. Revenue Calculations (Total collected)
# #     total_revenue_query = db.session.query(func.sum(PaymentTransaction.amount)).filter_by(status='success').scalar()
# #     total_revenue = total_revenue_query or 0.0

# #     # 3. MRR Estimate (Monthly Recurring Revenue)
# #     # Sum of all active monthly plans + (active annual plans / 12)
# #     # This is a simplified MRR calculation for the dashboard
# #     mrr = 0.0
# #     active_subs = SchoolSubscription.query.filter_by(status='active').all()
# #     for sub in active_subs:
# #         if sub.plan:
# #             if sub.billing_cycle == 'monthly':
# #                 mrr += sub.plan.price_monthly
# #             elif sub.billing_cycle == 'annual':
# #                 mrr += (sub.plan.price_annual / 12)
# #             elif sub.billing_cycle == 'termly':
# #                 mrr += (sub.plan.price_monthly * 4) / 12 # Rough average

# #     # 4. Recent Transactions (Last 30 days)
# #     thirty_days_ago = datetime.utcnow() - timedelta(days=30)
# #     recent_transactions = PaymentTransaction.query.filter(
# #         PaymentTransaction.created_at >= thirty_days_ago
# #     ).order_by(PaymentTransaction.created_at.desc()).limit(10).all()
    
# #     plans = Plan.query.order_by(Plan.price_monthly.asc()).all()
# #     coupons = Coupon.query.order_by(Coupon.id.desc()).all()

# #     # 5. Plan Distribution (How many schools on Starter vs Premium)
# #     plan_distribution = db.session.query(
# #         Plan.name, func.count(SchoolSubscription.id)
# #     ).join(SchoolSubscription, Plan.id == SchoolSubscription.plan_id)\
# #      .filter(SchoolSubscription.status == 'active')\
# #      .group_by(Plan.name).all()

# #     return render_template('superadmin/finance_dashboard.html',
# #                            total_schools=total_schools,
# #                            active_subscriptions=active_subscriptions,
# #                            paying_schools=paying_schools,
# #                            total_revenue=total_revenue,
# #                            mrr=mrr,
# #                            recent_transactions=recent_transactions,
# #                            plans=plans,
# #                            coupons=coupons,
# #                            plan_distribution=plan_distribution)


# @superadmin_finance_bp.route('/admin/finance/dashboard', methods=['GET'])
# @login_required
# def finance_dashboard():
#     total_schools = School.query.count()
#     active_subscriptions = SchoolSubscription.query.filter(
#         SchoolSubscription.status.in_(['active', 'trialing'])
#     ).count()
#     paying_schools = SchoolSubscription.query.filter_by(status='active').count()

#     total_revenue_query = db.session.query(func.sum(PaymentTransaction.amount)).filter_by(status='success').scalar()
#     total_revenue = total_revenue_query or 0.0

#     mrr = 0.0
#     active_subs = SchoolSubscription.query.filter_by(status='active').all()
#     for sub in active_subs:
#         if sub.plan:
#             if sub.billing_cycle == 'monthly':
#                 mrr += sub.plan.price_monthly
#             elif sub.billing_cycle == 'annual':
#                 mrr += (sub.plan.price_annual / 12)
#             elif sub.billing_cycle == 'termly':
#                 mrr += (sub.plan.price_monthly * 4) / 12

#     thirty_days_ago = datetime.utcnow() - timedelta(days=30)
#     recent_transactions = (
#         PaymentTransaction.query
#         .options(joinedload(PaymentTransaction.school))
#         .filter(PaymentTransaction.created_at >= thirty_days_ago)
#         .order_by(PaymentTransaction.created_at.desc())
#         .limit(10)
#         .all()
#     )
    
#     plans = Plan.query.order_by(Plan.price_monthly.asc()).all()
#     coupons = Coupon.query.order_by(Coupon.id.desc()).all()

#     plan_distribution = db.session.query(
#         Plan.name, func.count(SchoolSubscription.id)
#     ).join(SchoolSubscription, Plan.id == SchoolSubscription.plan_id)\
#      .filter(SchoolSubscription.status == 'active')\
#      .group_by(Plan.name).all()

#     return render_template(
#         'superadmin/finance_dashboard.html',
#         total_schools=total_schools,
#         active_subscriptions=active_subscriptions,
#         paying_schools=paying_schools,
#         total_revenue=total_revenue,
#         mrr=mrr,
#         recent_transactions=recent_transactions,
#         plans=plans,
#         coupons=coupons,
#         plan_distribution=plan_distribution
#     )

# @superadmin_finance_bp.route('/admin/finance/plan/update/<int:plan_id>', methods=['POST'])
# @login_required
# def update_plan_pricing(plan_id):
#     """Allows Super Admin to instantly change prices AND features of a plan"""
#     if current_user.role != 'super_admin':
#         return "Unauthorized", 403
        
#     plan = Plan.query.get_or_404(plan_id)
    
#     # Update Prices
#     plan.price_monthly = float(request.form.get('price_monthly'))
#     plan.price_annual = float(request.form.get('price_annual'))
    
#     plan.student_limit = int(request.form.get('student_limit', plan.student_limit))
#     plan.scanner_limit = int(request.form.get('scanner_limit', plan.scanner_limit))
    
#     # Update Features (Checkboxes only send data if they are checked)
#     plan.whatsapp_enabled = 'whatsapp_enabled' in request.form
#     plan.sms_enabled = 'sms_enabled' in request.form
#     plan.gps_enabled = 'gps_enabled' in request.form
    
    
#     db.session.commit()
#     flash(f"{plan.name} Package updated successfully globally.", "success")
#     return redirect(url_for('superadmin_finance.finance_dashboard'))

# @superadmin_finance_bp.route('/admin/finance/coupon/create', methods=['POST'])
# @login_required
# def create_coupon():
#     """Allows Super Admin to generate a Promo Code"""
#     if current_user.role != 'super_admin':
#         return "Unauthorized", 403
        
#     new_coupon = Coupon(
#         code=request.form.get('code').upper().strip(),
#         discount_percentage=float(request.form.get('discount_percentage')),
#         usage_limit=int(request.form.get('usage_limit', -1))
#     )
#     db.session.add(new_coupon)
#     db.session.commit()
#     flash(f"Promo Code {new_coupon.code} created and live!", "success")
#     return redirect(url_for('superadmin_finance.finance_dashboard'))