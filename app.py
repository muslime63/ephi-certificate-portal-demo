
import os
import random
import string
import io
import datetime

from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, send_file, make_response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import (
    generate_password_hash, check_password_hash
)
from sqlalchemy import or_
import qrcode

from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas


# ==========================================
# APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret-key"
)

database_url = os.environ.get("DATABASE_URL")

if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql://", 1
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///ephi_vaccine.db"
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True
}

db = SQLAlchemy(app)


# ==========================================
# LOGIN MANAGER
# ==========================================

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please login first."


# ==========================================
# DATABASE MODELS
# ==========================================

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(50), unique=True, nullable=False
    )
    password_hash = db.Column(
        db.String(255), nullable=False
    )


class VaccinationRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    traveler_id = db.Column(
        db.String(10), unique=True, nullable=False
    )

    full_name = db.Column(db.String(150), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10))
    nationality = db.Column(db.String(100))

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

    status = db.Column(
        db.String(20), default="ACTIVE", nullable=False
    )

    revoked_reason = db.Column(db.Text, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by = db.Column(db.String(50), nullable=True)

    created_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(50))
    action = db.Column(db.String(255))
    timestamp = db.Column(
        db.DateTime, default=datetime.datetime.utcnow
    )


# ==========================================
# AUDIT LOG HELPER
# ==========================================

def add_audit(action):
    if current_user.is_authenticated:
        try:
            db.session.add(AuditLog(
                admin_username=current_user.username,
                action=action
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Audit log error")


# ==========================================
# DATABASE INITIALIZATION
# ==========================================

def init_db():
    with app.app_context():
        db.create_all()

        username = os.environ.get(
            "ADMIN_USERNAME", "admin"
        )
        password = os.environ.get(
            "ADMIN_PASSWORD", "admin123"
        )

        admin_user = Admin.query.filter_by(
            username=username
        ).first()

        if admin_user is None:
            admin_user = Admin(
                username=username,
                password_hash=generate_password_hash(password)
            )
            db.session.add(admin_user)
            db.session.commit()


init_db()


# ==========================================
# USER LOADER
# ==========================================

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(Admin, int(user_id))
    except (TypeError, ValueError):
        return None


# ==========================================
# TRAVELER ID GENERATOR
# 4 LETTERS + 6 DIGITS
# ==========================================

def generate_traveler_id():
    while True:
        letters = "".join(
            random.choices(string.ascii_uppercase, k=4)
        )
        digits = "".join(
            random.choices(string.digits, k=6)
        )

        traveler_id = letters + digits

        exists = VaccinationRecord.query.filter_by(
            traveler_id=traveler_id
        ).first()

        if exists is None:
            return traveler_id


# ==========================================
# QR CODE - TRAVELER ID ONLY
# ==========================================

def generate_qr(traveler_id):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
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
    image.save(output, format="PNG")
    output.seek(0)

    return output


def pdf_text(value):
    if value is None or str(value).strip() == "":
        return "-"

    return str(value).encode(
        "latin-1", "replace"
    ).decode("latin-1")


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return redirect(url_for("login"))


# ==========================================
# ADMIN LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("admin"))

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        admin_user = Admin.query.filter_by(
            username=username
        ).first()

        if admin_user and check_password_hash(
            admin_user.password_hash, password
        ):

            login_user(admin_user)
            add_audit("Admin logged in")

            return redirect(url_for("admin"))

        flash("Username ykn password doggoraadha!")

    return render_template("login.html")


# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
@login_required
def logout():

    add_audit("Admin logged out")
    logout_user()

    return redirect(url_for("login"))


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin")
@login_required
def admin():

    search = request.args.get(
        "search", ""
    ).strip()

    query = VaccinationRecord.query

    if search:
        query = query.filter(
            or_(
                VaccinationRecord.traveler_id.ilike(
                    f"%{search}%"
                ),
                VaccinationRecord.full_name.ilike(
                    f"%{search}%"
                )
            )
        )

    records = query.order_by(
        VaccinationRecord.created_at.desc()
    ).all()

    total = VaccinationRecord.query.count()

    active = VaccinationRecord.query.filter_by(
        status="ACTIVE"
    ).count()

    revoked = VaccinationRecord.query.filter_by(
        status="REVOKED"
    ).count()

    archived = VaccinationRecord.query.filter_by(
        status="ARCHIVED"
    ).count()

    return render_template(
        "admin.html",
        records=records,
        total=total,
        active=active,
        revoked=revoked,
        archived=archived
    )


# ==========================================
# ADMIN AUDIT LOGS
# ==========================================

@app.route("/admin/audit-logs")
@login_required
def audit_logs():

    logs = AuditLog.query.order_by(
        AuditLog.timestamp.desc()
    ).all()

    return render_template(
        "audit_logs.html",
        logs=logs
    )


# ==========================================
# CREATE NEW VACCINATION RECORD
# ==========================================

@app.route("/admin/issue", methods=["GET", "POST"])
@login_required
def issue():

    if request.method == "POST":

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        dob = request.form.get(
            "dob", ""
        ).strip()

        if not full_name or not dob:
            flash("Full Name fi Date of Birth guuti.")
            return render_template("issue.html")

        record = VaccinationRecord(
            traveler_id=generate_traveler_id(),
            full_name=full_name,
            dob=dob,
            sex=request.form.get("sex", "").strip(),
            nationality=request.form.get("nationality", "").strip(),

            yf_manufacturer=request.form.get(
                "yf_manufacturer", ""
            ).strip(),
            yf_batch=request.form.get(
                "yf_batch", ""
            ).strip(),
            yf_date=request.form.get(
                "yf_date", ""
            ).strip(),

            opv_manufacturer=request.form.get(
                "opv_manufacturer", ""
            ).strip(),
            opv_batch=request.form.get(
                "opv_batch", ""
            ).strip(),
            opv_date=request.form.get(
                "opv_date", ""
            ).strip(),

            men_manufacturer=request.form.get(
                "men_manufacturer", ""
            ).strip(),
            men_batch=request.form.get(
                "men_batch", ""
            ).strip(),
            men_date=request.form.get(
                "men_date", ""
            ).strip(),

            organization=request.form.get(
                "organization", ""
            ).strip(),
            supervising_clinician=request.form.get(
                "supervising_clinician", ""
            ).strip(),
            signature_ref=request.form.get(
                "signature_ref", ""
            ).strip(),
            authorized_by=request.form.get(
                "authorized_by", ""
            ).strip(),

            status="ACTIVE"
        )

        try:
            db.session.add(record)
            db.session.commit()

        except Exception:
            db.session.rollback()
            app.logger.exception("Record save error")
            flash("Record save hin taane.")
            return render_template("issue.html")

        add_audit(
            f"Created record {record.traveler_id}"
        )

        flash(
            f"Record created: {record.traveler_id}"
        )

        return redirect(url_for(
            "view_certificate",
            traveler_id=record.traveler_id
        ))

    return render_template("issue.html")


# ==========================================
# VIEW CERTIFICATE - ADMIN ONLY
# ==========================================

@app.route("/record/<traveler_id>")
@login_required
def view_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    return render_template(
        "certificate.html",
        record=record
    )


# ==========================================
# REVOKE CERTIFICATE
# ==========================================

@app.route(
    "/revoke/<traveler_id>",
    methods=["POST"]
)
@login_required
def revoke_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    if record.status != "REVOKED":

        record.status = "REVOKED"

        record.revoked_at = datetime.datetime.utcnow()

        record.revoked_by = current_user.username

        record.revoked_reason = request.form.get(
            "reason",
            "Revoked by administrator"
        ).strip()

        db.session.commit()

        add_audit(
            f"Revoked record {traveler_id}"
        )

        flash("Record revoked successfully.")

    return redirect(url_for("admin"))


# ==========================================
# DELETE CERTIFICATE
# ==========================================

@app.route(
    "/delete/<traveler_id>",
    methods=["POST"]
)
@login_required
def delete_certificate(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    traveler_id = record.traveler_id

    db.session.delete(record)
    db.session.commit()

    add_audit(
        f"Deleted record {traveler_id}"
    )

    flash("Record deleted successfully.")

    return redirect(url_for("admin"))


# ==========================================
# PUBLIC ONLINE VERIFICATION
# ==========================================

@app.route("/verify/<traveler_id>")
def verify_record(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first()

    response = make_response(
        render_template(
            "verify.html",
            record=record,
            traveler_id=traveler_id
        )
    )

    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate"
    )

    return response


# ==========================================
# PDF RECORD DOWNLOAD
# ==========================================

@app.route("/certificate/<traveler_id>.pdf")
@login_required
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

    pdf.setTitle(
        "Personal Vaccination Record - "
        + record.traveler_id
    )

    # HEADER
    pdf.setFillColorRGB(0.95, 0.80, 0.25)

    pdf.rect(
        0, height - 95,
        width, 95,
        fill=1,
        stroke=0
    )

    pdf.setFillColorRGB(0, 0, 0)

    pdf.setFont("Helvetica-Bold", 19)

    pdf.drawCentredString(
        width / 2,
        height - 42,
        "VACCINATION RECORD"
    )

    pdf.setFont("Helvetica-Bold", 9)

    pdf.drawCentredString(
        width / 2,
        height - 63,
        "DEMONSTRATION PERSONAL RECORD - NOT OFFICIAL"
    )

    y = height - 125

    def section(title):

        nonlocal y

        if y < 120:
            pdf.showPage()
            y = height - 55

        pdf.setFillColorRGB(0.95, 0.85, 0.50)

        pdf.rect(
            45, y - 5,
            width - 90, 20,
            fill=1,
            stroke=0
        )

        pdf.setFillColorRGB(0, 0, 0)

        pdf.setFont("Helvetica-Bold", 11)

        pdf.drawString(52, y, title)

        y -= 30

    def detail(label, value):

        nonlocal y

        lines = simpleSplit(
            pdf_text(value),
            "Helvetica",
            9,
            320
        )

        needed = max(1, len(lines)) * 13 + 5

        if y - needed < 110:
            pdf.showPage()
            y = height - 55

        pdf.setFont("Helvetica-Bold", 9)

        pdf.drawString(
            55, y,
            pdf_text(label) + ":"
        )

        pdf.setFont("Helvetica", 9)

        for line in lines:
            pdf.drawString(225, y, line)
            y -= 13

        y -= 5

    section("PERSONAL INFORMATION")

    detail("Traveler ID", record.traveler_id)
    detail("Full Name", record.full_name)
    detail("Date of Birth", record.dob)
    detail("Sex", record.sex)
    detail("Nationality", record.nationality)

    section("YELLOW FEVER VACCINATION")

    detail("Manufacturer", record.yf_manufacturer)
    detail("Batch Number", record.yf_batch)
    detail("Vaccination Date", record.yf_date)

    section("ORAL POLIO VACCINATION")

    detail("Manufacturer", record.opv_manufacturer)
    detail("Batch Number", record.opv_batch)
    detail("Vaccination Date", record.opv_date)

    section("MENINGOCOCCAL ACYW135 VACCINATION")

    detail("Manufacturer", record.men_manufacturer)
    detail("Batch Number", record.men_batch)
    detail("Vaccination Date", record.men_date)

    section("CLINIC INFORMATION")

    detail("Clinic / Vaccination Center", record.organization)
    detail("Supervising Clinician", record.supervising_clinician)
    detail("Signature Reference", record.signature_ref)
    detail("Authorized By", record.authorized_by)

    section("RECORD STATUS")

    pdf.setFont("Helvetica-Bold", 12)

    if record.status == "ACTIVE":
        pdf.setFillColorRGB(0, 0.55, 0.15)
        status_label = "ACTIVE"

    elif record.status == "REVOKED":
        pdf.setFillColorRGB(0.8, 0, 0)
        status_label = "REVOKED"

    else:
        pdf.setFillColorRGB(0, 0, 0)
        status_label = pdf_text(record.status)

    pdf.drawString(55, y, status_label)

    pdf.setFillColorRGB(0, 0, 0)

    y -= 22

    if record.status == "REVOKED":

        detail("Revoked Reason", record.revoked_reason)
        detail("Revoked By", record.revoked_by)

        detail(
            "Revoked At",
            record.revoked_at.strftime("%Y-%m-%d %H:%M")
            if record.revoked_at else "-"
        )

    # QR CODE CONTAINS TRAVELER ID ONLY

    qr_buffer = generate_qr(record.traveler_id)

    qr_size = 75
    qr_x = width - 125
    qr_y = 45

    pdf.drawImage(
        ImageReader(qr_buffer),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size
    )

    pdf.setFont("Helvetica-Bold", 8)

    pdf.drawCentredString(
        qr_x + qr_size / 2,
        qr_y - 12,
        "TRAVELER ID QR"
    )

    # CLICKABLE ONLINE VERIFICATION TEXT

    verify_url = (
        "https://ephi-certificate-portal-demo-1.onrender.com"
        f"/verify/{record.traveler_id}"
    )

    verify_text = "VERIFY RECORD ONLINE"

    verify_x = 55
    verify_y = 75

    pdf.setFillColorRGB(0, 0, 0.8)

    pdf.setFont("Helvetica-Bold", 10)

    pdf.drawString(
        verify_x,
        verify_y,
        verify_text
    )

    text_width = pdf.stringWidth(
        verify_text,
        "Helvetica-Bold",
        10
    )

    pdf.linkURL(
        verify_url,
        (
            verify_x,
            verify_y - 3,
            verify_x + text_width,
            verify_y + 12
        ),
        relative=0
    )

    pdf.setFillColorRGB(0, 0, 0)

    pdf.setFont("Helvetica", 8)

    pdf.drawString(
        55,
        40,
        "Demonstration personal vaccination record only."
    )

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{record.traveler_id}.pdf",
        mimetype="application/pdf"
    )


# ==========================================
# QR CODE IMAGE
# ==========================================

@app.route("/qr/<traveler_id>.png")
@login_required
def qr_image(traveler_id):

    record = VaccinationRecord.query.filter_by(
        traveler_id=traveler_id
    ).first_or_404()

    return send_file(
        generate_qr(record.traveler_id),
        mimetype="image/png",
        download_name=f"{record.traveler_id}-qr.png"
    )


# ==========================================
# HEALTH CHECK
# ==========================================

@app.route("/health")
def health():
    return {"status": "ok"}, 200


# ==========================================
# APPLICATION START
# ==========================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
