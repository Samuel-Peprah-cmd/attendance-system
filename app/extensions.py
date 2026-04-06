from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect # Anti-spam/Phishing
from flask_talisman import Talisman     # Forced HTTPS/Security headers
from flask_limiter import Limiter       # Rate Limiter
from flask_cors import CORS
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_socketio import SocketIO

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()
socketio = SocketIO()
csrf = CSRFProtect()
cors = CORS()
login_manager.login_view = "auth.login"


# Limits scans to 5 per minute per IP to prevent bot spam
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])