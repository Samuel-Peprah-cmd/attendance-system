from app import create_app
from app.extensions import db
from app.models.billing import Plan

app = create_app()
with app.app_context():
    plans = Plan.query.all()
    for p in plans:
        p.complaints_enabled = (p.slug == "enterprise" or p.name.lower() == "enterprise")
    db.session.commit()