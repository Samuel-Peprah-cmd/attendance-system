from datetime import datetime
from app.extensions import db
from app.models.billing import SchoolSubscription
from app.models.audit import BillingAuditLog

def process_expired_subscriptions(app):
    """
    Checks all active subscriptions. If the end_date has passed, 
    it moves them to 'past_due' to trigger the access locks.
    """
    # We need the app context because this runs outside standard web requests
    with app.app_context():
        now = datetime.utcnow()
        
        # Find all active subscriptions where the time has run out
        expired_subs = SchoolSubscription.query.filter(
            SchoolSubscription.status == 'active',
            SchoolSubscription.end_date < now
        ).all()

        count = 0
        for sub in expired_subs:
            # 1. Change the status to lock the account
            sub.status = 'past_due'
            
            # 2. Log it for the financial audit trail
            audit = BillingAuditLog(
                school_id=sub.school_id,
                action="subscription_expired",
                old_value="active",
                new_value="past_due",
                reason=f"Automated expiry. End date was {sub.end_date.strftime('%Y-%m-%d')}"
            )
            db.session.add(audit)
            count += 1

        db.session.commit()
        print(f"✅ Automated Check Complete: {count} subscriptions moved to past_due.")