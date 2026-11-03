
import os
import io
import sqlite3
import secrets
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader


APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(APP_DIR, "certificates.db")
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        con.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY,
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

        columns = {
            "dob": "TEXT",
            "sex": "TEXT",
            "nationality": "TEXT",
            "yellow_fever_manufacturer": "TEXT",
            "yellow_fever_batch_no": "TEXT",
            "yellow_fever_date": "TEXT",
            "oral_polio_manufacturer": "TEXT",
            "oral_polio_batch_no": "TEXT",
            "oral_polio_date": "TEXT",
            "meningococcal_manufacturer": "TEXT",
            "meningococcal_batch_no": "TEXT",
            "meningococcal_date": "TEXT",
            "supervising_clinician": "TEXT",
            "clinician_signature": "TEXT",
            "authorized_by": "TEXT"
        }

        existing = {
            row["name"]
            for row in con.execute(
                "PRAGMA table_info(certificates)"
            ).fetchall()
        }

        for column, data_type in columns.items():
            if column not in existing:
                con.execute(
                    f"ALTER TABLE certificates ADD COLUMN {column} {data_type}"
                )

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD")

        if password and not con.execute(
            "SELECT id FROM admins WHERE username=?",
            (username,)
        ).fetchone():
            con.execute(
                "INSERT INTO admins(username,password_hash) VALUES(?,?)",
                (username, generate_password_hash(password))
            )


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def verification_url(token):
    return url_for("verify", token=token, _external=True)


def generate_traveler_id():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"

    with db() as con:
        for _ in range(100):
            candidate = (
                "".join(secrets.choice(alphabet) for _ in range(4))
                + "".join(secrets.choice(digits) for _ in range(6))
            )

            if not con.execute(
                "SELECT 1 FROM certificates WHERE cert_no=?",
                (candidate,)
            ).fetchone():
                return candidate

    raise RuntimeError("Could not generate a unique Traveler ID")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/verify/<token>")
def verify(token):
    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    return render_template("verify.html", cert=cert)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        with db() as con:
            admin = con.execute(
                "SELECT * FROM admins WHERE username=?",
                (username,)
            ).fetchone()

        if admin and check_password_hash(
            admin["password_hash"], password
        ):
            session.clear()
            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def dashboard():
    q = request.args.get("q", "").strip()

    with db() as con:
        if q:
            rows = con.execute("""
                SELECT * FROM certificates
                WHERE recipient LIKE ? OR cert_no LIKE ?
                ORDER BY id DESC LIMIT 100
            """, (f"%{q}%", f"%{q}%")).fetchall()
        else:
            rows = con.execute("""
                SELECT * FROM certificates
                ORDER BY id DESC LIMIT 100
            """).fetchall()

        total = con.execute(
            "SELECT COUNT(*) FROM certificates"
        ).fetchone()[0]

        valid = con.execute(
            "SELECT COUNT(*) FROM certificates WHERE status='VALID'"
        ).fetchone()[0]

    return render_template(
        "dashboard.html",
        certificates=rows,
        total=total,
        valid=valid,
        q=q
    )


@app.route("/admin/issue", methods=["GET", "POST"])
@login_required
def issue():
    if request.method == "POST":

        fields = {
            "recipient": request.form.get("recipient", "").strip(),
            "dob": request.form.get("dob", "").strip(),
            "sex": request.form.get("sex", "").strip(),
            "nationality": request.form.get("nationality", "").strip(),
            "organization": request.form.get("organization", "").strip(),
            "yellow_fever_manufacturer": request.form.get("yellow_fever_manufacturer", "").strip(),
            "yellow_fever_batch_no": request.form.get("yellow_fever_batch_no", "").strip(),
            "yellow_fever_date": request.form.get("yellow_fever_date", "").strip(),
            "oral_polio_manufacturer": request.form.get("oral_polio_manufacturer", "").strip(),
            "oral_polio_batch_no": request.form.get("oral_polio_batch_no", "").strip(),
            "oral_polio_date": request.form.get("oral_polio_date", "").strip(),
            "meningococcal_manufacturer": request.form.get("meningococcal_manufacturer", "").strip(),
            "meningococcal_batch_no": request.form.get("meningococcal_batch_no", "").strip(),
            "meningococcal_date": request.form.get("meningococcal_date", "").strip(),
            "supervising_clinician": request.form.get("supervising_clinician", "").strip(),
            "clinician_signature": request.form.get("clinician_signature", "").strip(),
            "authorized_by": request.form.get("authorized_by", "").strip()
        }

        required = [
            "recipient", "dob", "sex", "nationality",
            "organization", "supervising_clinician",
            "authorized_by"
        ]

        if any(not fields[name] for name in required):
            flash("Please complete all required fields.", "error")
            return render_template("issue.html")

        try:
            cert_no = generate_traveler_id()
        except RuntimeError:
            flash("Could not generate a unique Traveler ID.", "error")
            return render_template("issue.html")

        token = secrets.token_urlsafe(24)
        today = date.today().isoformat()

        title = "Personal Vaccination Record - Demonstration Copy"

        try:
            with db() as con:
                con.execute("""
                    INSERT INTO certificates (
                        cert_no, token, recipient, title,
                        organization, issue_date, expiry_date,
                        signatory, status, created_at,
                        dob, sex, nationality,
                        yellow_fever_manufacturer,
                        yellow_fever_batch_no, yellow_fever_date,
                        oral_polio_manufacturer,
                        oral_polio_batch_no, oral_polio_date,
                        meningococcal_manufacturer,
                        meningococcal_batch_no, meningococcal_date,
                        supervising_clinician,
                        clinician_signature, authorized_by
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, NULL, ?, 'VALID', ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    cert_no, token, fields["recipient"], title,
                    fields["organization"], today,
                    fields["authorized_by"], datetime.utcnow().isoformat(),
                    fields["dob"], fields["sex"], fields["nationality"],
                    fields["yellow_fever_manufacturer"],
                    fields["yellow_fever_batch_no"],
                    fields["yellow_fever_date"],
                    fields["oral_polio_manufacturer"],
                    fields["oral_polio_batch_no"],
                    fields["oral_polio_date"],
                    fields["meningococcal_manufacturer"],
                    fields["meningococcal_batch_no"],
                    fields["meningococcal_date"],
                    fields["supervising_clinician"],
                    fields["clinician_signature"],
                    fields["authorized_by"]
                ))

            flash("Vaccination record saved successfully.", "success")
            return redirect(
                url_for("certificate_detail", token=token)
            )

        except sqlite3.Error:
            app.logger.exception("Database error while saving record")
            flash("Database error. Please check the application logs.", "error")

    return render_template("issue.html")


@app.route("/admin/certificate/<token>")
@login_required
def certificate_detail(token):
    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    return render_template(
        "detail.html",
        cert=cert,
        verify_url=verification_url(token)
    )


@app.route("/admin/certificate/<token>/revoke", methods=["POST"])
@login_required
def revoke(token):
    with db() as con:
        con.execute(
            "UPDATE certificates SET status='REVOKED' WHERE token=?",
            (token,)
        )

    flash("Record status updated.", "success")
    return redirect(url_for("certificate_detail", token=token))


@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    verify = verification_url(token)
    qr = qrcode.make(verify)

    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_io.seek(0)

    buff = io.BytesIO()
    c = canvas.Canvas(buff, pagesize=A4)
    w, h = A4

    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    c.setStrokeColor(colors.HexColor("#174a6e"))
    c.setLineWidth(3)
    c.rect(25, 25, w - 50, h - 50, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(w / 2, h - 65, "PERSONAL VACCINATION RECORD")

    c.setFillColor(colors.red)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(
        w / 2, h - 85,
        "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE"
    )

    y = h - 125

    def line(label, value):
        nonlocal_y = None
        nonlocal draw_y
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(48, draw_y, label + ":")
        c.setFont("Helvetica", 9)
        c.drawString(190, draw_y, str(value or "Not recorded")[:75])
        draw_y -= 19

    draw_y = y

    line("Traveler ID", cert["cert_no"])
    line("Full Name", cert["recipient"])
    line("Date of Birth", cert["dob"])
    line("Sex", cert["sex"])
    line("Nationality", cert["nationality"])
    line("Organization", cert["organization"])
    line("Record Date", cert["issue_date"])

    draw_y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(48, draw_y, "VACCINATION DETAILS")
    draw_y -= 23

    line("Yellow Fever Manufacturer", cert["yellow_fever_manufacturer"])
    line("Yellow Fever Batch Number", cert["yellow_fever_batch_no"])
    line("Yellow Fever Date", cert["yellow_fever_date"])

    draw_y -= 8
    line("Oral Polio Manufacturer", cert["oral_polio_manufacturer"])
    line("Oral Polio Batch Number", cert["oral_polio_batch_no"])
    line("Oral Polio Date", cert["oral_polio_date"])

    draw_y -= 8
    line("Meningococcal Manufacturer", cert["meningococcal_manufacturer"])
    line("Meningococcal Batch Number", cert["meningococcal_batch_no"])
    line("Meningococcal Date", cert["meningococcal_date"])

    draw_y -= 8
    c.setFont("Helvetica-Bold", 11)
    c.drawString(48, draw_y, "CLINICIAN AND AUTHORIZATION")
    draw_y -= 23

    line("Supervising Clinician", cert["supervising_clinician"])
    line("Signature Reference", cert["clinician_signature"])
    line("Authorized By", cert["authorized_by"])

    c.drawImage(
        ImageReader(qr_io),
        w - 125, 45,
        width=75, height=75,
        preserveAspectRatio=True,
        mask="auto"
    )

    c.setFont("Helvetica", 7)
    c.drawString(48, 55, "Demonstration record only.")
    c.drawString(48, 43, "Not valid as an official travel or international vaccination certificate.")

    c.save()
    buff.seek(0)

    return send_file(
        buff,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{cert['cert_no']}-record.pdf"
    )


@app.route("/health")
def health():
    return {"status": "ok"}


init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
