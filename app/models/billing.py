from app.extensions import db
from datetime import datetime

class Plan(db.Model):
    __tablename__ = 'plans'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    price_monthly = db.Column(db.Float, nullable=False)
    price_annual = db.Column(db.Float, nullable=False)
    
    student_limit = db.Column(db.Integer, default=0)
    admin_limit = db.Column(db.Integer, default=1)
    scanner_limit = db.Column(db.Integer, default=1)
    broadcast_limit = db.Column(db.Integer, default=0)
    
    sms_enabled = db.Column(db.Boolean, default=False)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    gps_enabled = db.Column(db.Boolean, default=False)
    advanced_analytics_enabled = db.Column(db.Boolean, default=False)
    custom_branding_enabled = db.Column(db.Boolean, default=False)
    complaints_enabled = db.Column(db.Boolean, default=False)
    
    is_active = db.Column(db.Boolean, default=True)


class SchoolSubscription(db.Model):
    __tablename__ = 'school_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), unique=True, nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    
    status = db.Column(db.String(20), default='trialing')
    billing_cycle = db.Column(db.String(20), default='monthly')
    
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    grace_until = db.Column(db.DateTime, nullable=True)
    
    auto_renew = db.Column(db.Boolean, default=False)
    
    payment_provider = db.Column(db.String(50), default='paystack')
    provider_customer_code = db.Column(db.String(100), nullable=True)
    provider_subscription_code = db.Column(db.String(100), nullable=True)
    provider_authorization_code = db.Column(db.String(100), nullable=True)
    
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
    
    status = db.Column(db.String(20), default='open')
    
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
    channel = db.Column(db.String(50), nullable=True)

    provider = db.Column(db.String(50), default='paystack')
    provider_reference = db.Column(db.String(100), unique=True, nullable=False)
    provider_status = db.Column(db.String(50), nullable=True)
    
    status = db.Column(db.String(20), default='pending')
    paid_at = db.Column(db.DateTime, nullable=True)
    
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school = db.relationship(
        "School",
        backref=db.backref("payment_transactions", lazy="dynamic"),
        lazy="joined"
    )
    subscription = db.relationship(
        "SchoolSubscription",
        backref=db.backref("payment_transactions", lazy="dynamic")
    )
    invoice = db.relationship(
        "Invoice",
        backref=db.backref("payment_transactions", lazy="dynamic")
    )


class FeatureEntitlement(db.Model):
    __tablename__ = 'feature_entitlements'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True)
    limit_value = db.Column(db.Integer, nullable=True)
    source = db.Column(db.String(50), default='admin_override')
    expires_at = db.Column(db.DateTime, nullable=True)


class FeatureUsageLog(db.Model):
    __tablename__ = 'feature_usage_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    feature_key = db.Column(db.String(100), nullable=False)
    usage_count = db.Column(db.Integer, default=0)
    period_start = db.Column(db.DateTime, nullable=False)
    period_end = db.Column(db.DateTime, nullable=False)

