from flask import render_template, Blueprint
from app.models.billing import Plan
from flask_login import login_required, current_user

views_bp = Blueprint('views', __name__)

@views_bp.route('/pricing')
@login_required
def pricing_page():
    # Fetch active plans ordered by price
    plans = Plan.query.filter_by(is_active=True).order_by(Plan.price_monthly.asc()).all()
    
    # Check if user already has a subscription to show "Current Plan" status
    current_sub = current_user.school.subscription if current_user.school else None
    
    return render_template('billing/pricing.html', 
                           plans=plans, 
                           current_sub=current_sub)