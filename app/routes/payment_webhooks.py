import hmac
import hashlib
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from app.extensions import db
from app.services.paystack_service import PaystackService

# Strictly importing from your defined models structure
from app.models.billing import PaymentTransaction
from app.models.billing import SchoolSubscription

webhook_bp = Blueprint('webhooks', __name__)

@webhook_bp.route('/paystack/webhook', methods=['POST'])
def paystack_webhook():
    secret = os.environ.get('PAYSTACK_SECRET_KEY')
    signature = request.headers.get('x-paystack-signature')
    payload = request.get_data()

    # 1. Security Check: Ensure the request is actually from Paystack
    hash_calc = hmac.new(secret.encode('utf-8'), payload, hashlib.sha512).hexdigest()
    if hash_calc != signature:
        return jsonify({"status": "error", "message": "Invalid signature"}), 400

    event_data = request.json
    event_type = event_data.get('event')
    data = event_data.get('data', {})

    # 2. Handle Successful Payment
    if event_type == 'charge.success':
        reference = data.get('reference')
        
        # Prevent duplicate processing
        if PaymentTransaction.query.filter_by(provider_reference=reference).first():
            return jsonify({"status": "ignored", "message": "Already processed"}), 200

        metadata = data.get('metadata', {})
        school_id = metadata.get('school_id')
        plan_id = metadata.get('plan_id')
        billing_cycle = metadata.get('billing_cycle', 'monthly')

        # 3. Log the Transaction for Super Admin Analytics
        sub = SchoolSubscription.query.filter_by(school_id=school_id).first()
        
        new_txn = PaymentTransaction(
            school_id=school_id,
            subscription_id=sub.id if sub else None,
            amount=data.get('amount') / 100,
            currency=data.get('currency'),
            channel=data.get('channel'),
            provider='paystack',
            provider_reference=reference,
            provider_status=data.get('status'),
            status='success',
            paid_at=datetime.utcnow(),
            metadata_json=data
        )
        db.session.add(new_txn)

        # 4. Update the School's Plan and Dates
        if sub:
            sub.plan_id = plan_id
            sub.status = 'active'
            sub.billing_cycle = billing_cycle
            sub.start_date = datetime.utcnow()
            
            if billing_cycle == 'annual':
                sub.end_date = sub.start_date + timedelta(days=365)
            elif billing_cycle == 'termly':
                sub.end_date = sub.start_date + timedelta(days=120)
            else:
                sub.end_date = sub.start_date + timedelta(days=30)
                
            # Save auth code for recurring card charges
            if 'authorization' in data:
                sub.provider_authorization_code = data['authorization'].get('authorization_code')

        db.session.commit()

    return jsonify({"status": "success"}), 200