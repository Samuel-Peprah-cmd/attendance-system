from app import create_app
from app.extensions import db
from app.models.billing import Plan

def seed_plans():
    app = create_app()
    with app.app_context():
        print("--- Starting Plan Seeding ---")
        
        # 1. Define your 4 OpenAI-style packages
        plans_data = [
            {
                "name": "Starter",
                "slug": "starter",
                "price_monthly": 100.0,
                "price_annual": 1000.0,
                "student_limit": 100,
                "admin_limit": 1,
                "scanner_limit": 1,
                "broadcast_limit": 0,
                "sms_enabled": True,
                "whatsapp_enabled": False,
                "gps_enabled": False,
                "advanced_analytics_enabled": False
            },
            {
                "name": "Growth",
                "slug": "growth",
                "price_monthly": 250.0,
                "price_annual": 2500.0,
                "student_limit": 500,
                "admin_limit": 3,
                "scanner_limit": 2,
                "broadcast_limit": 100,
                "sms_enabled": True,
                "whatsapp_enabled": False,
                "gps_enabled": False,
                "advanced_analytics_enabled": True
            },
            {
                "name": "Premium",
                "slug": "premium",
                "price_monthly": 500.0,
                "price_annual": 5000.0,
                "student_limit": 2000,
                "admin_limit": 10,
                "scanner_limit": 5,
                "broadcast_limit": -1, # Unlimited
                "sms_enabled": True,
                "whatsapp_enabled": True,
                "gps_enabled": True,
                "advanced_analytics_enabled": True
            },
            {
                "name": "Enterprise",
                "slug": "enterprise",
                "price_monthly": 1500.0,
                "price_annual": 15000.0,
                "student_limit": -1, # Unlimited
                "admin_limit": -1,
                "scanner_limit": -1,
                "broadcast_limit": -1,
                "sms_enabled": True,
                "whatsapp_enabled": True,
                "gps_enabled": True,
                "advanced_analytics_enabled": True,
                "custom_branding_enabled": True
            }
        ]

        for data in plans_data:
            # Check if plan already exists by slug to avoid duplicates
            existing_plan = Plan.query.filter_by(slug=data['slug']).first()
            
            if existing_plan:
                print(f"Updating existing plan: {data['name']}")
                for key, value in data.items():
                    setattr(existing_plan, key, value)
            else:
                print(f"Creating new plan: {data['name']}")
                new_plan = Plan(**data)
                db.session.add(new_plan)
        
        db.session.commit()
        print("--- Seeding Complete! ---")

if __name__ == "__main__":
    seed_plans()