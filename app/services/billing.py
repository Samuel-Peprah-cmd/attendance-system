from datetime import datetime
from app.extensions import db
from app.models.billing import SchoolSubscription, Invoice

class BillingService:
    @staticmethod
    def calculate_upgrade_cost(school_id, new_plan):
        sub = SchoolSubscription.query.filter_by(school_id=school_id).first()
        if not sub or sub.status != 'active':
            return new_plan.price_monthly, 0.0

        # 1. Calculate remaining days in current cycle
        total_days = (sub.end_date - sub.start_date).days
        remaining_days = (sub.end_date - datetime.utcnow()).days
        
        if remaining_days <= 0:
            return new_plan.price_monthly, 0.0

        # 2. Calculate credit from unused time
        # (Current Price / Total Days) * Remaining Days
        current_plan_price = sub.plan.price_monthly
        unused_credit = (current_plan_price / total_days) * remaining_days
        
        # 3. New total = New Plan Price - Unused Credit
        final_price = max(0, new_plan.price_monthly - unused_credit)
        
        return round(final_price, 2), round(unused_credit, 2)