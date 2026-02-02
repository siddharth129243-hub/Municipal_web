from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from config import Config
from database import db, login_manager, init_db
from models import User, Complaint, RoadAnalysis
import os
from datetime import datetime
from functools import wraps
import json


app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
init_db(app)

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def role_required(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        taluka = request.form.get('taluka', '')
        phone = request.form.get('phone', '')
        department = request.form.get('department', '')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('login'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('login'))
        
        user = User(
            username=username,
            email=email,
            role=role,
            taluka=taluka,
            phone=phone,
            department=department if role == 'officer' else None
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    # If GET request, show login page (registration is handled in login.html modal)
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'officer':
        return redirect(url_for('officer_dashboard'))
    else:
        return redirect(url_for('user_dashboard'))

@app.route('/user/dashboard')
@login_required
@role_required('user')
def user_dashboard():
    user_complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    resolved_complaints = Complaint.query.filter_by(user_id=current_user.id, status='resolved').count()
    pending_complaints = Complaint.query.filter_by(user_id=current_user.id, status='pending').count()
    
    return render_template('user_dashboard.html',
                         complaints=user_complaints,
                         resolved_count=resolved_complaints,
                         pending_count=pending_complaints)

@app.route('/officer/dashboard')
@login_required
@role_required('officer')
def officer_dashboard():
    assigned_complaints = Complaint.query.filter_by(assigned_officer_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    taluka_complaints = Complaint.query.filter_by(taluka=current_user.taluka, status='pending').all() if current_user.taluka else []
    
    return render_template('officer_dashboard.html',
                         assigned_complaints=assigned_complaints,
                         taluka_complaints=taluka_complaints)

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    # AI Road Analysis
    roads = RoadAnalysis.query.order_by(RoadAnalysis.problem_score.desc()).limit(10).all()
    
    stats = {
        'total_complaints': Complaint.query.count() or 0,
        'pending_complaints': Complaint.query.filter_by(status='pending').count() or 0,
        'resolved_complaints': Complaint.query.filter_by(status='resolved').count() or 0,
        'total_users': User.query.count() or 0,
        'total_officers': User.query.filter_by(role='officer').count() or 0
    }
    
    recent_complaints = Complaint.query.order_by(Complaint.created_at.desc()).limit(10).all()
    
    return render_template('admin_dashboard.html',
                         roads=roads,
                         stats=stats,
                         recent_complaints=recent_complaints)

@app.route('/complaint/new', methods=['GET', 'POST'])
@login_required
def new_complaint():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        address = request.form.get('address')
        
        # Handle file upload
        image_file = request.files.get('image')
        image_path = None
        
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
        
        # Get taluka from user or from form
        taluka = current_user.taluka or 'General'
        if not taluka or taluka == 'General':
            # Try to extract from address
            if address and ',' in address:
                parts = address.split(',')
                if len(parts) > 1:
                    taluka = parts[-1].strip()
        
        complaint = Complaint(
            title=title,
            description=description,
            category=category,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            address=address,
            image_path=image_path,
            user_id=current_user.id,
            taluka=taluka,
            priority='medium'
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        # Update road analysis
        update_road_analysis(address, taluka)
        
        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    
    return render_template('new_complaint.html')

@app.route('/complaint/resolve/<int:complaint_id>', methods=['POST'])
@login_required
@role_required('officer')
def resolve_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    
    resolution_details = request.form.get('resolution_details')
    resolved_image = request.files.get('resolved_image')
    
    if resolved_image and allowed_file(resolved_image.filename):
        filename = secure_filename(f"resolved_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{resolved_image.filename}")
        resolved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        resolved_image.save(resolved_image_path)
        complaint.resolved_image_path = resolved_image_path
    
    complaint.status = 'resolved'
    complaint.resolution_details = resolution_details
    complaint.resolved_at = datetime.utcnow()
    complaint.resolved_by = current_user.id
    
    db.session.commit()
    
    # Update road analysis
    update_road_analysis(complaint.address, complaint.taluka, resolved=True)
    
    flash('Complaint marked as resolved!', 'success')
    return redirect(url_for('officer_dashboard'))

@app.route('/complaint/assign/<int:complaint_id>/<int:officer_id>')
@login_required
@role_required('admin')
def assign_complaint(complaint_id, officer_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    officer = User.query.get_or_404(officer_id)
    
    complaint.assigned_officer_id = officer_id
    complaint.status = 'in_progress'
    db.session.commit()
    
    flash(f'Complaint assigned to {officer.username}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/api/officers')
@login_required
def get_officers():
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    officers = User.query.filter_by(role='officer').all()
    data = [{
        'id': officer.id,
        'username': officer.username,
        'taluka': officer.taluka or 'Not specified',
        'department': officer.department or 'Not specified',
        'phone': officer.phone or 'Not specified'
    } for officer in officers]
    
    return jsonify(data)

@app.route('/api/roads/analysis')
@login_required
def get_road_analysis():
    roads = RoadAnalysis.query.order_by(RoadAnalysis.problem_score.desc()).all()
    data = [{
        'road_name': road.road_name,
        'taluka': road.taluka,
        'total': road.total_complaints or 0,
        'pending': road.pending_complaints or 0,
        'score': road.problem_score or 0
    } for road in roads]
    
    return jsonify(data)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def update_road_analysis(address, taluka, resolved=False):
    if not address:
        return
    
    # Extract road name from address (simple implementation)
    road_name = address.split(',')[0] if ',' in address else address
    
    road = RoadAnalysis.query.filter_by(road_name=road_name, taluka=taluka).first()
    
    if not road:
        road = RoadAnalysis(road_name=road_name, taluka=taluka)
        db.session.add(road)
    
    # Initialize with 0 if None
    road.total_complaints = road.total_complaints or 0
    road.pending_complaints = road.pending_complaints or 0
    road.resolved_complaints = road.resolved_complaints or 0
    road.problem_score = road.problem_score or 0.0
    
    if resolved:
        road.resolved_complaints += 1
        road.pending_complaints = max(0, road.pending_complaints - 1)
    else:
        road.total_complaints += 1
        road.pending_complaints += 1
    
    # Calculate problem score (AI-like calculation)
    # Avoid division by zero
    if road.resolved_complaints > 0:
        road.problem_score = (road.pending_complaints * 0.7 + 
                             road.total_complaints * 0.3) / road.resolved_complaints
    else:
        road.problem_score = road.pending_complaints * 0.7 + road.total_complaints * 0.3
    
    road.last_updated = datetime.utcnow()
    db.session.commit()

@app.route('/api/complaints/stats')
@login_required
def get_complaint_stats():
    if current_user.role == 'user':
        total = Complaint.query.filter_by(user_id=current_user.id).count()
        resolved = Complaint.query.filter_by(user_id=current_user.id, status='resolved').count()
        pending = Complaint.query.filter_by(user_id=current_user.id, status='pending').count()
    elif current_user.role == 'officer':
        total = Complaint.query.filter_by(taluka=current_user.taluka).count() if current_user.taluka else 0
        resolved = Complaint.query.filter_by(taluka=current_user.taluka, status='resolved').count() if current_user.taluka else 0
        pending = Complaint.query.filter_by(taluka=current_user.taluka, status='pending').count() if current_user.taluka else 0
    else:  # admin
        total = Complaint.query.count()
        resolved = Complaint.query.filter_by(status='resolved').count()
        pending = Complaint.query.filter_by(status='pending').count()
    
    return jsonify({
        'total': total,
        'resolved': resolved,
        'pending': pending,
        'resolution_rate': (resolved / total * 100) if total > 0 else 0
    })

# Add a route for viewing all complaints
@app.route('/complaints')
@login_required
def view_complaints():
    if current_user.role == 'admin':
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()
    elif current_user.role == 'officer':
        complaints = Complaint.query.filter_by(taluka=current_user.taluka).order_by(Complaint.created_at.desc()).all() if current_user.taluka else []
    else:
        complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    
    return render_template('view_complaints.html', complaints=complaints)

# Add a route for the homepage/landing page
@app.route('/home')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

    