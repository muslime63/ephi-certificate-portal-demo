import os
import io
import re
import sqlite3
import secrets
import string
from datetime import date, datetime
from functools import wraps

import qrcode
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, abort, send_file, make_response
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")

# On Render, set DATABASE_PATH to a file on your persistent disk, for example:
# /var/data/certificates.db
DATABASE_PATH = os.environ.get(
    "DATABASE_PATH",
    os.path.join(os.path.dirname(__file__), "certificates.db")
)
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

VACCINES = {
    "yellow_fever": "Yellow Fever",
    "oral_polio": "Oral Polio Vaccine",
    "meningococcal": "Meningococcal ACYW135",
}

def db():
    con = sqlite3.connect(DATABASE_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    folder = os.path.dirname(DATABASE_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                cert_no TEXT UNIQUE NOT NULL,
                recipient TEXT NOT NULL,
                dob TEXT,
                sex TEXT,
                nationality TEXT,
                organization TEXT,
                issue_date TEXT NOT NULL,
                supervising_clinician TEXT,
                clinician_signature TEXT,
                authorized_by TEXT,
                yellow_fever_type TEXT,
                yellow_fever_manufacturer TEXT,
                yellow_fever_batch_no TEXT,
                yellow_fever_date TEXT,
                oral_polio_type TEXT,
                oral_polio_manufacturer TEXT,
                oral_polio_batch_no TEXT,
                oral_polio_date TEXT,
                meningococcal_type TEXT,
                meningococcal_manufacturer TEXT,
                meningococcal_batch_no TEXT,
                meningococcal_date TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                record_id INTEGER,
                detail TEXT,
                created_at TEXT NOT NULL
            )
        """)

def audit(action, record_id=None, detail=""):
    with db() as con:
        con.execute(
            "INSERT INTO audit_log(action, record_id, detail, created_at) VALUES (?, ?, ?, ?)",
            (action, record_id, detail, datetime.utcnow().isoformat(timespec="seconds"))
        )

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]

@app.context_processor
def inject_csrf():
    return {"csrf_token": csrf_token}

def check_csrf():
    if request.form.get("_csrf") != session.get("_csrf"):
        abort(400, "Invalid form token. Refresh and try again.")

def make_traveler_id():
    alphabet = string.ascii_uppercase
    digits = string.digits
    with db() as con:
        for _ in range(30):
            candidate = "".join(secrets.choice(alphabet) for _ in range(4))
            candidate += "".join(secrets.choice(digits) for _ in range(6))
            exists = con.execute(
                "SELECT 1 FROM certificates WHERE cert_no=?", (candidate,)
            ).fetchone()
            if not exists:
                return candidate
    raise RuntimeError("Could not create a unique Traveler ID")

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        check_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not ADMIN_PASSWORD:
            flash("Admin password is not configured. Set ADMIN_PASSWORD in the hosting environment.", "error")
        elif secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD):
            session.clear()
            session["is_admin"] = True
            session["username"] = username
            session["_csrf"] = secrets.token_urlsafe(24)
            return redirect(url_for("admin"))
        else:
            flash("Username or password is incorrect.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    check_csrf()
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def admin():
    search = request.args.get("q", "").strip()
    with db() as con:
        counts = {
            "total": con.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
            "active": con.execute("SELECT COUNT(*) FROM certificates WHERE status='ACTIVE'").fetchone()[0],
            "revoked": con.execute("SELECT COUNT(*) FROM certificates WHERE status='REVOKED'").fetchone()[0],
            "archived": con.execute("SELECT COUNT(*) FROM certificates WHERE status='ARCHIVED'").fetchone()[0],
        }
        if search:
            like = f"%{search}%"
            records = con.execute("""
                SELECT * FROM certificates
                WHERE recipient LIKE ? OR cert_no LIKE ? OR nationality LIKE ?
                ORDER BY id DESC
            """, (like, like, like)).fetchall()
        else:
            records = con.execute("SELECT * FROM certificates ORDER BY id DESC").fetchall()
        logs = con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 15").fetchall()
    return render_template("admin.html", counts=counts, records=records, logs=logs, search=search)

@app.route("/admin/issue", methods=["GET", "POST"])
@admin_required
def issue():
    if request.method == "POST":
        check_csrf()
        recipient = request.form.get("recipient", "").strip()
        if not recipient:
            flash("Full Name is required.", "error")
            return render_template("issue.html", vaccines=VACCINES)
        token = secrets.token_urlsafe(24)
        cert_no = make_traveler_id()
        fields = [
            "dob", "sex", "nationality", "organization", "supervising_clinician",
            "clinician_signature", "authorized_by",
            "yellow_fever_type", "yellow_fever_manufacturer", "yellow_fever_batch_no", "yellow_fever_date",
            "oral_polio_type", "oral_polio_manufacturer", "oral_polio_batch_no", "oral_polio_date",
            "meningococcal_type", "meningococcal_manufacturer", "meningococcal_batch_no", "meningococcal_date",
        ]
        values = [request.form.get(name, "").strip() for name in fields]
        columns = ["token", "cert_no", "recipient"] + fields + ["issue_date", "created_at"]
        row_values = [token, cert_no, recipient] + values + [date.today().isoformat(), datetime.utcnow().isoformat(timespec="seconds")]
        placeholders = ",".join(["?"] * len(columns))
        with db() as con:
            con.execute(
                f"INSERT INTO certificates ({','.join(columns)}) VALUES ({placeholders})",
                row_values
            )
            record_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        audit("ISSUED", record_id, f"Traveler ID {cert_no}")
        flash(f"Record saved. Traveler ID: {cert_no}", "success")
        return redirect(url_for("admin"))
    return render_template("issue.html", vaccines=VACCINES)

@app.route("/admin/action/<int:record_id>", methods=["POST"])
@admin_required
def record_action(record_id):
    check_csrf()
    action = request.form.get("action", "")
    allowed = {"REVOKE": "REVOKED", "RESTORE": "ACTIVE", "ARCHIVE": "ARCHIVED"}
    if action not in allowed:
        abort(400)
    with db() as con:
        record = con.execute("SELECT * FROM certificates WHERE id=?", (record_id,)).fetchone()
        if not record:
            abort(404)
        con.execute("UPDATE certificates SET status=? WHERE id=?", (allowed[action], record_id))
    audit(action, record_id, f"Status changed to {allowed[action]}")
    flash(f"Record status updated to {allowed[action]}.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/backup")
@admin_required
def backup():
    if not os.path.exists(DATABASE_PATH):
        abort(404)
    return send_file(DATABASE_PATH, as_attachment=True, download_name="ephi_portal_backup.db")

@app.route("/verify/<token>")
def verify(token):
    with db() as con:
        cert = con.execute("SELECT * FROM certificates WHERE token=?", (token,)).fetchone()
    if not cert:
        return render_template("verify.html", cert=None), 404
    return render_template("verify.html", cert=cert)

@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    with db() as con:
        cert = con.execute("SELECT * FROM certificates WHERE token=?", (token,)).fetchone()
    if not cert:
        abort(404)

    traveler_id = cert["cert_no"]
    qr = qrcode.make(f"Traveler ID: {traveler_id}")
    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_io.seek(0)

    buff = io.BytesIO()
    page_size = (13 * cm, 9.3 * cm)
    c = canvas.Canvas(buff, pagesize=page_size)
    w, h = page_size
    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColor(colors.HexColor("#174a6e"))
    c.setLineWidth(1.3)
    c.rect(8, 8, w - 16, h - 16, fill=0, stroke=1)

    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, h - 20, "PERSONAL VACCINATION RECORD")
    c.setFillColor(colors.red)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(w / 2, h - 30, "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE")

    def line(x, y, label, value):
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 5.1)
        c.drawString(x, y, label + ":")
        c.setFont("Helvetica", 5.1)
        c.drawString(x + 63, y, str(value or "Not recorded")[:38])

    x1, y = 15, h - 47
    c.setFont("Helvetica-Bold", 6)
    c.drawString(x1, y, "TRAVELER INFORMATION")
    y -= 11
    for label, value in [
        ("Traveler ID", traveler_id), ("Full Name", cert["recipient"]),
        ("Date of Birth", cert["dob"]), ("Sex", cert["sex"]),
        ("Nationality", cert["nationality"]), ("Organization", cert["organization"]),
        ("Record Date", cert["issue_date"]), ("Status", cert["status"])
    ]:
        line(x1, y, label, value)
        y -= 9

    x2, y2 = 185, h - 47
    c.setFont("Helvetica-Bold", 6)
    c.drawString(x2, y2, "VACCINATION DETAILS")
    y2 -= 12
    for title, prefix in [
        ("YELLOW FEVER", "yellow_fever"),
        ("ORAL POLIO VACCINE", "oral_polio"),
        ("MENINGOCOCCAL ACYW135", "meningococcal"),
    ]:
        c.setFillColor(colors.HexColor("#174a6e"))
        c.setFont("Helvetica-Bold", 5.4)
        c.drawString(x2, y2, title)
        y2 -= 9
        for label, suffix in [("Type", "type"), ("Manufacturer", "manufacturer"), ("Batch", "batch_no"), ("Date", "date")]:
            line(x2, y2, label, cert[f"{prefix}_{suffix}"])
            y2 -= 8
        y2 -= 3

    c.drawImage(ImageReader(qr_io), w - 48, 13, width=32, height=32, mask="auto")
    c.setFont("Helvetica", 4.2)
    c.drawString(w - 53, 9, "TRAVELER ID QR")

    verify_link = url_for("verify", token=token, _external=True)
    link_text = "OPEN RECORD VERIFICATION"
    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 6)
    c.drawString(15, 35, link_text)
    tw = c.stringWidth(link_text, "Helvetica-Bold", 6)
    c.linkURL(verify_link, (15, 32, 15 + tw, 43), relative=0)
    c.setFont("Helvetica", 3.8)
    c.setFillColor(colors.blue)
    c.drawString(15, 26, verify_link[:105])
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 4.2)
    c.drawString(15, 14, "Demonstration personal record only. Verify all details against original source records.")
    c.save()
    buff.seek(0)
    return send_file(buff, mimetype="application/pdf", as_attachment=True,
                     download_name=f"{traveler_id}-record.pdf")

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
