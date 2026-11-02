
import os
import io
import re
import secrets
from datetime import date, datetime
from functools import wraps
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

import qrcode
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is missing")


@contextmanager
def db():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:

        # Create admins table if it does not exist.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL
            )
        """)

        # IMPORTANT: Add password column before updating admins.
        conn.execute("""
            ALTER TABLE admins
            ADD COLUMN IF NOT EXISTS password TEXT
        """)

        # Create certificates table.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id SERIAL PRIMARY KEY,
                cert_no TEXT UNIQUE NOT NULL,
                token TEXT UNIQUE NOT NULL,
                recipient TEXT NOT NULL,
                title TEXT NOT NULL,
                organization TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                expiry_date TEXT,
                signatory TEXT,
                status TEXT NOT NULL DEFAULT 'VALID',
                created_at TEXT NOT NULL
            )
        """)

        # Add new traveler information columns safely.
        columns = {
            "traveler_id": "TEXT",
            "dob": "TEXT",
            "sex": "TEXT",
            "nationality": "TEXT",
            "supervising_clinician": "TEXT",
            "authorized_by": "TEXT",
            "clinician_signature": "TEXT"
        }

        for column, data_type in columns.items():
            conn.execute(
                f"ALTER TABLE certificates ADD COLUMN IF NOT EXISTS {column} {data_type}"
            )

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            certificates_traveler_id_unique
            ON certificates (traveler_id)
            WHERE traveler_id IS NOT NULL
        """)

        # Store individual vaccine records.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vaccinations (
                id SERIAL PRIMARY KEY,
                certificate_id INTEGER NOT NULL
                    REFERENCES certificates(id) ON DELETE CASCADE,
                vaccine_type TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                batch_no TEXT NOT NULL,
                vaccination_date TEXT NOT NULL
            )
        """)

        # Synchronize admin login from Render environment variables.
        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")

        if username and password:
            existing = conn.execute(
                "SELECT id FROM admins WHERE username = %s",
                (username,)
            ).fetchone()

            hashed_password = generate_password_hash(password)

            if existing:
                conn.execute(
                    "UPDATE admins SET password = %s WHERE username = %s",
                    (hashed_password, username)
                )
            else:
                conn.execute(
                    "INSERT INTO admins (username, password) VALUES (%s, %s)",
                    (username, hashed_password)
                )


init_db()


def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


def get_record(token):
    with db() as conn:
        certificate = conn.execute(
            "SELECT * FROM certificates WHERE token = %s",
            (token,)
        ).fetchone()

        if not certificate:
            return None, []

        vaccinations = conn.execute(
            """
            SELECT * FROM vaccinations
            WHERE certificate_id = %s
            ORDER BY vaccination_date
            """,
            (certificate["id"],)
        ).fetchall()

        return certificate, vaccinations


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with db() as conn:
            admin_user = conn.execute(
                "SELECT * FROM admins WHERE username = %s",
                (username,)
            ).fetchone()

        if (
            admin_user
            and admin_user.get("password")
            and check_password_hash(admin_user["password"], password)
        ):
            session["admin"] = username
            return redirect(url_for("admin"))

        flash("Username yookaan password sirrii miti.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin")
@login_required
def admin():
    with db() as conn:
        certificates = conn.execute(
            "SELECT * FROM certificates ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "dashboard.html",
        certificates=certificates
    )


@app.route("/admin/issue", methods=["GET", "POST"])
@login_required
def issue():
    if request.method == "GET":
        return render_template("issue.html")

    traveler_id = request.form.get("traveler_id", "").strip().upper()
    full_name = request.form.get("recipient", "").strip()
    dob = request.form.get("dob", "").strip()
    sex = request.form.get("sex", "").strip()
    nationality = request.form.get("nationality", "").strip()
    organization = request.form.get("organization", "").strip()
    clinician = request.form.get("supervising_clinician", "").strip()
    signature = request.form.get("clinician_signature", "").strip()
    authorized_by = request.form.get("authorized_by", "").strip()

    if not re.fullmatch(r"[A-Z]{4}[0-9]{6}", traveler_id):
        flash("Traveler ID: qubee afur fi lakkoofsa jaha qabaachuu qaba. Fakkeenya: ABCD123456")
        return redirect(url_for("issue"))

    if not all([
        full_name, dob, sex, nationality,
        organization, clinician, authorized_by
    ]):
        flash("Maaloo odeeffannoo dirqama ta'e hunda guuti.")
        return redirect(url_for("issue"))

    try:
        date.fromisoformat(dob)
    except ValueError:
        flash("Guyyaan dhalootaa sirrii miti.")
        return redirect(url_for("issue"))

    vaccine_fields = [
        ("Yellow Fever", "yellow_fever"),
        ("Oral Polio", "oral_polio"),
        ("Meningococcal A, C, Y, W135", "meningococcal")
    ]

    vaccine_records = []

    for vaccine_name, prefix in vaccine_fields:
        manufacturer = request.form.get(
            f"{prefix}_manufacturer", ""
        ).strip()

        batch_no = request.form.get(
            f"{prefix}_batch_no", ""
        ).strip()

        vaccination_date = request.form.get(
            f"{prefix}_date", ""
        ).strip()

        if manufacturer or batch_no or vaccination_date:
            if not all([manufacturer, batch_no, vaccination_date]):
                flash(f"Odeeffannoo {vaccine_name} guutuu guuti.")
                return redirect(url_for("issue"))

            try:
                date.fromisoformat(vaccination_date)
            except ValueError:
                flash(f"Guyyaan {vaccine_name} sirrii miti.")
                return redirect(url_for("issue"))

            vaccine_records.append((
                vaccine_name,
                manufacturer,
                batch_no,
                vaccination_date
            ))

    if not vaccine_records:
        flash("Yoo xiqqaate talaallii tokko galchi.")
        return redirect(url_for("issue"))

    cert_no = "VAC-" + secrets.token_hex(5).upper()
    token = secrets.token_urlsafe(24)
    today = date.today().isoformat()

    try:
        with db() as conn:
            existing = conn.execute(
                "SELECT id FROM certificates WHERE traveler_id = %s",
                (traveler_id,)
            ).fetchone()

            if existing:
                flash("Traveler ID kun duraan galmaa'eera.")
                return redirect(url_for("issue"))

            certificate = conn.execute(
                """
                INSERT INTO certificates (
                    cert_no, token, recipient, title,
                    organization, issue_date, signatory,
                    status, created_at, traveler_id, dob,
                    sex, nationality, supervising_clinician,
                    authorized_by, clinician_signature
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    'VALID', %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    cert_no, token, full_name,
                    "Vaccination Record",
                    organization, today, clinician,
                    datetime.utcnow().isoformat(),
                    traveler_id, dob, sex, nationality,
                    clinician, authorized_by, signature
                )
            ).fetchone()

            for vaccine in vaccine_records:
                conn.execute(
                    """
                    INSERT INTO vaccinations (
                        certificate_id, vaccine_type,
                        manufacturer, batch_no, vaccination_date
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (certificate["id"], *vaccine)
                )

        flash("Galmeen talaallii milkaa'inaan kuufameera.")
        return redirect(url_for("certificate_detail", token=token))

    except Exception:
        app.logger.exception("Unable to save vaccination record")
        flash("Dogoggorri uumameera. Odeeffannoo galmee ilaali.")
        return redirect(url_for("issue"))


@app.route("/admin/certificate/<token>")
@login_required
def certificate_detail(token):
    certificate, vaccinations = get_record(token)

    if not certificate:
        abort(404)

    return render_template(
        "detail.html",
        certificate=certificate,
        vaccinations=vaccinations
    )


@app.route("/admin/certificate/<token>/revoke", methods=["POST"])
@login_required
def revoke(token):
    with db() as conn:
        conn.execute(
            "UPDATE certificates SET status = 'REVOKED' WHERE token = %s",
            (token,)
        )

    flash("Galmeen kun hojii irraa haqameera.")
    return redirect(url_for("admin"))


@app.route("/verify/<token>")
def verify(token):
    certificate, vaccinations = get_record(token)

    if not certificate:
        return render_template(
            "verify.html",
            certificate=None,
            vaccinations=[]
        ), 404

    return render_template(
        "verify.html",
        certificate=certificate,
        vaccinations=vaccinations
    )


@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    certificate, vaccinations = get_record(token)

    if not certificate:
        abort(404)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    pdf.setTitle("Vaccination Record")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(
        width / 2, height - 45,
        "VACCINATION RECORD"
    )

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(
        width / 2, height - 65,
        "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE"
    )

    pdf.setFont("Helvetica", 11)
    y = height - 110

    details = [
        ("Record Number", certificate["cert_no"]),
        ("Traveler ID", certificate.get("traveler_id") or ""),
        ("Full Name", certificate["recipient"]),
        ("Date of Birth", certificate.get("dob") or ""),
        ("Sex", certificate.get("sex") or ""),
        ("Nationality", certificate.get("nationality") or ""),
        ("Organization", certificate["organization"]),
        ("Supervising Clinician", certificate.get("supervising_clinician") or ""),
        ("Authorized By", certificate.get("authorized_by") or ""),
        ("Record Status", certificate["status"])
    ]

    for label, value in details:
        pdf.drawString(55, y, f"{label}: {value}")
        y -= 22

    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(55, y, "Vaccination Details")
    y -= 25

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(55, y, "Vaccine")
    pdf.drawString(260, y, "Manufacturer")
    pdf.drawString(430, y, "Batch No.")
    pdf.drawString(570, y, "Vaccination Date")
    y -= 18

    pdf.setFont("Helvetica", 9)

    for vaccine in vaccinations:
        pdf.drawString(55, y, vaccine["vaccine_type"][:35])
        pdf.drawString(260, y, vaccine["manufacturer"][:25])
        pdf.drawString(430, y, vaccine["batch_no"][:20])
        pdf.drawString(570, y, vaccine["vaccination_date"])
        y -= 20

    verification_url = url_for(
        "verify",
        token=token,
        _external=True
    )

    qr = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.drawImage(
        ImageReader(qr_buffer),
        width - 145,
        35,
        width=85,
        height=85
    )

    pdf.setFont("Helvetica", 8)
    pdf.drawString(55, 35, f"Verify online: {verification_url}")

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{certificate['cert_no']}.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run()
