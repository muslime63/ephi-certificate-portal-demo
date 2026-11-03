@app.route("/verify/<token>")
def verify(token):
    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        return """
        <h2>Record Not Found</h2>
        <p>No matching demonstration record was found.</p>
        """, 404

    return render_template(
        "verify.html",
        cert=cert
    )@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    from reportlab.lib.units import cm
    from flask import url_for

    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    # Landscape page: 13 cm x 9.3 cm
    PAGE_SIZE = (13 * cm, 9.3 * cm)

    traveler_id = cert["cert_no"]

    # QR Code contains Traveler ID only
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
    c.drawCentredString(
        w / 2, h - 23,
        "PERSONAL VACCINATION RECORD"
    )

    c.setFillColor(colors.red)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawCentredString(
        w / 2, h - 34,
        "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE"
    )

    # Information line
    def draw_line(x, y, label, value):
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 5.2)
        c.drawString(x, y, label + ":")

        c.setFont("Helvetica", 5.2)
        c.drawString(
            x + 68, y,
            str(value or "Not recorded")[:42]
        )

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
            ]
        ),
        (
            "ORAL POLIO",
            [
                ("Manufacturer", cert["oral_polio_manufacturer"]),
                ("Batch Number", cert["oral_polio_batch_no"]),
                ("Date", cert["oral_polio_date"]),
            ]
        ),
        (
            "MENINGOCOCCAL",
            [
                ("Manufacturer", cert["meningococcal_manufacturer"]),
                ("Batch Number", cert["meningococcal_batch_no"]),
                ("Date", cert["meningococcal_date"]),
            ]
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
        w - 53, 17,
        width=35,
        height=35,
        preserveAspectRatio=True,
        mask="auto"
    )

    c.setFont("Helvetica-Bold", 4.5)
    c.drawString(w - 58, 12, "TRAVELER ID QR")

    # Clickable verification link
    verify_link = url_for(
        "verify",
        token=token,
        _external=True
    )

    link_text = "OPEN RECORD VERIFICATION"
    link_x = 18
    link_y = 48

    c.setFillColor(colors.HexColor("#174a6e"))
    c.setFont("Helvetica-Bold", 7)

    c.drawString(
        link_x,
        link_y,
        link_text
    )

    text_width = c.stringWidth(
        link_text,
        "Helvetica-Bold",
        7
    )

    c.linkURL(
        verify_link,
        (
            link_x,
            link_y - 3,
            link_x + text_width,
            link_y + 10
        ),
        relative=0
    )

    # Footer
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 4.5)

    c.drawString(
        18, 18,
        "Demonstration personal record only."
    )

    c.save()
    buff.seek(0)

    return send_file(
        buff,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{traveler_id}-record.pdf"
    )
