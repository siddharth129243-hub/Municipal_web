import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'municipal-compiler-secret-key-2024'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///municipal.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # AI Analysis Settings
    AI_THRESHOLD = 5  # Minimum complaints to flag as problematic road