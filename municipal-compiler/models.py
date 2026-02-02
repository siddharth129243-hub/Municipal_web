from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'officer', 'admin'
    taluka = db.Column(db.String(50), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(15), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with explicit foreign_keys
    complaints = db.relationship('Complaint', 
                                 foreign_keys='Complaint.user_id',
                                 backref='author',
                                 lazy=True)
    
    assigned_complaints = db.relationship('Complaint',
                                          foreign_keys='Complaint.assigned_officer_id',
                                          backref='assigned_officer',
                                          lazy=True)
    
    resolved_complaints = db.relationship('Complaint',
                                          foreign_keys='Complaint.resolved_by',
                                          backref='resolver',
                                          lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_officer(self):
        return self.role == 'officer'
    
    def is_user(self):
        return self.role == 'user'

class Complaint(db.Model):
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    address = db.Column(db.String(300), nullable=True)
    image_path = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, resolved, rejected
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    taluka = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Resolution details
    resolved_image_path = db.Column(db.String(300), nullable=True)
    resolution_details = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

class RoadAnalysis(db.Model):
    __tablename__ = 'road_analysis'
    
    id = db.Column(db.Integer, primary_key=True)
    road_name = db.Column(db.String(200), nullable=False)
    taluka = db.Column(db.String(50), nullable=False)
    total_complaints = db.Column(db.Integer, default=0)
    pending_complaints = db.Column(db.Integer, default=0)
    resolved_complaints = db.Column(db.Integer, default=0)
    problem_score = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        # Ensure defaults are set even if not provided
        kwargs.setdefault('total_complaints', 0)
        kwargs.setdefault('pending_complaints', 0)
        kwargs.setdefault('resolved_complaints', 0)
        kwargs.setdefault('problem_score', 0.0)
        super().__init__(**kwargs)