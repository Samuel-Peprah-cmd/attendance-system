import uuid
import traceback
from flask import Blueprint, flash, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
# Strictly adhering to your structure
from app.models.billing import PaymentTransaction, Plan
from app.models.billing import SchoolSubscription
from app.services.paystack_service import PaystackService
from app.models.coupon import Coupon
from datetime import datetime, timedelta

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/pricing', methods=['GET'])
@login_required
def pricing_page():
    try:
        """Displays the Starter, Growth, Premium, Enterprise plans"""
        # Suspect 1: Does the Plan table actually have an 'is_active' column?
        plans = Plan.query.filter_by(is_active=True).all()
        
        current_sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
        
        # Suspect 2: Is the HTML template crashing because current_sub is None?
        return render_template('billing/pricing.html', plans=plans, current_sub=current_sub)
        
    except Exception as e:
        # 🚨 This will print the EXACT crash reason directly onto your screen!
        return f"<h1>Pricing Page Crash:</h1><pre>{traceback.format_exc()}</pre>", 500

@billing_bp.route('/promo/validate', methods=['POST'])
@login_required
def validate_promo():
    """Returns the discount calculation without committing the usage"""
    data = request.get_json()
    code = data.get('code', '').strip().upper()
    plan_id = data.get('plan_id')
    cycle = data.get('cycle', 'monthly')

    plan = Plan.query.get(plan_id)
    coupon = Coupon.query.filter_by(code=code, is_active=True).first()

    if not coupon:
        return jsonify({"success": False, "message": "Invalid promo code."}), 404

    # Check Expiry
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        return jsonify({"success": False, "message": "This code has expired."}), 400

    # Check Usage Limit
    if coupon.usage_limit != -1 and coupon.times_used >= coupon.usage_limit:
        return jsonify({"success": False, "message": "Usage limit reached."}), 400

    # Calculate Savings
    base_price = plan.price_annual if cycle == 'annual' else plan.price_monthly
    savings = base_price * (coupon.discount_percentage / 100)
    new_total = base_price - savings

    return jsonify({
        "success": True,
        "discount_percent": coupon.discount_percentage,
        "savings": round(savings, 2),
        "new_total": round(new_total, 2)
    })

@billing_bp.route('/checkout/initialize', methods=['POST'])
@login_required
def initialize_checkout():
    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id')
    billing_cycle = data.get('billing_cycle')
    promo_code_input = data.get('promo_code', '').strip().upper() 
    
    plan = Plan.query.get_or_404(plan_id)
    amount = plan.price_annual if billing_cycle == 'annual' else plan.price_monthly
    
    # 🚨 PROMO CODE LOGIC
    if promo_code_input:
        coupon = Coupon.query.filter_by(code=promo_code_input, is_active=True).first()
        
        if coupon:
            # Check Expiry
            if coupon.expires_at and coupon.expires_at < datetime.utcnow():
                return jsonify({"success": False, "message": "This promo code has expired."}), 400
            
            # Check Usage Limit
            if coupon.usage_limit != -1 and coupon.times_used >= coupon.usage_limit:
                return jsonify({"success": False, "message": "This promo code has reached its usage limit."}), 400
                
            # Apply discount
            discount = amount * (coupon.discount_percentage / 100)
            amount -= discount
            
            # Commit usage
            coupon.times_used += 1
            db.session.commit()
        else:
            return jsonify({"success": False, "message": "Invalid promo code."}), 400

    # Paystack Initialization
    reference = f"SUB_{current_user.school_id}_{uuid.uuid4().hex[:10]}"
    metadata = {
        "school_id": current_user.school_id,
        "plan_id": plan.id,
        "billing_cycle": billing_cycle,
        "promo_used": promo_code_input if promo_code_input else "None"
    }
    
    paystack_data = PaystackService.initialize_transaction(
        email=current_user.email,
        amount_ghs=amount, 
        reference=reference,
        metadata=metadata,
        callback_url=url_for('billing.checkout_callback', _external=True)
    )
    
    if paystack_data and 'authorization_url' in paystack_data:
        return jsonify({"success": True, "checkout_url": paystack_data['authorization_url']})
    
    return jsonify({"success": False, "message": "Gateway connection failed."}), 500

@billing_bp.route('/checkout/callback', methods=['GET'])
@login_required
def checkout_callback():
    reference = request.args.get('reference')
    if not reference:
        return redirect(url_for('billing.pricing_page'))

    paystack_data = PaystackService.verify_transaction(reference)
    
    if paystack_data and paystack_data.get('status') == 'success':
        # Paystack verification puts the ID inside the 'data' key
        actual_txn_info = paystack_data.get('data', paystack_data)
        
        metadata = actual_txn_info.get('metadata', {})
        plan_id = metadata.get('plan_id')
        billing_cycle = metadata.get('billing_cycle', 'monthly')
        
        # ALWAYS Upgrade Subscription
        sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
        if sub and plan_id:
            sub.plan_id = plan_id
            sub.status = 'active'
            sub.billing_cycle = billing_cycle
            sub.start_date = datetime.utcnow()
            days = 365 if billing_cycle == 'annual' else 30
            sub.end_date = sub.start_date + timedelta(days=days)

        # Handle Transaction Ledger
        existing_txn = PaymentTransaction.query.filter_by(provider_reference=reference).first()
        if not existing_txn:
            new_txn = PaymentTransaction(
                school_id=current_user.school_id,
                subscription_id=sub.id if sub else None,
                amount=actual_txn_info.get('amount') / 100, 
                provider_reference=reference,
                status='success',
                paid_at=datetime.utcnow(),
                metadata_json=actual_txn_info # 🚨 SAVES THE NESTED DATA (Fixes Receipt)
            )
            db.session.add(new_txn)
        else:
            # Update existing record with the full data if it was missing
            existing_txn.metadata_json = actual_txn_info
            existing_txn.status = 'success'
        
        db.session.commit()

    return render_template('billing/checkout_success.html', reference=reference)