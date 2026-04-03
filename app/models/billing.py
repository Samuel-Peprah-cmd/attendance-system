from app.extensions import db
from datetime import datetime

class Plan(db.Model):
    __tablename__ = 'plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False) # starter, growth, premium, enterprise
    price_monthly = db.Column(db.Float, nullable=False)
    price_annual = db.Column(db.Float, nullable=False)
    
    # Quantitative Limits (-1 means unlimited)
    student_limit = db.Column(db.Integer, default=0)
    admin_limit = db.Column(db.Integer, default=1)
    scanner_limit = db.Column(db.Integer, default=1)
    broadcast_limit = db.Column(db.Integer, default=0)
    
    # Feature Toggles (Access Control)
    sms_enabled = db.Column(db.Boolean, default=False)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    gps_enabled = db.Column(db.Boolean, default=False)
    advanced_analytics_enabled = db.Column(db.Boolean, default=False)
    custom_branding_enabled = db.Column(db.Boolean, default=False)
    
    is_active = db.Column(db.Boolean, default=True)

class SchoolSubscription(db.Model):
    __tablename__ = 'school_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    
    status = db.Column(db.String(20), default='trialing') # trialing, active, past_due, canceled
    billing_cycle = db.Column(db.String(20), default='monthly') # monthly, termly, annual
    
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    grace_until = db.Column(db.DateTime, nullable=True) # Used when MoMo payment is pending
    
    # Determines if we charge automatically or send an invoice
    auto_renew = db.Column(db.Boolean, default=False) # True for Cards, False for MoMo/Bank
    
    # Provider details
    payment_provider = db.Column(db.String(50), default='paystack')
    provider_customer_code = db.Column(db.String(100), nullable=True)
    provider_subscription_code = db.Column(db.String(100), nullable=True)
    provider_authorization_code = db.Column(db.String(100), nullable=True) # Used for Paystack recurring charges
    
    # Relationships
    plan = db.relationship("Plan")
    school = db.relationship("School", backref=db.backref("subscription", uselist=False))

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('school_subscriptions.id'), nullable=False)
    
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='GHS')
    
    status = db.Column(db.String(20), default='open') # open, paid, void, uncollectible
    
    due_date = db.Column(db.DateTime, nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    
    subscription = db.relationship("SchoolSubscription", backref=db.backref("invoices", lazy="dynamic"))

class PaymentTransaction(db.Model):
    __tablename__ = 'payment_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('school_subscriptions.id'), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=True)
    
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='GHS')
    channel = db.Column(db.String(50), nullable=True) # card, mobile_money, bank_transfer
    
    provider = db.Column(db.String(50), default='paystack')
    provider_reference = db.Column(db.String(100), unique=True, nullable=False) 
    provider_status = db.Column(db.String(50), nullable=True)
    
    status = db.Column(db.String(20), default='pending') # pending, success, failed
    paid_at = db.Column(db.DateTime, nullable=True)
    
    # Store the entire raw webhook payload here for financial auditing
    metadata_json = db.Column(db.JSON, nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FeatureEntitlement(db.Model):
    """For custom add-ons that override the base plan"""
    __tablename__ = 'feature_entitlements'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)
    limit_value = db.Column(db.Integer, nullable=True) # Override quantitative limit
    source = db.Column(db.String(50), default='admin_override') # e.g., 'addon_purchase', 'admin_override'
    expires_at = db.Column(db.DateTime, nullable=True)

class FeatureUsageLog(db.Model):
    """Tracks how much of a capped feature a school has used this cycle"""
    __tablename__ = 'feature_usage_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False) # e.g., 'monthly_broadcasts'
    usage_count = db.Column(db.Integer, default=0)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)