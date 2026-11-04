import os
import random
import string
import io
import datetime
import base64

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ephi-secure-production-key')
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
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(50))
    action = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)


# --- DATABASE INITIALIZATION ---

def init_db():
    with app.app_context():
        db.create_all()
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            default_admin = Admin(
                username='admin',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(default_admin)
            db.session.commit()

init_db()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


def generate_traveler_id():
    while True:
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        digits = ''.join(random.choices(string.digits, k=6))
        tid = f"{letters}{digits}"
        if not VaccinationRecord.query.filter_by(traveler_id=tid).first():
            return tid
