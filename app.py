
@app.route("/certificate/<token>.pdf")
def certificate_pdf(token):
    with db() as con:
        cert = con.execute(
            "SELECT * FROM certificates WHERE token=?",
            (token,)
        ).fetchone()

    if not cert:
        abort(404)

    # QR Code contains ONLY the Traveler ID.
    traveler_id = cert["cert_no"]
    qr = qrcode.make(traveler_id)

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
    c.drawCentredString(
        w / 2, h - 65,
        "PERSONAL VACCINATION RECORD"
    )

    c.setFillColor(colors.red)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(
        w / 2, h - 85,
        "RECORD COPY - NOT AN INTERNATIONAL CERTIFICATE"
    )

    draw_y = h - 125

    def line(label, value):
        nonlocal draw_y
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(48, draw_y, label + ":")
        c.setFont("Helvetica", 9)
        c.drawString(
            190, draw_y,
            str(value or "Not recorded")[:75]
        )
        draw_y -= 19

    line("Traveler ID", traveler_id)
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

    # QR Code: Traveler ID only
    c.drawImage(
        ImageReader(qr_io),
        w - 125, 45,
        width=75,
        height=75,
        preserveAspectRatio=True,
        mask="auto"
    )

    c.setFont("Helvetica-Bold", 8)
    c.drawString(w - 145, 35, "TRAVELER ID QR")

    c.setFont("Helvetica", 7)
    c.drawString(48, 55, "Demonstration personal record only.")
    c.drawString(
        48, 43,
        "Not valid as an official travel or international vaccination certificate."
    )

    c.save()
    buff.seek(0)

    return send_file(
        buff,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"{traveler_id}-record.pdf"
    )
