import os
import io
import secrets
from datetime import datetime
from functools import wraps
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, send_file, abort
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

import qrcode

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader


# DATABASE CONFIGURATION

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


# FLASK CONFIGURATION

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)


# DATABASE CONNECTION

@contextmanager
def db():
    conn = psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )

    try:
        with conn:
            yield conn
    finally:
        conn.close()


# LOGIN REQUIRED

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


# DATABASE INITIALIZATION

def init_db():

    with db() as con:

        con.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)

        con.execute("""
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

        username = os.environ.get(
            "ADMIN_USERNAME",
            "admin"
        )

        password = os.environ.get("ADMIN_PASSWORD")

        if password:

            admin = con.execute(
                "SELECT id FROM admins WHERE username=%s",
                (username,)
            ).fetchone()

            if admin:

                con.execute(
                    """
                    UPDATE admins
                    SET password_hash=%s
                    WHERE username=%s
                    """,
                    (
                        generate_password_hash(password),
                        username
                    )
                )

            else:

                con.execute(
                    """
                    INSERT INTO admins(
                        username,
                        password_hash
                    )
                    VALUES(%s, %s)
                    """,
                    (
                        username,
                        generate_password_hash(password)
                    )
                )


# VERIFICATION URL

def verification_url(token):

    return url_for(
        "verify",
        token=token,
        _external=True
    )


# HOME PAGE

@app.route("/")
def home():

    return render_template("home.html")


# VERIFY CERTIFICATE

@app.route("/verify/<token>")
def verify(token):

    with db() as con:

        cert = con.execute(
            "SELECT * FROM certificates WHERE token=%s",
            (token,)
        ).fetchone()

    return render_template(
        "verify.html",
        cert=cert
    )


# LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        with db() as con:

            admin = con.execute(
                "SELECT * FROM admins WHERE username=%s",
                (username,)
            ).fetchone()

        if admin and check_password_hash(
            admin["password_hash"],
            password
        ):

            session.clear()

            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]

            return redirect(url_for("dashboard"))

        flash(
            "Invalid username or password.",
            "error"
        )

    return render_template("login.html")


# LOGOUT

@app.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return redirect(url_for("home"))


# ADMIN DASHBOARD

@app.route("/admin")
@login_required
def dashboard():

    q = request.args.get("q", "").strip()

    with db() as con:

        if q:

            rows = con.execute(
                """
                SELECT * FROM certificates
                WHERE recipient LIKE %s
                OR cert_no LIKE %s
                ORDER BY id DESC
                LIMIT 100
                """,
                (
                    f"%{q}%",
                    f"%{q}%"
                )
            ).fetchall()

        else:

            rows = con.execute(
                """
                SELECT * FROM certificates
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()

        total = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM certificates
            """
        ).fetchone()["count"]

        valid = con.execute(
            """
            SELECT COUNT(*) AS count
            FROM certificates
            WHERE status='VALID'
            """
        ).fetchone()["count"]

    return render_template(
        "dashboard.html",
        certificates=rows,
        total=total,
        valid=valid,
        q=q
    )


# ISSUE CERTIFICATE

@app.route("/admin/issue", methods=["GET", "POST"])
@login_required
def issue():

    if request.method == "POST":

        recipient = request.form.get(
            "recipient", ""
        ).strip()

        title = request.form.get(
            "title", ""
        ).strip()

        organization = request.form.get(
            "organization",
            "Ethiopian Public Health Institute"
        ).strip()

        issue_date = request.form.get(
            "issue_date", ""
        ).strip()

        expiry_date = request.form.get(
            "expiry_date", ""
        ).strip() or None

        signatory = request.form.get(
            "signatory", ""
        ).strip()

        cert_no = request.form.get(
            "cert_no", ""
        ).strip() or (
            "EPHI-"
            + datetime.now().strftime("%Y%m%d")
            + "-"
            + secrets.token_hex(3).upper()
        )

        if not recipient or not title or not issue_date:

            flash(
                "Recipient name, certificate title and issue date are required.",
                "error"
            )

            return render_template("issue.html")

        token = secrets.token_urlsafe(24)

        try:

            with db() as con:

                con.execute(
                    """
                    INSERT INTO certificates(
                        cert_no,
                        token,
                        recipient,
                        title,
                        organization,
                        issue_date,
                        expiry_date,
                        signatory,
                        status,
                        created_at
                    )
                    VALUES(
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        cert_no,
                        token,
                        recipient,
                        title,
                        organization,
                        issue_date,
                        expiry_date,
                        signatory,
                        "VALID",
                        datetime.now().isoformat()
                    )
                )

            flash(
                "Certificate issued successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "certificate_detail",
                    token=token
                )
            )

        except psycopg.IntegrityError:

            flash(
                "That certificate number already exists. Choose another number.",
                "error"
            )

    return render_template("issue.html")


# CERTIFICATE DETAIL

@app.route("/admin/certificate/<token>")
@login_required
def certificate_detail(token):

    with db() as con:

        cert = con.execute(
            "SELECT * FROM certificates WHERE token=%s",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    return render_template(
        "detail.html",
        cert=cert,
        verify_url=verification_url(token)
    )


# REVOKE CERTIFICATE

@app.route(
    "/admin/certificate/<token>/revoke",
    methods=["POST"]
)
@login_required
def revoke(token):

    with db() as con:

        con.execute(
            """
            UPDATE certificates
            SET status='REVOKED'
            WHERE token=%s
            """,
            (token,)
        )

    flash(
        "Certificate status updated to REVOKED.",
        "success"
    )

    return redirect(
        url_for(
            "certificate_detail",
            token=token
        )
    )


# CERTIFICATE PDF

@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):

    with db() as con:

        cert = con.execute(
            "SELECT * FROM certificates WHERE token=%s",
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

    page = landscape(A4)

    c = canvas.Canvas(
        buff,
        pagesize=page
    )

    w, h = page

    c.setFillColor(
        colors.HexColor("#f8fafc")
    )

    c.rect(
        0, 0, w, h,
        fill=1,
        stroke=0
    )

    c.setStrokeColor(
        colors.HexColor("#174a6e")
    )

    c.setLineWidth(5)

    c.rect(
        24, 24,
        w - 48,
        h - 48,
        fill=0,
        stroke=1
    )

    c.setStrokeColor(
        colors.HexColor("#c49a42")
    )

    c.setLineWidth(1.5)

    c.rect(
        34, 34,
        w - 68,
        h - 68,
        fill=0,
        stroke=1
    )

    c.setFillColor(
        colors.HexColor("#123b59")
    )

    c.setFont(
        "Helvetica-Bold",
        22
    )

    c.drawCentredString(
        w / 2,
        h - 88,
        cert["organization"].upper()
    )

    c.setFillColor(
        colors.HexColor("#9a7428")
    )

    c.setFont(
        "Helvetica-Bold",
        15
    )

    c.drawCentredString(
        w / 2,
        h - 125,
        "CERTIFICATE OF ACHIEVEMENT"
    )

    c.setFillColor(
        colors.HexColor("#334155")
    )

    c.setFont(
        "Helvetica",
        13
    )

    c.drawCentredString(
        w / 2,
        h - 174,
        "This certificate is proudly presented to"
    )

    c.setFillColor(
        colors.HexColor("#123b59")
    )

    c.setFont(
        "Helvetica-Bold",
        27
    )

    c.drawCentredString(
        w / 2,
        h - 218,
        cert["recipient"]
    )

    c.setFillColor(
        colors.HexColor("#334155")
    )

    c.setFont(
        "Helvetica",
        13
    )

    c.drawCentredString(
        w / 2,
        h - 255,
        "for successfully completing / receiving"
    )

    c.setFillColor(
        colors.HexColor("#123b59")
    )

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawCentredString(
        w / 2,
        h - 285,
        cert["title"]
    )

    c.setFillColor(
        colors.HexColor("#475569")
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        75, 105,
        f"Certificate No: {cert['cert_no']}"
    )

    c.drawString(
        75, 85,
        f"Issue date: {cert['issue_date']}"
    )

    if cert["expiry_date"]:

        c.drawString(
            75, 65,
            f"Expiry date: {cert['expiry_date']}"
        )

    if cert["signatory"]:

        c.drawString(
            w - 270,
            105,
            cert["signatory"]
        )

        c.setStrokeColor(
            colors.HexColor("#64748b")
        )

        c.line(
            w - 270, 100,
            w - 90, 100
        )

        c.drawString(
            w - 270,
            82,
            "Authorized signatory"
        )

    c.drawImage(
        ImageReader(qr_io),
        w - 145,
        55,
        width=78,
        height=78,
        preserveAspectRatio=True,
        mask="auto"
    )

    c.setFont(
        "Helvetica",
        8
    )

    c.drawRightString(
        w - 65,
        43,
        "Scan to verify authenticity"
    )

    c.save()

    buff.seek(0)

    return send_file(
        buff,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{cert['cert_no']}.pdf"
    )


# HEALTH CHECK

@app.route("/health")
def health():

    return {"status": "ok"}


# INITIALIZE DATABASE

init_db()


# RUN APPLICATION

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
