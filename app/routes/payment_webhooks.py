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
from app.extensions import csrf


webhook_bp = Blueprint('webhooks', __name__)

@csrf.exempt
@webhook_bp.route('/paystack/webhook', methods=['POST'])
def paystack_webhook():
    payload = request.json
    
    # Paystack sends different events, we only care when a charge is successful
    if payload and payload.get('event') == 'charge.success':
        data = payload.get('data', {})
        reference = data.get('reference')
        
        # 1. Check if we already processed this
        existing_txn = PaymentTransaction.query.filter_by(provider_reference=reference).first()
        
        if not existing_txn:
            # It's a new payment! Let's get the metadata
            metadata = data.get('metadata', {})
            school_id = metadata.get('school_id')
            plan_id = metadata.get('plan_id')
            billing_cycle = metadata.get('billing_cycle', 'monthly')
            
            # 2. UPGRADE THE PLAN (Unlock the padlocks!)
            sub = None
            if school_id and plan_id:
                sub = SchoolSubscription.query.filter_by(school_id=school_id).first()
                if sub:
                    sub.plan_id = plan_id
                    sub.status = 'active'
                    sub.billing_cycle = billing_cycle
                    sub.start_date = datetime.utcnow()
                    
                    # Do the date math
                    if billing_cycle == 'annual':
                        sub.end_date = sub.start_date + timedelta(days=365)
                    elif billing_cycle == 'termly':
                        sub.end_date = sub.start_date + timedelta(days=120)
                    else:
                        sub.end_date = sub.start_date + timedelta(days=30)
            
            # 3. Save the Transaction Ledger
            new_txn = PaymentTransaction(
                school_id=school_id,
                subscription_id=sub.id if sub else None,
                amount=data.get('amount') / 100,  # Pesewas to GHS
                currency=data.get('currency'),
                channel=data.get('channel'),
                provider='paystack',
                provider_reference=reference,
                provider_status='success',
                status='success',
                paid_at=datetime.utcnow(),
                metadata_json=data
            )
            
            db.session.add(new_txn)
            db.session.commit()
            print(f"✅ WEBHOOK SUCCESS: School {school_id} upgraded to Plan {plan_id}!")

    # Always return 200 OK so Paystack knows we received it
    return jsonify({"status": "success"}), 200