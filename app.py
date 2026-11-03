import io
import random
import string
import sqlite3
import uuid
from flask import (
    Flask,
    abort,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)
import qrcode
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

app = Flask(__name__)
app.secret_key = "secret-key-vaccine-record"

DATABASE = "certificates.db"


def get_db():
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with get_db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                cert_no TEXT UNIQUE NOT NULL,
                recipient TEXT NOT NULL,
                dob TEXT,
                sex TEXT,
                nationality TEXT,
                organization TEXT,
                issue_date TEXT,
                supervising_clinician TEXT,
                clinician_signature TEXT,
                authorized_by TEXT,
                yellow_fever_manufacturer TEXT,
                yellow_fever_batch_no TEXT,
                yellow_fever_date TEXT,
                oral_polio_manufacturer TEXT,
                oral_polio_batch_no TEXT,
                oral_polio_date TEXT,
                meningococcal_manufacturer TEXT,
                meningococcal_batch_no TEXT,
                meningococcal_date TEXT
            )
            """
        )
        con.commit()


# Initialize database table on startup
init_db()


def generate_traveler_id():
    """Generates a Traveler ID with 4 random uppercase letters + 6 digits (e.g. ABCD123456)"""
    letters = "".join(random.choices(string.ascii_uppercase, k=4))
    digits = "".join(random.choices(string.digits, k=6))
    return f"{letters}{digits}"


@app.route("/")
def index():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin", methods=["GET"])
def admin_dashboard():
    query = request.args.get("q", "").strip()
    with get_db() as con:
        if query:
            cur = con.execute(
                """
                SELECT * FROM certificates 
                WHERE cert_no LIKE ? OR recipient LIKE ?
                ORDER BY id DESC
                """,
                (f"%{query}%", f"%{query}%"),
            )
        else:
            cur = con.execute("SELECT * FROM certificates ORDER BY id DESC")
        records = cur.fetchall()

    return render_template_string(ADMIN_HTML, records=records, query=query)


@app.route("/create", methods=["GET", "POST"])
def create_record():
    error = None
    auto_id = generate_traveler_id()

    if request.method == "POST":
        cert_no = request.form.get("cert_no", "").strip().upper()
        token = str(uuid.uuid4())

        try:
            with get_db() as con:
                con.execute(
                    """
                    INSERT INTO certificates (
                        token, cert_no, recipient, dob, sex, nationality, organization, 
                        issue_date, supervising_clinician, clinician_signature, authorized_by,
                        yellow_fever_manufacturer, yellow_fever_batch_no, yellow_fever_date,
                        oral_polio_manufacturer, oral_polio_batch_no, oral_polio_date,
                        meningococcal_manufacturer, meningococcal_batch_no, meningococcal_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        token,
                        cert_no,
                        request.form.get("recipient"),
                        request.form.get("dob"),
                        request.form.get("sex"),
                        request.form.get("nationality"),
                        request.form.get("organization"),
                        request.form.get("issue_date"),
                        request.form.get("supervising_clinician"),
                        request.form.get("clinician_signature"),
                        request.form.get("authorized_by"),
                        request.form.get("yellow_fever_manufacturer"),
                        request.form.get("yellow_fever_batch_no"),
                        request.form.get("yellow_fever_date"),
                        request.form.get("oral_polio_manufacturer"),
                        request.form.get("oral_polio_batch_no"),
                        request.form.get("oral_polio_date"),
                        request.form.get("meningococcal_manufacturer"),
                        request.form.get("meningococcal_batch_no"),
                        request.form.get("meningococcal_date"),
                    ),
                )
                con.commit()
            return redirect(url_for("admin_dashboard"))
        except sqlite3.IntegrityError:
            error = "Traveler ID hororiin kuusameera. Maaloo irra deebi'ii yaali."

    return render_template_string(CREATE_HTML, auto_id=auto_id, error=error)


@app.route("/verify/<token>")
def verify(token):
    with get_db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?", (token,)
        ).fetchone()

    if not cert:
        return """
        <div style="font-family: Arial; text-align: center; margin-top: 50px;">
            <h2>Record Not Found</h2>
            <p>No matching demonstration record was found in database.</p>
        </div>
        """, 404

    return render_template_string(VERIFY_HTML, cert=cert)


@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    with get_db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?", (token,)
        ).fetchone()

    if not cert:
        abort(404)

    PAGE_SIZE = (13 * cm, 9.3 * cm)
    traveler_id = cert["cert_no"]

    # QR Code - Traveler ID qofa of keessaa qaba
    qr = qrcode.make(traveler_id)
    qr_io = io.BytesIO()
    qr.save(qr_io, format="PNG")
    qr_io.seek(0)

    buff = io.BytesIO()
    c = canvas.Canvas(buff, pagesize=PAGE_SIZE)
    w, h = PAGE_SIZE

    # Background
    c.setFillColor(colors.white)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Border
    c.setStrokeColor(colors.HexColor("#174a6e"))
    c.setLineWidth(1.5)
    c.rect(10, 10, w - 20, h - 20, fill=0, stroke=1)

    # Header
    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(w / 2, h - 23, "PERSONAL VACCINATION RECORD")

    c.setFillColor(colors.red)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(
        w / 2, h - 34, "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE"
    )

    def draw_line(x, y, label, value):
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 5.2)
        c.drawString(x, y, label + ":")
        c.setFont("Helvetica", 5.2)
        c.drawString(x + 68, y, str(value or "Not recorded")[:42])

    # LEFT COLUMN
    left_x = 18
    y = h - 52

    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(left_x, y, "TRAVELER INFORMATION")
    y -= 13

    personal_data = [
        ("Traveler ID", traveler_id),
        ("Full Name", cert["recipient"]),
        ("Date of Birth", cert["dob"]),
        ("Sex", cert["sex"]),
        ("Nationality", cert["nationality"]),
        ("Organization", cert["organization"]),
        ("Record Date", cert["issue_date"]),
    ]

    for label, value in personal_data:
        draw_line(left_x, y, label, value)
        y -= 11

    # Clinician information
    y -= 5
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(left_x, y, "CLINICIAN INFORMATION")
    y -= 13

    clinician_data = [
        ("Clinician", cert["supervising_clinician"]),
        ("Signature Ref.", cert["clinician_signature"]),
        ("Authorized By", cert["authorized_by"]),
    ]

    for label, value in clinician_data:
        draw_line(left_x, y, label, value)
        y -= 11

    # RIGHT COLUMN
    right_x = 190
    y = h - 52

    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(right_x, y, "VACCINATION DETAILS")
    y -= 15

    vaccines = [
        (
            "YELLOW FEVER",
            [
                ("Manufacturer", cert["yellow_fever_manufacturer"]),
                ("Batch Number", cert["yellow_fever_batch_no"]),
                ("Date", cert["yellow_fever_date"]),
            ],
        ),
        (
            "ORAL POLIO",
            [
                ("Manufacturer", cert["oral_polio_manufacturer"]),
                ("Batch Number", cert["oral_polio_batch_no"]),
                ("Date", cert["oral_polio_date"]),
            ],
        ),
        (
            "MENINGOCOCCAL",
            [
                ("Manufacturer", cert["meningococcal_manufacturer"]),
                ("Batch Number", cert["meningococcal_batch_no"]),
                ("Date", cert["meningococcal_date"]),
            ],
        ),
    ]

    for vaccine_name, details in vaccines:
        c.setFillColor(colors.HexColor("#174a6e"))
        c.setFont("Helvetica-Bold", 5.8)
        c.drawString(right_x, y, vaccine_name)
        y -= 11

        for label, value in details:
            draw_line(right_x, y, label, value)
            y -= 10

        y -= 5

    # QR Code
    c.drawImage(
        ImageReader(qr_io),
        w - 53,
        17,
        width=35,
        height=35,
        preserveAspectRatio=True,
        mask="auto",
    )

    c.setFont("Helvetica-Bold", 4.5)
    c.drawString(w - 58, 12, "TRAVELER ID QR")

    # Verification link
    verify_link = url_for("verify", token=token, _external=True)

    link_text = "OPEN RECORD VERIFICATION"
    link_x = 18
    link_y = 48

    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 7)
    c.drawString(link_x, link_y, link_text)

    text_width = c.stringWidth(link_text, "Helvetica-Bold", 7)

    c.linkURL(
        verify_link, (link_x, link_y - 3, link_x + text_width, link_y + 10), relative=0
    )

    c.setFillColor(colors.blue)
    c.setFont("Helvetica", 4)
    c.drawString(18, 38, verify_link)

    # Footer
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 4.5)
    c.drawString(18, 18, "Demonstration personal record only.")

    c.save()
    buff.seek(0)

    # Check if download or print/view inline requested
    disposition = (
        "inline" if request.args.get("action") == "print" else "attachment"
    )

    return send_file(
        buff,
        mimetype="application/pdf",
        as_attachment=(disposition == "attachment"),
        download_name=f"{traveler_id}-record.pdf",
    )


# ---------------- HTML TEMPLATES ---------------- #

ADMIN_HTML = """
<!doctype html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background: #f4f6f9; }
        h1 { color: #174a6e; }
        .btn { background: #174a6e; color: white; padding: 7px 14px; text-decoration: none; border-radius: 4px; font-size: 13px; display: inline-block; }
        .btn-print { background: #2e7d32; }
        .btn-verify { background: #0288d1; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; font-size: 14px; }
        th { background: #174a6e; color: white; }
        tr:hover { background: #f1f1f1; }
        .search-box { margin-bottom: 20px; }
        input[type="text"] { padding: 6px; width: 260px; }
    </style>
</head>
<body>
    <h1>Vaccination Records Dashboard</h1>
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <form method="get" class="search-box">
            <input type="text" name="q" value="{{ query }}" placeholder="Search by Traveler ID or Name...">
            <button type="submit" class="btn" style="border:none; cursor:pointer;">Search</button>
            {% if query %}<a href="/admin" style="margin-left: 10px; font-size: 14px;">Clear Search</a>{% endif %}
        </form>
        <a href="/create" class="btn">+ Create New Record</a>
    </div>
    <table>
        <tr>
            <th>Traveler ID</th>
            <th>Recipient Name</th>
            <th>Nationality</th>
            <th>Issue Date</th>
            <th>Actions</th>
        </tr>
        {% for r in records %}
        <tr>
            <td><strong>{{ r.cert_no }}</strong></td>
            <td>{{ r.recipient }}</td>
            <td>{{ r.nationality }}</td>
            <td>{{ r.issue_date }}</td>
            <td>
                <a href="/certificate/{{ r.token }}.pdf" class="btn">Download PDF</a>
                <a href="/certificate/{{ r.token }}.pdf?action=print" target="_blank" class="btn btn-print">Print PDF</a>
                <a href="/verify/{{ r.token }}" target="_blank" class="btn btn-verify">Verification Link</a>
            </td>
        </tr>
        {% else %}
        <tr><td colspan="5" style="text-align: center;">Record tokkollee hin argamne.</td></tr>
        {% endfor %}
    </table>
</body>
</html>
"""

CREATE_HTML = """
<!doctype html>
<html>
<head>
    <title>Create Record</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 30px; background: #f4f6f9; }
        .form-container { background: white; padding: 25px; border-radius: 6px; max-width: 650px; margin: 0 auto; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); }
        input { width: 100%; padding: 8px; margin: 4px 0 14px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        label { font-weight: bold; font-size: 13px; color: #333; }
        .btn { background: #174a6e; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .error { color: red; font-weight: bold; margin-bottom: 15px; }
        .readonly-id { background: #eef2f5; font-weight: bold; color: #174a6e; letter-spacing: 1px; }
    </style>
</head>
<body>
    <div class="form-container">
        <h1>Create Vaccination Record</h1>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form method="POST">
            <label>Traveler ID (Auto-Generated: Qubee 4 + Lakkoofsa 6):</label>
            <input type="text" name="cert_no" value="{{ auto_id }}" class="readonly-id" readonly>

            <label>Recipient Full Name:</label>
            <input type="text" name="recipient" required placeholder="Abebe Bikila">

            <label>Date of Birth:</label>
            <input type="date" name="dob">

            <label>Sex:</label>
            <input type="text" name="sex" placeholder="Male / Female">

            <label>Nationality:</label>
            <input type="text" name="nationality" placeholder="Ethiopian">

            <label>Organization:</label>
            <input type="text" name="organization" placeholder="Organization Name">

            <label>Record Date:</label>
            <input type="date" name="issue_date">

            <h3 style="color: #174a6e; margin-top: 20px;">Clinician Information</h3>
            <label>Supervising Clinician:</label>
            <input type="text" name="supervising_clinician">

            <label>Signature Ref.:</label>
            <input type="text" name="clinician_signature">

            <label>Authorized By:</label>
            <input type="text" name="authorized_by">

            <h3 style="color: #174a6e; margin-top: 20px;">Vaccination Details</h3>
            
            <label>Yellow Fever (Manufacturer / Batch / Date):</label>
            <input type="text" name="yellow_fever_manufacturer" placeholder="Manufacturer">
            <input type="text" name="yellow_fever_batch_no" placeholder="Batch Number">
            <input type="date" name="yellow_fever_date">

            <label>Oral Polio (Manufacturer / Batch / Date):</label>
            <input type="text" name="oral_polio_manufacturer" placeholder="Manufacturer">
            <input type="text" name="oral_polio_batch_no" placeholder="Batch Number">
            <input type="date" name="oral_polio_date">

            <label>Meningococcal (Manufacturer / Batch / Date):</label>
            <input type="text" name="meningococcal_manufacturer" placeholder="Manufacturer">
            <input type="text" name="meningococcal_batch_no" placeholder="Batch Number">
            <input type="date" name="meningococcal_date">

            <button type="submit" class="btn">Save Record</button>
        </form>
        <p style="margin-top: 15px;"><a href="/admin">&larr; Back to Dashboard</a></p>
    </div>
</body>
</html>
"""

VERIFY_HTML = """
<!doctype html>
<html>
<head>
    <title>Record Verification</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 50px; background: #f4f6f9; text-align: center; }
        .card { background: white; padding: 30px; border-radius: 8px; display: inline-block; text-align: left; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); width: 400px; }
        h2 { color: #2e7d32; text-align: center; margin-top: 0; }
        .field { margin-bottom: 10px; font-size: 14px; }
        .label { font-weight: bold; color: #555; }
    </style>
</head>
<body>
    <div class="card">
        <h2>✓ Record Verified</h2>
        <div class="field"><span class="label">Traveler ID:</span> {{ cert.cert_no }}</div>
        <div class="field"><span class="label">Full Name:</span> {{ cert.recipient }}</div>
        <div class="field"><span class="label">Nationality:</span> {{ cert.nationality }}</div>
        <div class="field"><span class="label">Organization:</span> {{ cert.organization or 'N/A' }}</div>
        <div class="field"><span class="label">Record Date:</span> {{ cert.issue_date }}</div>
        <div class="field"><span class="label">Clinician:</span> {{ cert.supervising_clinician }}</div>
        <hr style="margin: 20px 0; border:0; border-top:1px solid #ddd;">
        <p style="color: #777; font-size: 12px; text-align: center; margin: 0;">This is an authentic registered demonstration record.</p>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)
