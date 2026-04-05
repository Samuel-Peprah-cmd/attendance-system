import hmac
import hashlib
import os
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from app.extensions import db, csrf
from app.models.billing import PaymentTransaction, SchoolSubscription

webhook_bp = Blueprint('webhooks', __name__)

def parse_paystack_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None

@csrf.exempt
@webhook_bp.route('/paystack/webhook', methods=['POST'])
def paystack_webhook():
    raw_body = request.get_data()
    signature = request.headers.get('x-paystack-signature', '')
    secret = os.environ.get('PAYSTACK_SECRET_KEY', '')

    if not secret:
        return jsonify({"status": "error", "message": "Missing PAYSTACK_SECRET_KEY"}), 500

    computed_signature = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, signature):
        return jsonify({"status": "error", "message": "Invalid signature"}), 400

    payload = request.get_json(silent=True) or {}

    if payload.get('event') != 'charge.success':
        return jsonify({"status": "ignored"}), 200

    data = payload.get('data', {})
    reference = data.get('reference')
    if not reference:
        return jsonify({"status": "ignored", "message": "Missing reference"}), 200

    metadata = data.get('metadata') or {}
    school_id = metadata.get('school_id')
    plan_id = metadata.get('plan_id')
    billing_cycle = metadata.get('billing_cycle', 'monthly')

    sub = None
    if school_id:
        sub = SchoolSubscription.query.filter_by(school_id=school_id).first()

    if sub and plan_id:
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

    txn = PaymentTransaction.query.filter_by(provider_reference=reference).first()

    if not txn:
        if not sub:
            return jsonify({"status": "error", "message": "Subscription not found"}), 200

        txn = PaymentTransaction(
            school_id=school_id,
            subscription_id=sub.id,
            invoice_id=metadata.get('invoice_id'),
            provider='paystack',
            provider_reference=reference
        )
        db.session.add(txn)

    txn.amount = (data.get('amount') or 0) / 100
    txn.currency = data.get('currency') or 'GHS'
    txn.channel = data.get('channel') or (data.get('authorization') or {}).get('channel')
    txn.provider_status = data.get('status')
    txn.status = 'success' if data.get('status') == 'success' else (data.get('status') or 'pending')
    txn.paid_at = parse_paystack_datetime(data.get('paid_at')) or datetime.utcnow()
    txn.metadata_json = data

    if sub and not txn.subscription_id:
        txn.subscription_id = sub.id

    db.session.commit()

    print(f"✅ WEBHOOK SUCCESS: reference={reference}, school_id={school_id}, channel={txn.channel}")
    return jsonify({"status": "success"}), 200








# import hmac
# import hashlib
# import os
# from datetime import datetime, timedelta
# from flask import Blueprint, request, jsonify
# from app.extensions import db
# from app.services.paystack_service import PaystackService

# # Strictly importing from your defined models structure
# from app.models.billing import PaymentTransaction
# from app.models.billing import SchoolSubscription
# from app.extensions import csrf


# webhook_bp = Blueprint('webhooks', __name__)

# @csrf.exempt
# @webhook_bp.route('/paystack/webhook', methods=['POST'])
# def paystack_webhook():
#     payload = request.json
    
#     # Paystack sends different events, we only care when a charge is successful
#     if payload and payload.get('event') == 'charge.success':
#         data = payload.get('data', {})
#         reference = data.get('reference')
        
#         # 1. Check if we already processed this
#         existing_txn = PaymentTransaction.query.filter_by(provider_reference=reference).first()
        
#         if not existing_txn:
#             # It's a new payment! Let's get the metadata
#             metadata = data.get('metadata', {})
#             school_id = metadata.get('school_id')
#             plan_id = metadata.get('plan_id')
#             billing_cycle = metadata.get('billing_cycle', 'monthly')
            
#             # 2. UPGRADE THE PLAN (Unlock the padlocks!)
#             sub = None
#             if school_id and plan_id:
#                 sub = SchoolSubscription.query.filter_by(school_id=school_id).first()
#                 if sub:
#                     sub.plan_id = plan_id
#                     sub.status = 'active'
#                     sub.billing_cycle = billing_cycle
#                     sub.start_date = datetime.utcnow()
                    
#                     # Do the date math
#                     if billing_cycle == 'annual':
#                         sub.end_date = sub.start_date + timedelta(days=365)
#                     elif billing_cycle == 'termly':
#                         sub.end_date = sub.start_date + timedelta(days=120)
#                     else:
#                         sub.end_date = sub.start_date + timedelta(days=30)
            
#             # 3. Save the Transaction Ledger
#             new_txn = PaymentTransaction(
#                 school_id=school_id,
#                 subscription_id=sub.id if sub else None,
#                 amount=data.get('amount') / 100,  # Pesewas to GHS
#                 currency=data.get('currency'),
#                 channel=data.get('channel'),
#                 provider='paystack',
#                 provider_reference=reference,
#                 provider_status='success',
#                 status='success',
#                 paid_at=datetime.utcnow(),
#                 metadata_json=data
#             )
            
#             db.session.add(new_txn)
#             db.session.commit()
#             print(f"✅ WEBHOOK SUCCESS: School {school_id} upgraded to Plan {plan_id}!")

#     # Always return 200 OK so Paystack knows we received it
#     return jsonify({"status": "success"}), 200