from functools import wraps
from flask import flash, redirect, url_for, abort, jsonify, request
from flask_login import current_user
from app.services.feature_gate_service import FeatureGateService
from app.models.student import Student

def requires_feature(feature_name):
    """Blocks access to a route if the school's plan doesn't include the feature."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not FeatureGateService.can_use_feature(current_user.school_id, feature_name):
                if request.is_json:
                    return jsonify({"success": False, "message": f"Upgrade to Premium to access {feature_name.replace('_', ' ')}."}), 403
                
                flash(f"Upgrade Required: Your current plan does not include {feature_name.replace('_', ' ')}.", "warning")
                return redirect(url_for('billing.pricing_page'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def requires_limit(limit_name, model_class):
    """Checks if a school has hit their maximum allowed students/scanners."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Count how many they currently have
            current_count = model_class.query.filter_by(school_id=current_user.school_id).count()
            
            if not FeatureGateService.within_limit(current_user.school_id, limit_name, current_count):
                flash(f"Limit Reached: You have hit the maximum {limit_name} for your current plan. Please upgrade to add more.", "danger")
                return redirect(url_for('billing.pricing_page'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator