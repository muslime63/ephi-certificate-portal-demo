
import os
import random
import string
import io
import datetime
import sqlite3

from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, send_file, abort
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)

from werkzeug.security import (
    generate_password_hash, check_password_hash
)

import qrcode

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'change-this-secret-key'
)

database_url = os.environ.get('DATABASE_URL')

if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace(
            'postgres://', 'postgresql://', 1
        )
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ephi_vaccine.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ==========================================
# DATABASE MODELS
# ==========================================

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class VaccinationRecord(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    traveler_id = db.Column(
        db.String(10), unique=True, nullable=False
    )

    full_name = db.Column(db.String(150), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    nationality = db.Column(db.String(100), nullable=False)

    yf_manufacturer = db.Column(db.String(100))
    yf_batch = db.Column(db.String(50))
    yf_date = db.Column(db.String(20))

    opv_manufacturer = db.Column(db.String(100))
    opv_batch = db.Column(db.String(50))
    opv_date = db.Column(db.String(20))

    men_manufacturer = db.Column(db.String(100))
    men_batch = db.Column(db.String(50))
    men_date = db.Column(db.String(20))

    organization = db.Column(db.String(150))
    supervising_clinician = db.Column(db.String(150))
    signature_ref = db.Column(db.String(100))
    authorized_by = db.Column(db.String(150))

    status = db.Column(db.String(20), default='ACTIVE')

    revoked_reason = db.Column(db.Text, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by = db.Column(db.String(50), nullable=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow
    )


class AuditLog(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    admin_username = db.Column(db.String(50))
    action = db.Column(db.String(255))

    timestamp = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow
    )


# ==========================================
# AUDIT LOG FUNCTION
# ==========================================

def add_audit(action):

    if current_user.is_authenticated:

        log = AuditLog(
            admin_username=current_user.username,
            action=action
        )

        db.session.add(log)
        db.session.commit()


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def init_db():

    with app.app_context():

        db.create_all()

        admin_user = os.environ.get(
            'ADMIN_USERNAME', 'admin'
        )

        admin_password = os.environ.get(
            'ADMIN_PASSWORD', 'admin123'
        )

        admin = Admin.query.filter_by(
            username=admin_user
        ).first()

        if not admin:

            admin = Admin(
                username=admin_user,
                password_hash=generate_password_hash(
                    admin_password
                )
            )

            db.session.add(admin)
            db.session.commit()


init_db()


@login_manager.user_loader
def load_user(user_id):

    return db.session.get(Admin, int(user_id))


# ==========================================
# TRAVELER ID GENERATOR
# 4 LETTERS + 6 DIGITS
# ==========================================

def generate_traveler_id():

    while True:

        letters = ''.join(
            random.choices(string.ascii_uppercase, k=4)
        )

        digits = ''.join(
            random.choices(string.digits, k=6)
        )

        traveler_id = letters + digits

        existing = VaccinationRecord.query.filter_by(
            traveler_id=traveler_id
        ).first()

        if not existing:
            return traveler_id


# ==========================================
# QR CODE GENERATOR
# QR CONTAINS TRAVELER ID ONLY
# ==========================================

def generate_qr(traveler_id):

    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=3
    )

    qr.add_data(traveler_id)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    output = io.BytesIO()

    image.save(output, format='PNG')

    output.seek(0)

    return output


# ==========================================
# HOME
# ==========================================

@app.route('/')
def home():

    return redirect(url_for('login'))


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        admin = Admin.query.filter_by(
            username=username
        ).first()

        if admin and check_password_hash(
            admin.password_hash, password
        ):

            login_user(admin)

            add_audit('Admin logged in')

            return redirect(url_for('admin'))

        flash('Username ykn password doggoraadha!')

    return render_template('login.html')


# ==========================================
# LOGOUT
# ==========================================

@app.route('/logout')
@login_required
def logout():

    add_audit('Admin logged out')

    logout_user()

    return redirect(url_for('login'))


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route('/admin')
@login_required
def admin():

    search = request.args.get(
        'search', ''
    ).strip()

    query = VaccinationRecord.query

    if search:

        query = query.filter(
            db.or_(
                VaccinationRecord.traveler_id.ilike(
                    f'%{search}%'
                ),

                VaccinationRecord.full_name.ilike(
                    f'%{search}%'
                )
            )
        )

    records = query.order_by(
        VaccinationRecord.created_at.desc()
    ).all()

    all_records = VaccinationRecord.query.all()

    total = len(all_records)

    active = sum(
        1 for r in all_records if r.status == 'ACTIVE'
    )

    revoked = sum(
        1 for r in all_records if r.status == 'REVOKED'
    )

    archived = sum(
        1 for r in all_records if r.status == 'ARCHIVED'
    )

    return render_template(
        'admin.html',
        records=records,
        total=total,
        active=active,
        revoked=revoked,
        archived=archived
    )


# ==========================================
# CREATE NEW VACCINATION RECORD
# ==========================================

@app.route('/admin/issue', methods=['GET', 'POST'])
@login_required
def issue():

    if request.method == 'POST':

        traveler_id = generate_traveler_id()

        record = VaccinationRecord(

            traveler_id=traveler_id,

            full_name=request.form.get('full_name', '').strip(),
            dob=request.form.get('dob', ''),
            sex=request.form.get('sex', ''),
            nationality=request.form.get('nationality', ''),

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
            authorized_by=request.form.get('authorized_by'),

            status='ACTIVE'
        )

        if not record.full_name or not record.dob:
            flash('Maqaa fi guyyaa dhalootaa guuti.')
            return render_template('issue.html')

        db.session.add(record)
        db.session.commit()

        add_audit(
            f'Created vaccination record {traveler_id}'
        )

        flash(
            f'Record created successfully. Traveler ID: {traveler_id}'
        )

        return redirect(
            url_for(
                'view_certificate',
                traveler_id=traveler_id
            )
        )

    return render_template('issue.html')


# ==========================================
# VIEW RECORD
# ==========================================

@app.route('/record/<traveler_id>')
@login_required
def view_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    return render_template(
        'certificate.html',
        record=record
    )


# ==========================================
# PUBLIC CERTIFICATE VERIFICATION
# ==========================================

@app.route('/verify/<traveler_id>')
def verify_record(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first()

    return render_template(
        'verify.html',
        record=record,
        traveler_id=traveler_id
    )


# ==========================================
# PDF CERTIFICATE DOWNLOAD
# ==========================================

@app.route('/certificate/<traveler_id>.pdf')
def download_pdf(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    buffer = io.BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=letter
    )

    width, height = letter

    pdf.setTitle('Vaccination Record')

    pdf.setFont('Helvetica-Bold', 18)

    pdf.drawCentredString(
        width / 2,
        height - 45,
        'VACCINATION RECORD'
    )

    pdf.setFont('Helvetica-Bold', 10)

    pdf.drawCentredString(
        width / 2,
        height - 65,
        'RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE'
    )

    pdf.setFont('Helvetica', 11)

    y = height - 110

    details = [

        ('Traveler ID', record.traveler_id),
        ('Full Name', record.full_name),
        ('Date of Birth', record.dob),
        ('Sex', record.sex),
        ('Nationality', record.nationality),

        ('Yellow Fever Manufacturer', record.yf_manufacturer),
        ('Yellow Fever Batch', record.yf_batch),
        ('Yellow Fever Date', record.yf_date),

        ('Oral Polio Manufacturer', record.opv_manufacturer),
        ('Oral Polio Batch', record.opv_batch),
        ('Oral Polio Date', record.opv_date),

        ('Meningococcal Manufacturer', record.men_manufacturer),
        ('Meningococcal Batch', record.men_batch),
        ('Meningococcal Date', record.men_date),

        ('Organization', record.organization),
        ('Supervising Clinician', record.supervising_clinician),
        ('Authorized By', record.authorized_by),

        ('Status', record.status)
    ]

    for label, value in details:

        pdf.setFont('Helvetica-Bold', 10)

        pdf.drawString(55, y, str(label) + ':')

        pdf.setFont('Helvetica', 10)

        pdf.drawString(
            210,
            y,
            str(value or '-')
        )

        y -= 19

        if y < 140:
            pdf.showPage()
            y = height - 60

    # QR CODE: TRAVELER ID ONLY

    qr_buffer = generate_qr(record.traveler_id)

    pdf.drawImage(
        qr_buffer,
        width - 145,
        65,
        width=85,
        height=85
    )

    # CLICKABLE VERIFY CERTIFICATE SENTENCE

    verify_url = url_for(
        'verify_record',
        traveler_id=record.traveler_id,
        _external=True
    )

    pdf.setFont('Helvetica-Bold', 11)

    verify_text = 'Verify Certificate'

    pdf.setFillColorRGB(0, 0, 0.7)

    pdf.drawString(55, 90, verify_text)

    pdf.linkURL(
        verify_url,
        (53, 85, 180, 105),
        relative=0
    )

    pdf.setFillColorRGB(0, 0, 0)

    pdf.setFont('Helvetica', 8)

    pdf.drawString(
        55,
        70,
        'Click Verify Certificate to check this record online.'
    )

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f'{record.traveler_id}.pdf',
        mimetype='application/pdf'
    )


# ==========================================
# QR CODE IMAGE
# ==========================================

@app.route('/qr/<traveler_id>')
def qr_code(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    qr_buffer = generate_qr(record.traveler_id)

    return send_file(
        qr_buffer,
        mimetype='image/png'
    )


# ==========================================
# REVOKE CERTIFICATE
# ==========================================

@app.route('/revoke/<traveler_id>', methods=['GET', 'POST'])
@login_required
def revoke_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    if record.status != 'REVOKED':

        record.status = 'REVOKED'

        record.revoked_reason = request.form.get(
            'reason', 'Revoked by administrator'
        )

        record.revoked_at = datetime.datetime.utcnow()

        record.revoked_by = current_user.username

        db.session.commit()

        add_audit(
            f'Revoked certificate {traveler_id}'
        )

        flash('Certificate revoked successfully.')

    return redirect(url_for('admin'))


# ==========================================
# DELETE CERTIFICATE
# ==========================================

@app.route('/delete/<traveler_id>', methods=['GET', 'POST'])
@login_required
def delete_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    db.session.delete(record)

    db.session.commit()

    add_audit(
        f'Deleted certificate {traveler_id}'
    )

    flash('Record deleted successfully.')

    return redirect(url_for('admin'))


# ==========================================
# DATABASE BACKUP
# SQLITE DATABASE ONLY
# ==========================================

@app.route('/database-backup')
@login_required
def database_backup():

    engine = db.engine

    if engine.dialect.name != 'sqlite':
        flash(
            'Database backup for this database type needs a separate backup process.'
        )
        return redirect(url_for('admin'))

    database_path = engine.url.database

    if not database_path:
        abort(404)

    if not os.path.isabs(database_path):
        database_path = os.path.join(
            app.instance_path,
            database_path
        )

    if not os.path.exists(database_path):
        abort(404)

    return send_file(
        database_path,
        as_attachment=True,
        download_name='ephi_database_backup.db'
    )


# ==========================================
# AUDIT LOGS
# ==========================================

@app.route('/audit-logs')
@login_required
def audit_logs():

    logs = AuditLog.query.order_by(
        AuditLog.timestamp.desc()
    ).all()

    return render_template(
        'audit_logs.html',
        logs=logs
    )


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route('/health')
def health():

    return {
        'status': 'ok',
        'application': 'EPHI Vaccination Record Demo'
    }


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )
