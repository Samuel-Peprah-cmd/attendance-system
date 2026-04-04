from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func
from app.extensions import db
# Strictly adhering to your structure
from app.models.billing import PaymentTransaction
from app.models.billing import SchoolSubscription
from app.models.billing import Plan
from app.models.school import School # Assuming standard school model exists
from flask import request, redirect, url_for, flash
from app.models.coupon import Coupon

superadmin_finance_bp = Blueprint('superadmin_finance', __name__)

# Add a decorator here if you have a @superadmin_required custom wrapper
@superadmin_finance_bp.route('/admin/finance/dashboard', methods=['GET'])
@login_required
def finance_dashboard():
    # 1. Active & Paying Schools
    total_schools = School.query.count()
    active_subscriptions = SchoolSubscription.query.filter(
        SchoolSubscription.status.in_(['active', 'trialing'])
    ).count()
    paying_schools = SchoolSubscription.query.filter_by(status='active').count()

    # 2. Revenue Calculations (Total collected)
    total_revenue_query = db.session.query(func.sum(PaymentTransaction.amount)).filter_by(status='success').scalar()
    total_revenue = total_revenue_query or 0.0

    # 3. MRR Estimate (Monthly Recurring Revenue)
    # Sum of all active monthly plans + (active annual plans / 12)
    # This is a simplified MRR calculation for the dashboard
    mrr = 0.0
    active_subs = SchoolSubscription.query.filter_by(status='active').all()
    for sub in active_subs:
        if sub.plan:
            if sub.billing_cycle == 'monthly':
                mrr += sub.plan.price_monthly
            elif sub.billing_cycle == 'annual':
                mrr += (sub.plan.price_annual / 12)
            elif sub.billing_cycle == 'termly':
                mrr += (sub.plan.price_monthly * 4) / 12 # Rough average

    # 4. Recent Transactions (Last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_transactions = PaymentTransaction.query.filter(
        PaymentTransaction.created_at >= thirty_days_ago
    ).order_by(PaymentTransaction.created_at.desc()).limit(10).all()
    
    plans = Plan.query.order_by(Plan.price_monthly.asc()).all()
    coupons = Coupon.query.order_by(Coupon.id.desc()).all()

    # 5. Plan Distribution (How many schools on Starter vs Premium)
    plan_distribution = db.session.query(
        Plan.name, func.count(SchoolSubscription.id)
    ).join(SchoolSubscription, Plan.id == SchoolSubscription.plan_id)\
     .filter(SchoolSubscription.status == 'active')\
     .group_by(Plan.name).all()

    return render_template('superadmin/finance_dashboard.html',
                           total_schools=total_schools,
                           active_subscriptions=active_subscriptions,
                           paying_schools=paying_schools,
                           total_revenue=total_revenue,
                           mrr=mrr,
                           recent_transactions=recent_transactions,
                           plans=plans,
                           coupons=coupons,
                           plan_distribution=plan_distribution)

@superadmin_finance_bp.route('/admin/finance/plan/update/<int:plan_id>', methods=['POST'])
@login_required
def update_plan_pricing(plan_id):
    """Allows Super Admin to instantly change prices AND features of a plan"""
    if current_user.role != 'super_admin':
        return "Unauthorized", 403
        
    plan = Plan.query.get_or_404(plan_id)
    
    # Update Prices
    plan.price_monthly = float(request.form.get('price_monthly'))
    plan.price_annual = float(request.form.get('price_annual'))
    
    # Update Features (Checkboxes only send data if they are checked)
    plan.whatsapp_enabled = 'whatsapp_enabled' in request.form
    plan.sms_enabled = 'sms_enabled' in request.form
    plan.gps_enabled = 'gps_enabled' in request.form
    
    # You can also add limits here if you want!
    # plan.student_limit = int(request.form.get('student_limit', -1))
    
    db.session.commit()
    flash(f"{plan.name} Package updated successfully globally.", "success")
    return redirect(url_for('superadmin_finance.finance_dashboard'))

@superadmin_finance_bp.route('/admin/finance/coupon/create', methods=['POST'])
@login_required
def create_coupon():
    """Allows Super Admin to generate a Promo Code"""
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