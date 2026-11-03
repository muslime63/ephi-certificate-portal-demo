
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
        pdf.setLineWidth(1.5)
        pdf.rect(22, 22, width - 44, height - 44,
                 fill=0, stroke=1)

    def text(x, y, value, size=10, bold=False):
        pdf.setFillColorRGB(*DARK)
        font = "Helvetica-Bold" if bold else "Helvetica"
        pdf.setFont(font, size)
        pdf.drawString(x, y, str(value or "-")[:100])

    def heading(value, y):
        pdf.setFillColorRGB(*DARK)
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawCentredString(width / 2, y, value)

    def page_title(title, subtitle):
        pdf.setFillColorRGB(*DARK)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawCentredString(width / 2, height - 65, title)

        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawCentredString(width / 2, height - 85, subtitle)

        pdf.setStrokeColorRGB(*DARK)
        pdf.line(40, height - 105, width - 40, height - 105)

    verification_url = url_for(
        "verify",
        token=certificate["token"],
        _external=True
    )


    text(
        45, height - 170,
        "This document is a copy of vaccination information saved in the portal.",
        8
    )
    text(
        45, height - 187,
        "It is not a government-issued or WHO International Certificate.",
        8
    )
    text(
        45, height - 204,
        "For official travel requirements, contact an authorized health authority.",
        8
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
        ("Supervising Clinician",
         certificate.get("supervising_clinician")),
        ("Authorized By", certificate.get("authorized_by")),
        ("Record Status", certificate.get("status"))
    ]

    y = height - 290

    for label, value in details:
        text(55, y, label + ":", 9, True)
        text(220, y, value, 9)
        y -= 22

    # QR code for online verification
    qr_image = qrcode.make(verification_url)
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    pdf.drawImage(
        ImageReader(qr_buffer),
        width - 125, 65,
        width=75, height=75
    )

    text(45, 100, "Online record verification:", 8, True)
    text(45, 84, verification_url, 6)

    pdf.setFillColorRGB(*DARK)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(
        width / 2, 40,
        "DEMO / RECORD COPY - NOT VALID FOR INTERNATIONAL TRAVEL"
    )

    pdf.showPage()

    # ---------------------------------
    # PAGE 2 AND EXTRA PAGES:
    # VACCINATION DETAILS
    # ---------------------------------

    columns = [
        ("Date of Vaccination", 105),
        ("Vaccine Type", 125),
        ("Manufacturer", 115),
        ("Batch Number", 95)
    ]

    table_x = 35
    table_width = sum(col[1] for col in columns)
    row_height = 32

    # Split vaccine records into groups of 9
    vaccine_list = list(vaccinations or [])
    chunks = [
        vaccine_list[i:i + 9]
        for i in range(0, len(vaccine_list), 9)
    ]

    if not chunks:
        chunks = [[]]

    for page_index, vaccine_chunk in enumerate(chunks):

        background()

        page_title(
            "VACCINATION DETAILS",
            "PERSONAL VACCINATION RECORD - DEMO COPY"
        )

        text(
            45, height - 135,
            "Recipient: " + str(
                certificate.get("recipient") or "-"
            ),
            10, True
        )

        text(
            45, height - 155,
            "Record Number: " + str(
                certificate.get("cert_no") or "-"
            ),
            9
        )

        text(
            45, height - 175,
            "Traveler ID: " + str(
                certificate.get("traveler_id") or "-"
            ),
            9
        )

        if page_index > 0:
            text(
                45, height - 195,
                "Additional vaccination records",
                9, True
            )

        table_top = height - 220

        # Table header
        pdf.setFillColorRGB(*DARK)
        pdf.rect(
            table_x,
            table_top - row_height,
            table_width,
            row_height,
            fill=1,
            stroke=1
        )

        x = table_x

        for label, col_width in columns:
            pdf.setFillColorRGB(*WHITE)
            pdf.setFont("Helvetica-Bold", 7)

            pdf.drawCentredString(
                x + col_width / 2,
                table_top - 19,
                label
            )

            x += col_width

        # Vaccine records
        y = table_top - row_height

        for vaccine in vaccine_chunk:
            y -= row_height

            pdf.setFillColorRGB(*YELLOW)
            pdf.rect(
                table_x,
                y,
                table_width,
                row_height,
                fill=1,
                stroke=1
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
                pdf.setFont("Helvetica", 7)

                value = str(values[index] or "-")[:24]

                pdf.drawCentredString(
                    x + col_width / 2,
                    y + 12,
                    value
                )

                x += col_width

            pdf.line(x, y, x, y + row_height)

        # Authorization details on final page only
        if page_index == len(chunks) - 1:

            auth_y = y - 55

            text(45, auth_y, "Authorized By:", 9, True)
            text(
                150, auth_y,
                certificate.get("authorized_by"),
                9
            )

            auth_y -= 28

            text(
                45, auth_y,
                "Supervising Clinician:",
                9, True
            )

            text(
                190, auth_y,
                certificate.get("supervising_clinician"),
                9
            )

            auth_y -= 45

            pdf.setStrokeColorRGB(*DARK)
            pdf.line(45, auth_y, width - 45, auth_y)

            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawCentredString(
                width / 2,
                auth_y - 23,
                "DEMO / RECORD COPY - NOT AN OFFICIAL CERTIFICATE"
            )

            pdf.setFont("Helvetica", 8)
            pdf.drawCentredString(
                width / 2,
                auth_y - 40,
                "Verify saved record using the QR code on page 1."
            )

        pdf.showPage()

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{certificate.get('cert_no', 'record')}.pdf",
        mimetype="application/pdf"
    )
import secrets
import string

def generate_traveler_id(existing_ids=None):
    existing_ids = existing_ids or set()

    while True:
        letters = ''.join(
            secrets.choice(string.ascii_uppercase)
            for _ in range(4)
        )

        numbers = ''.join(
            secrets.choice(string.digits)
            for _ in range(6)
        )

        traveler_id = letters + numbers

        if traveler_id not in existing_ids:
            return traveler_id
