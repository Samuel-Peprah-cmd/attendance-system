from app.models.billing import SchoolSubscription
from app.models.billing import Plan
from app.models.billing import FeatureEntitlement

class FeatureGateService:
    
    @staticmethod
    def get_school_plan(school_id):
        sub = SchoolSubscription.query.filter_by(school_id=school_id, status='active').first()
        if not sub:
            return None
        return Plan.query.get(sub.plan_id)

    @classmethod
    def can_use_feature(cls, school_id, feature_name):
        """Checks boolean features (e.g., whatsapp_enabled, gps_enabled)"""
        plan = cls.get_school_plan(school_id)
        if not plan:
            return False
            
        # Check base plan features
        has_base_access = getattr(plan, f"{feature_name}_enabled", False)
        
        # Check for custom entitlements/add-ons purchased
        addon = FeatureEntitlement.query.filter_by(
            school_id=school_id, 
            feature_key=feature_name, 
            is_enabled=True
        ).first()
        
        return has_base_access or (addon is not None)

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