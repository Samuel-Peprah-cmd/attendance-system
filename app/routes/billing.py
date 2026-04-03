import uuid
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db

# Strictly adhering to your structure
from app.models.billing import Plan
from app.models.billing import SchoolSubscription
from app.services.paystack_service import PaystackService

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/pricing', methods=['GET'])
@login_required
def pricing_page():
    """Displays the Starter, Growth, Premium, Enterprise plans"""
    plans = Plan.query.filter_by(is_active=True).all()
    current_sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
    
    return render_template('billing/pricing.html', plans=plans, current_sub=current_sub)

from app.models.coupon import Coupon
from datetime import datetime

@billing_bp.route('/checkout/initialize', methods=['POST'])
@login_required
def initialize_checkout():
    data = request.json
    plan_id = data.get('plan_id')
    billing_cycle = data.get('billing_cycle')
    promo_code_input = data.get('promo_code') # The new promo code field
    
    plan = Plan.query.get_or_404(plan_id)
    amount = plan.price_annual if billing_cycle == 'annual' else plan.price_monthly
    
    # --- PROMO CODE LOGIC ---
    if promo_code_input:
        coupon = Coupon.query.filter_by(code=promo_code_input.upper(), is_active=True).first()
        
        # Validate the coupon
        if coupon:
            is_valid = True
            if coupon.expires_at and coupon.expires_at < datetime.utcnow():
                is_valid = False
            if coupon.usage_limit != -1 and coupon.times_used >= coupon.usage_limit:
                is_valid = False
                
            if is_valid:
                # Apply the discount math!
                discount_amount = amount * (coupon.discount_percentage / 100)
                amount = amount - discount_amount
                
                # Increment the usage counter
                coupon.times_used += 1
                db.session.commit()
    # ------------------------

    # Generate reference and pass to Paystack (same as before)
    reference = f"SUB_{current_user.school_id}_{uuid.uuid4().hex[:10]}"
    metadata = {
        "school_id": current_user.school_id,
        "plan_id": plan.id,
        "billing_cycle": billing_cycle
    }
    
    paystack_data = PaystackService.initialize_transaction(
        email=current_user.email,
        amount_ghs=amount, # Paystack now gets the heavily discounted amount!
        reference=reference,
        metadata=metadata
    )
    
    if paystack_data and 'authorization_url' in paystack_data:
        return jsonify({"success": True, "checkout_url": paystack_data['authorization_url']})
    return jsonify({"success": False, "message": "Failed to connect to gateway."}), 500

@billing_bp.route('/checkout/callback', methods=['GET'])
@login_required
def checkout_callback():
    """Where Paystack redirects the user AFTER they pay"""
    # Note: The actual database update is handled securely by the Webhook.
    # This route is just to show the user a "Success" page.
    reference = request.args.get('reference')
    return render_template('billing/checkout_success.html', reference=reference)