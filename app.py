
@app.route("/certificate/<token>.pdf")
@login_required
def certificate_pdf(token):
    certificate, vaccinations = get_record(token)

    if not certificate:
        abort(404)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle("Vaccination Record Copy")

    YELLOW = (1.0, 0.91, 0.25)
    DARK = (0.08, 0.20, 0.30)
    WHITE = (1, 1, 1)

    def background():
        pdf.setFillColorRGB(*YELLOW)
        pdf.rect(0, 0, width, height, fill=1, stroke=0)

        pdf.setStrokeColorRGB(*DARK)
        pdf.setLineWidth(1.2)
        pdf.rect(
            22, 22, width - 44, height - 44,
            fill=0, stroke=1
        )

    def text(x, y, value, size=10, bold=False):
        pdf.setFillColorRGB(*DARK)
        font = "Helvetica-Bold" if bold else "Helvetica"
        pdf.setFont(font, size)
        pdf.drawString(x, y, str(value or "-")[:100])

    def heading(value, y):
        pdf.setFillColorRGB(*DARK)
        pdf.setFont("Helvetica-Bold", 15)
        pdf.drawCentredString(width / 2, y, value)

    verification_url = url_for(
        "verify",
        token=certificate["token"],
        _external=True
    )

    # PAGE 1: RECORD INFORMATION
    background()

    pdf.setFillColorRGB(*DARK)
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawCentredString(
        width / 2, height - 65,
        "VACCINATION RECORD COPY"
    )

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(
        width / 2, height - 85,
        "DEMO / RECORD COPY - NOT AN OFFICIAL INTERNATIONAL CERTIFICATE"
    )

    pdf.setStrokeColorRGB(*DARK)
    pdf.line(40, height - 105, width - 40, height - 105)

    heading("INFORMATION FOR RECORD HOLDERS", height - 140)

    text(
        45, height - 170,
        "This document is a copy of vaccination information saved in the portal.",
        9
    )
    text(
        45, height - 187,
        "It is not a government-issued or WHO International Certificate.",
        9
    )
    text(
        45, height - 204,
        "For official travel requirements, contact an authorized health authority.",
        9
    )

    pdf.line(40, height - 225, width - 40, height - 225)

    heading("RECIPIENT INFORMATION", height - 255)

    details = [
        ("Record Number", certificate.get("cert_no")),
        ("Traveler ID", certificate.get("traveler_id")),
        ("Full Name", certificate.get("recipient")),
        ("Date of Birth", certificate.get("dob")),
        ("Sex", certificate.get("sex")),
        ("Nationality", certificate.get("nationality")),
        ("Organization", certificate.get("organization")),
        ("Issue Date", certificate.get("issue_date")),
        ("Supervising Clinician", certificate.get("supervising_clinician")),
        ("Authorized By", certificate.get("authorized_by")),
        ("Record Status", certificate.get("status"))
    ]

    y = height - 290

    for label, value in details:
        text(55, y, label + ":", 10, True)
        text(220, y, value, 10)
        y -= 23

    # QR code for online record verification
    qr_image = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.drawImage(
        ImageReader(qr_buffer),
        width - 125, 45,
        width=75, height=75
    )

    text(45, 90, "Online record verification:", 8, True)
    text(45, 75, verification_url, 7)

    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(
        width / 2, 40,
        "DEMO / RECORD COPY - NOT VALID FOR INTERNATIONAL TRAVEL"
    )

    pdf.showPage()

    # PAGE 2: VACCINATION DETAILS
    background()

    pdf.setFillColorRGB(*DARK)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(
        width / 2, height - 65,
        "VACCINATION DETAILS"
    )

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(
        width / 2, height - 85,
        "PERSONAL VACCINATION RECORD"
    )

    pdf.line(40, height - 105, width - 40, height - 105)

    text(
        45, height - 135,
        "Recipient: " + str(certificate.get("recipient") or "-"),
        11, True
    )
    text(
        45, height - 155,
        "Record Number: " + str(certificate.get("cert_no") or "-"),
        10
    )
    text(
        45, height - 175,
        "Traveler ID: " + str(certificate.get("traveler_id") or "-"),
        10
    )

    # Vaccination table
    table_x = 35
    table_top = height - 215

    columns = [
        ("Date of Vaccination", 105),
        ("Vaccine Type", 125),
        ("Manufacturer", 115),
        ("Batch Number", 95)
    ]

    row_height = 42
    table_width = sum(item[1] for item in columns)

    # Table header
    pdf.setFillColorRGB(*DARK)
    pdf.rect(
        table_x, table_top - row_height,
        table_width, row_height,
        fill=1, stroke=1
    )

    x = table_x

    for label, col_width in columns:
        pdf.setFillColorRGB(*WHITE)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawCentredString(
            x + col_width / 2,
            table_top - 25,
            label
        )
        x += col_width

    # Vaccine rows
    y = table_top - row_height

    for vaccine in vaccinations:
        y -= row_height

        pdf.setFillColorRGB(*YELLOW)
        pdf.rect(
            table_x, y,
            table_width, row_height,
            fill=1, stroke=1
        )

        values = [
            vaccine.get("vaccination_date"),
            vaccine.get("vaccine_type"),
            vaccine.get("manufacturer"),
            vaccine.get("batch_no")
        ]

        x = table_x

        for index, (_, col_width) in enumerate(columns):
            pdf.setStrokeColorRGB(*DARK)
            pdf.line(x, y, x, y + row_height)

            pdf.setFillColorRGB(*DARK)
            pdf.setFont("Helvetica", 8)

            value = str(values[index] or "-")[:24]

            pdf.drawCentredString(
                x + col_width / 2,
                y + 16,
                value
            )

            x += col_width

        pdf.line(x, y, x, y + row_height)

    # Authorized record information
    y -= 55

    text(45, y, "Authorized By:", 10, True)
    text(150, y, certificate.get("authorized_by"), 10)

    y -= 30

    text(45, y, "Supervising Clinician:", 10, True)
    text(
        190, y,
        certificate.get("supervising_clinician"),
        10
    )

    y -= 45

    pdf.setStrokeColorRGB(*DARK)
    pdf.line(45, y, width - 45, y)

    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawCentredString(
        width / 2, y - 25,
        "DEMO / RECORD COPY - NOT AN OFFICIAL CERTIFICATE"
    )

    pdf.setFont("Helvetica", 8)
    pdf.drawCentredString(
        width / 2, y - 42,
        "Verify saved record using the QR code on page 1."
    )

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{certificate.get('cert_no', 'record')}.pdf",
        mimetype="application/pdf"
    )
