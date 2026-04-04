from flask import Flask, flash, redirect, url_for
from config import Config
from app.extensions import db, migrate, mail, login_manager
from app.extensions import csrf, limiter, cors

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app) # Enable CSRF protection globally
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "X-Device-Key", "ngrok-skip-browser-warning"], # 🚩 MUST MATCH FRONTEND
            "expose_headers": ["X-Device-Key"]
        }
    })
    
    # allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    # cors.init_app(app, resources={
    #     r"/api/*": {
    #         "origins": allowed_origins,  # 🚩 Now it's dynamic!
    #         "methods": ["GET", "POST", "OPTIONS"],
    #         "allow_headers": ["Content-Type", "X-Device-Key"],
    #         "supports_credentials": True
    #     }
    # })
    limiter.init_app(app)

    # Import and register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.schools import schools_bp
    from app.routes.students import students_bp
    from app.routes.scanner_api import scanner_api_bp
    from app.routes.parents import parents_bp
    from app.routes.attendance import attendance_bp
    from app.routes.staff import staff_bp
    from app.routes.communications import communications_bp
    from app.routes.billing import billing_bp
    from app.routes.superadmin_finance import superadmin_finance_bp
    from app.routes.school_finance import finance_bp
    from app.routes.payment_webhooks import webhook_bp
    from app.routes.biometric import biometric_bp

    if not app.debug:
        from flask_talisman import Talisman
        Talisman(app, content_security_policy=None)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(schools_bp, url_prefix="/schools")
    app.register_blueprint(students_bp, url_prefix="/students")
    app.register_blueprint(scanner_api_bp, url_prefix="/api/scanner")
    app.register_blueprint(parents_bp, url_prefix="/parents")
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(communications_bp, url_prefix='/communications')
    app.register_blueprint(biometric_bp, url_prefix="/api/biometric")
    app.register_blueprint(billing_bp)
    app.register_blueprint(superadmin_finance_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(webhook_bp)
    
    

    csrf.exempt(scanner_api_bp)
    
    @app.after_request
    def add_cors_headers(response):
        # 🚩 Force allow the ngrok origin and the custom headers
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,X-Device-Key,ngrok-skip-browser-warning")
        response.headers.add("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        return response
    
    from app.services.feature_gate_service import FeatureGateService
    from flask_login import current_user

    # This makes the 'has_feature' function available in EVERY HTML file automatically
    @app.context_processor
    def inject_feature_checker():
        def has_feature(feature_name):
            if current_user.is_authenticated and hasattr(current_user, 'school_id'):
                return FeatureGateService.can_use_feature(current_user.school_id, feature_name)
            return False
        return dict(has_feature=has_feature)
    
    from flask import request, redirect, url_for, flash
    from flask_login import current_user
    from app.models.billing import SchoolSubscription

# Add this inside your app initialization / create_app function:
    @app.before_request
    def enforce_paywall():
        # 1. Only check logged-in users who are School Admins
        if current_user.is_authenticated and current_user.role in ['admin', 'school_admin']:
        
            # 2. Allow them to access Auth (logout), Billing, and Static files (CSS/Images)
            # If we don't whitelist these, they will get stuck in an infinite redirect loop!
            allowed_blueprints = ['auth', 'billing', 'finance', 'static']
        
            if request.blueprint not in allowed_blueprints:
            
                # 3. Check their subscription status
                sub = SchoolSubscription.query.filter_by(school_id=current_user.school_id).first()
            
                if sub and sub.status == 'past_due':
                    flash("Your billing cycle has ended. Please renew your package to restore system access.", "danger")
                    # 4. Trap them on the pricing page!
                    return redirect(url_for('billing.pricing_page'))

    return app