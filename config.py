import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'atomdev-security-suite-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Path for student photos
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'app/static/uploads/students')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
    CF_PUBLIC_URL_PREFIX = os.getenv("CF_PUBLIC_URL_PREFIX", "")
    CF_BUCKET_NAME = os.getenv("CF_BUCKET_NAME", "")
    CF_SECRET_KEY = os.getenv("CF_SECRET_KEY", "")
    CF_ACCESS_KEY = os.getenv("CF_ACCESS_KEY", "")
    CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
    
    # MAIL CONFIGURATION
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 465)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'False').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'True').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')