from app.models.billing import SchoolSubscription
from app.models.billing import Plan
from app.models.billing import FeatureEntitlement

class FeatureGateService:
    
    @staticmethod
    def get_school_plan(school_id):
        # Only returns the plan if the subscription is 'active'
        sub = SchoolSubscription.query.filter_by(school_id=school_id, status='active').first()
        if not sub:
            return None
        return Plan.query.get(sub.plan_id)

    @classmethod
    def can_use_feature(cls, school_id, feature_name):
        plan = cls.get_school_plan(school_id)
        if not plan:
            return False # Locked if no plan or expired
            
        # 🚨 THE MAPPING
        # This maps the name in your HTML to the column in your Database
        feature_map = {
            'broadcasts': 'whatsapp_enabled',
            'live_scanner': 'gps_enabled',
            'gps': 'gps_enabled',
            'staff_attendance': 'whatsapp_enabled',
            'complaints': 'complaints_enabled'
            
        }
        
        column_name = feature_map.get(feature_name, f"{feature_name}_enabled")
        
        # Check if the plan has this boolean set to True
        return getattr(plan, column_name, False)

    @classmethod
    def within_limit(cls, school_id, limit_name, current_count):
        """Checks numeric limits (e.g., student_limit, scanner_limit)"""
        plan = cls.get_school_plan(school_id)
        if not plan:
            return False
            
        base_limit = getattr(plan, f"{limit_name}_limit", 0)
        
        # -1 means unlimited in your database schema
        if base_limit == -1:
            return True
            
        # Check if they have an add-on that increases the limit
        addon = FeatureEntitlement.query.filter_by(school_id=school_id, feature_key=limit_name).first()
        if addon and addon.limit_value:
            base_limit = max(base_limit, addon.limit_value)

        return current_count < base_limit