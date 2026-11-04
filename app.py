import os
import random
import string
import io
import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ephi-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ephi_vaccine.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class VaccinationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    traveler_id = db.Column(db.String(10), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    nationality = db.Column(db.String(100), nullable=False)
    
    # Vaccine Details
    yf_type = db.Column(db.String(100), default='Yellow Fever')
    yf_manufacturer = db.Column(db.String(100))
    yf_batch = db.Column(db.String(50))
    yf_date = db.Column(db.String(20))
    
    opv_type = db.Column(db.String(100), default='Oral Polio Vaccine')
    opv_manufacturer = db.Column(db.String(100))
    opv_batch = db.Column(db.String(50))
    opv_date = db.Column(db.String(20))
    
    men_type = db.Column(db.String(100), default='Meningococcal A, C, Y, W135')
    men_manufacturer = db.Column(db.String(100))
    men_batch = db.Column(db.String(50))
    men_date = db.Column(db.String(20))
    
    # Clinician Info
    organization = db.Column(db.String(150))
    supervising_clinician = db.Column(db.String(150))
    signature_ref = db.Column(db.String(100))
    authorized_by = db.Column(db.String(150))
    
    # Status & Audit
    status = db.Column(db.String(20), default='ACTIVE') # ACTIVE, REVOKED, ARCHIVED
    revoked_reason = db.Column(db.Text, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(50))
    action = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# --- DATABASE SETUP & INITIAL ADMIN ---

def init_db():
    with app.app_context():
        db.create_all()
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            # Create default admin if it doesn't exist
            hashed_pw = generate_password_hash('admin123')
            default_admin = Admin(username='admin', password_hash=hashed_pw)
            db.session.add(default_admin)
        else:
            # Force-update password hash so login always succeeds
            admin.password_hash = generate_password_hash('admin123')
        db.session.commit()

# Execute initialization so WSGI servers (Gunicorn) run it on startup
init_db()

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

# Helper to generate unique Traveler ID (4 letters + 6 digits)
def generate_traveler_id():
    while True:
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        digits = ''.join(random.choices(string.digits, k=6))
        tid = f"{letters}{digits}"
        if not VaccinationRecord.query.filter_by(traveler_id=tid).first():
            return tid

def log_action(action):
    log = AuditLog(admin_username=current_user.username if current_user.is_authenticated else 'System', action=action)
    db.session.add(log)
    db.session.commit()

# --- ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            log_action("Admin logged in")
            return redirect(url_for('dashboard'))
        flash('Username ykn password doggoraadha!', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    log_action("Admin logged out")
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    search_query = request.args.get('search', '')
    if search_query:
        records = VaccinationRecord.query.filter(
            (VaccinationRecord.traveler_id.ilike(f'%{search_query}%')) |
            (VaccinationRecord.full_name.ilike(f'%{search_query}%'))
        ).all()
    else:
        records = VaccinationRecord.query.filter_by(status='ACTIVE').all()
        
    total_records = VaccinationRecord.query.count()
    active_records = VaccinationRecord.query.filter_by(status='ACTIVE').count()
    revoked_records = VaccinationRecord.query.filter_by(status='REVOKED').count()
    archived_records = VaccinationRecord.query.filter_by(status='ARCHIVED').count()

    return render_template('admin.html', 
                           records=records, 
                           total=total_records, 
                           active=active_records, 
                           revoked=revoked_records, 
                           archived=archived_records)

@app.route('/issue', methods=['GET', 'POST'])
@login_required
def issue_record():
    if request.method == 'POST':
        tid = generate_traveler_id()
        record = VaccinationRecord(
            traveler_id=tid,
            full_name=request.form.get('full_name'),
            dob=request.form.get('dob'),
            sex=request.form.get('sex'),
            nationality=request.form.get('nationality'),
            
            yf_manufacturer=request.form.get('yf_manufacturer'),
            yf_batch=request.form.get('yf_batch'),
            yf_date=request.form.get('yf_date'),
            
            opv_manufacturer=request.form.get('opv_manufacturer'),
            opv_batch=request.form.get('opv_batch'),
            opv_date=request.form.get('opv_date'),
            
            men_manufacturer=request.form.get('men_manufacturer'),
            men_batch=request.form.get('men_batch'),
            men_date=request.form.get('men_date'),
            
            organization=request.form.get('organization'),
            supervising_clinician=request.form.get('supervising_clinician'),
            signature_ref=request.form.get('signature_ref'),
            authorized_by=request.form.get('authorized_by')
        )
        db.session.add(record)
        db.session.commit()
        log_action(f"Issued new record for ID: {tid}")
        flash(f'Galmeen haaraa galmeeffameera! Traveler ID: {tid}', 'success')
        return redirect(url_for('view_certificate', traveler_id=tid))
    return render_template('issue.html')

@app.route('/record/<traveler_id>')
@login_required
def view_certificate(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first_or_404()
    verify_url = url_for('verify_record', traveler_id=record.traveler_id, _external=True)
    
    # Generate QR Code image in memory
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_buf = io.BytesIO()
    img.save(img_buf, 'PNG')
    import base64
    qr_b64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')
    
    return render_template('certificate.html', record=record, qr_code=qr_b64, verify_url=verify_url)

@app.route('/verify/<traveler_id>')
def verify_record(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first()
    return render_template('verify.html', record=record)

@app.route('/revoke/<traveler_id>', methods=['POST'])
@login_required
def revoke_record(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first_or_404()
    reason = request.form.get('reason', 'No reason provided')
    record.status = 'REVOKED'
    record.revoked_reason = reason
    record.revoked_at = datetime.datetime.utcnow()
    record.revoked_by = current_user.username
    db.session.commit()
    log_action(f"Revoked record: {traveler_id}")
    flash('Record hojii irraa dhaabbateera (Revoked)!', 'warning')
    return redirect(url_for('dashboard'))

@app.route('/restore/<traveler_id>')
@login_required
def restore_record(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first_or_404()
    record.status = 'ACTIVE'
    db.session.commit()
    log_action(f"Restored record: {traveler_id}")
    flash('Record deebi’ee hojii irra ooleera!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/archive/<traveler_id>')
@login_required
def archive_record(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first_or_404()
    record.status = 'ARCHIVED'
    db.session.commit()
    log_action(f"Archived record: {traveler_id}")
    flash('Record kuusaa seenaatti dabalameera!', 'info')
    return redirect(url_for('dashboard'))

@app.route('/download-pdf/<traveler_id>')
@login_required
def download_pdf(traveler_id):
    record = VaccinationRecord.query.filter_by(traveler_id=traveler_id).first_or_404()
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    p.drawString(100, 750, f"EPHI VACCINATION RECORD: {record.traveler_id}")
    p.drawString(100, 730, f"Full Name: {record.full_name}")
    p.drawString(100, 710, f"DOB: {record.dob} | Sex: {record.sex} | Nationality: {record.nationality}")
    p.drawString(100, 680, f"Yellow Fever Date: {record.yf_date} Batch: {record.yf_batch}")
    p.drawString(100, 660, f"OPV Date: {record.opv_date} Batch: {record.opv_batch}")
    p.drawString(100, 640, f"Meningococcal Date: {record.men_date} Batch: {record.men_batch}")
    p.drawString(100, 610, f"Authorized By: {record.authorized_by}")
    p.drawString(100, 590, f"Status: {record.status}")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{record.traveler_id}_certificate.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True)
