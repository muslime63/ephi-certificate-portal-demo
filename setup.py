import os

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)

# Dictionary containing filename as key and HTML content as value
templates = {
    'login.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPHI Admin Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center py-4" style="height: 100vh;">
    <main class="form-signin w-100 m-auto" style="max-width: 400px;">
        <form method="POST" class="card p-4 shadow-sm">
            <h1 class="h3 mb-3 fw-normal text-center">EPHI Portal Login</h1>
            
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, message in messages %}
                  <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
              {% endif %}
            {% endwith %}

            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" class="form-control" id="username" name="username" required autocomplete="username">
            </div>
            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required autocomplete="current-password">
            </div>
            <button class="w-100 btn btn-primary py-2" type="submit">Sign in</button>
        </form>
    </main>
</body>
</html>''',

    'admin.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPHI Admin Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">EPHI Vaccination Portal</a>
            <div class="d-flex">
                <a href="{{ url_for('database_backup') }}" class="btn btn-outline-light btn-sm me-2">Database Backup</a>
                <a href="{{ url_for('audit_logs') }}" class="btn btn-outline-light btn-sm me-2">Audit Logs</a>
                <a href="{{ url_for('logout') }}" class="btn btn-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }} alert-dismissible fade show">
                {{ message }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <h2 class="mb-3">Administration Dashboard</h2>
        
        <div class="row text-white my-3 g-3">
            <div class="col-md-3"><div class="p-3 bg-primary rounded shadow-sm">Total Records: <strong>{{ total }}</strong></div></div>
            <div class="col-md-3"><div class="p-3 bg-success rounded shadow-sm">Active Records: <strong>{{ active }}</strong></div></div>
            <div class="col-md-3"><div class="p-3 bg-warning rounded shadow-sm text-dark">Revoked Records: <strong>{{ revoked }}</strong></div></div>
            <div class="col-md-3"><div class="p-3 bg-secondary rounded shadow-sm">Archived Records: <strong>{{ archived }}</strong></div></div>
        </div>

        <div class="d-flex justify-content-between align-items-center my-4">
            <a href="{{ url_for('issue_record') }}" class="btn btn-success">+ Issue New Vaccination Record</a>
            <form class="d-flex" method="GET" action="{{ url_for('dashboard') }}">
                <input class="form-control me-2" type="search" name="search" placeholder="Search Traveler ID or Name" value="{{ request.args.get('search', '') }}">
                <button class="btn btn-outline-success" type="submit">Search</button>
            </form>
        </div>

        <div class="table-responsive bg-white shadow-sm rounded">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-dark">
                    <tr>
                        <th>Traveler ID</th>
                        <th>Full Name</th>
                        <th>DOB</th>
                        <th>Sex</th>
                        <th>Nationality</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for r in records %}
                    <tr>
                        <td><strong>{{ r.traveler_id }}</strong></td>
                        <td>{{ r.full_name }}</td>
                        <td>{{ r.dob }}</td>
                        <td>{{ r.sex }}</td>
                        <td>{{ r.nationality }}</td>
                        <td>
                            <span class="badge bg-{{ 'success' if r.status=='ACTIVE' else ('danger' if r.status=='REVOKED' else 'secondary') }}">
                                {{ r.status }}
                            </span>
                        </td>
                        <td>
                            <a href="{{ url_for('view_certificate', traveler_id=r.traveler_id) }}" class="btn btn-sm btn-info text-white">View</a>
                            <a href="{{ url_for('download_pdf', traveler_id=r.traveler_id) }}" class="btn btn-sm btn-dark">PDF</a>
                            
                            {% if r.status == 'ACTIVE' %}
                            <button type="button" class="btn btn-sm btn-warning" data-bs-toggle="modal" data-bs-target="#revokeModal{{ r.traveler_id }}">Revoke</button>
                            <a href="{{ url_for('archive_record', traveler_id=r.traveler_id) }}" class="btn btn-sm btn-secondary">Archive</a>
                            {% elif r.status == 'REVOKED' %}
                            <a href="{{ url_for('restore_record', traveler_id=r.traveler_id) }}" class="btn btn-sm btn-success">Restore</a>
                            {% endif %}
                        </td>
                    </tr>

                    <!-- Modal for Revoke Reason -->
                    <div class="modal fade" id="revokeModal{{ r.traveler_id }}" tabindex="-1">
                      <div class="modal-dialog">
                        <form method="POST" action="{{ url_for('revoke_record', traveler_id=r.traveler_id) }}" class="modal-content">
                          <div class="modal-header">
                            <h5 class="modal-title">Revoke Record: {{ r.traveler_id }}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                          </div>
                          <div class="modal-body">
                            <label class="form-label">Sababa Revoke Godhameef:</label>
                            <textarea class="form-control" name="reason" rows="3" required></textarea>
                          </div>
                          <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="submit" class="btn btn-danger">Confirm Revoke</button>
                          </div>
                        </form>
                      </div>
                    </div>
                    {% else %}
                    <tr>
                        <td colspan="7" class="text-center py-4">Record-iin tokkollee hin argamne.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>''',

    'issue.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Issue New Vaccination Record</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container my-5" style="max-width: 900px;">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>Issue New Vaccination Record</h2>
            <a href="{{ url_for('dashboard') }}" class="btn btn-outline-secondary">← Back to Dashboard</a>
        </div>

        <form method="POST" class="card p-4 shadow-sm">
            <h4 class="text-primary mb-3">1. Traveler Information</h4>
            <div class="row g-3 mb-3">
                <div class="col-md-6">
                    <label class="form-label">Full Name</label>
                    <input type="text" class="form-control" name="full_name" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Date of Birth</label>
                    <input type="date" class="form-control" name="dob" required>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Sex</label>
                    <select class="form-select" name="sex" required>
                        <option value="Male">Male</option>
                        <option value="Female">Female</option>
                    </select>
                </div>
            </div>
            <div class="mb-4">
                <label class="form-label">Nationality</label>
                <input type="text" class="form-control" name="nationality" value="Ethiopian" required>
            </div>

            <hr>
            <h4 class="text-primary mb-3">2. Vaccination Details</h4>

            <h6 class="fw-bold">Yellow Fever (YF)</h6>
            <div class="row g-3 mb-3">
                <div class="col-md-4"><input type="text" class="form-control" name="yf_manufacturer" placeholder="Manufacturer"></div>
                <div class="col-md-4"><input type="text" class="form-control" name="yf_batch" placeholder="Batch Number"></div>
                <div class="col-md-4"><input type="date" class="form-control" name="yf_date"></div>
            </div>

            <h6 class="fw-bold">Oral Polio Vaccine (OPV)</h6>
            <div class="row g-3 mb-3">
                <div class="col-md-4"><input type="text" class="form-control" name="opv_manufacturer" placeholder="Manufacturer"></div>
                <div class="col-md-4"><input type="text" class="form-control" name="opv_batch" placeholder="Batch Number"></div>
                <div class="col-md-4"><input type="date" class="form-control" name="opv_date"></div>
            </div>

            <h6 class="fw-bold">Meningococcal A, C, Y, W135</h6>
            <div class="row g-3 mb-4">
                <div class="col-md-4"><input type="text" class="form-control" name="men_manufacturer" placeholder="Manufacturer"></div>
                <div class="col-md-4"><input type="text" class="form-control" name="men_batch" placeholder="Batch Number"></div>
                <div class="col-md-4"><input type="date" class="form-control" name="men_date"></div>
            </div>

            <hr>
            <h4 class="text-primary mb-3">3. Clinician Authorization</h4>
            <div class="row g-3 mb-3">
                <div class="col-md-6">
                    <label class="form-label">Organization / Center</label>
                    <input type="text" class="form-control" name="organization" value="EPHI Center">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Supervising Clinician</label>
                    <input type="text" class="form-control" name="supervising_clinician">
                </div>
            </div>
            <div class="row g-3 mb-4">
                <div class="col-md-6">
                    <label class="form-label">Signature Reference</label>
                    <input type="text" class="form-control" name="signature_ref">
                </div>
                <div class="col-md-6">
                    <label class="form-label">Authorized By</label>
                    <input type="text" class="form-control" name="authorized_by">
                </div>
            </div>

            <button type="submit" class="btn btn-primary btn-lg w-100">Generate Certificate & Traveler ID</button>
        </form>
    </div>
</body>
</html>''',

    'certificate.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Certificate - {{ record.traveler_id }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container my-5 card p-5 shadow-sm" style="max-width: 750px;">
        <div class="text-center mb-4">
            <h2 class="fw-bold text-dark">ETHIOPIAN PUBLIC HEALTH INSTITUTE</h2>
            <h4 class="text-secondary">INTERNATIONAL VACCINATION CERTIFICATE</h4>
        </div>

        <div class="row my-4 align-items-center">
            <div class="col-md-8">
                <p class="fs-5"><strong>Traveler ID:</strong> <span class="badge bg-dark">{{ record.traveler_id }}</span></p>
                <p><strong>Full Name:</strong> {{ record.full_name }}</p>
                <p><strong>DOB:</strong> {{ record.dob }} | <strong>Sex:</strong> {{ record.sex }}</p>
                <p><strong>Nationality:</strong> {{ record.nationality }}</p>
                <p><strong>Status:</strong> 
                    <span class="badge bg-{{ 'success' if record.status=='ACTIVE' else ('danger' if record.status=='REVOKED' else 'secondary') }}">
                        {{ record.status }}
                    </span>
                </p>
            </div>
            <div class="col-md-4 text-center">
                <img src="data:image/png;base64,{{ qr_code }}" alt="QR Code" class="img-thumbnail" style="width: 140px;">
                <p class="small mt-2"><a href="{{ verify_url }}" target="_blank" class="text-decoration-none">Verify Online</a></p>
            </div>
        </div>

        <hr>
        <h5 class="fw-bold text-primary mb-3">Vaccine Details</h5>
        <table class="table table-bordered mb-4">
            <thead class="table-light">
                <tr>
                    <th>Vaccine</th>
                    <th>Manufacturer</th>
                    <th>Batch No.</th>
                    <th>Date</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Yellow Fever</td>
                    <td>{{ record.yf_manufacturer or 'N/A' }}</td>
                    <td>{{ record.yf_batch or 'N/A' }}</td>
                    <td>{{ record.yf_date or 'N/A' }}</td>
                </tr>
                <tr>
                    <td>OPV</td>
                    <td>{{ record.opv_manufacturer or 'N/A' }}</td>
                    <td>{{ record.opv_batch or 'N/A' }}</td>
                    <td>{{ record.opv_date or 'N/A' }}</td>
                </tr>
                <tr>
                    <td>Meningococcal</td>
                    <td>{{ record.men_manufacturer or 'N/A' }}</td>
                    <td>{{ record.men_batch or 'N/A' }}</td>
                    <td>{{ record.men_date or 'N/A' }}</td>
                </tr>
            </tbody>
        </table>

        <div class="row my-3">
            <div class="col-md-6">
                <p><strong>Organization:</strong> {{ record.organization or 'EPHI' }}</p>
                <p><strong>Clinician:</strong> {{ record.supervising_clinician or 'N/A' }}</p>
            </div>
            <div class="col-md-6">
                <p><strong>Signature Ref:</strong> {{ record.signature_ref or 'N/A' }}</p>
                <p><strong>Authorized By:</strong> {{ record.authorized_by or 'N/A' }}</p>
            </div>
        </div>

        <div class="mt-4 d-flex justify-content-between align-items-center">
            <a href="{{ url_for('dashboard') }}" class="btn btn-secondary">Dashboard</a>
            <div>
                <button onclick="window.print()" class="btn btn-outline-primary me-2">Print Record</button>
                <a href="{{ url_for('download_pdf', traveler_id=record.traveler_id) }}" class="btn btn-dark">Download PDF</a>
            </div>
        </div>
    </div>
</body>
</html>''',

    'verify.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Certificate - EPHI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container my-5 card p-4 shadow-sm text-center" style="max-width: 550px;">
        <h3 class="fw-bold text-dark">EPHI Official Verification</h3>
        <p class="text-muted">Public Vaccination Certificate Check</p>
        <hr>

        {% if record %}
            {% if record.status == 'ACTIVE' %}
                <div class="alert alert-success p-3">
                    <h4 class="alert-heading">✓ VALID CERTIFICATE</h4>
                    <p class="mb-0">This record is authentic and registered with EPHI.</p>
                </div>
                <div class="text-start mt-3">
                    <p><strong>Traveler ID:</strong> {{ record.traveler_id }}</p>
                    <p><strong>Full Name:</strong> {{ record.full_name }}</p>
                    <p><strong>Nationality:</strong> {{ record.nationality }}</p>
                    <p><strong>Issued On:</strong> {{ record.created_at.strftime('%Y-%m-%d') if record.created_at else 'N/A' }}</p>
                </div>
            {% elif record.status == 'REVOKED' %}
                <div class="alert alert-danger p-3">
                    <h4 class="alert-heading">✗ REVOKED CERTIFICATE</h4>
                    <p class="mb-0">This certificate has been revoked and is NO LONGER VALID.</p>
                </div>
                <div class="text-start mt-3">
                    <p><strong>Traveler ID:</strong> {{ record.traveler_id }}</p>
                    <p><strong>Revoked Date:</strong> {{ record.revoked_at }}</p>
                    <p><strong>Reason:</strong> {{ record.revoked_reason }}</p>
                </div>
            {% else %}
                <div class="alert alert-warning p-3">
                    <h4 class="alert-heading">⚠ ARCHIVED RECORD</h4>
                    <p class="mb-0">This record has been archived.</p>
                </div>
            {% endif %}
        {% else %}
            <div class="alert alert-warning p-3">
                <h4 class="alert-heading">⚠ INVALID RECORD</h4>
                <p class="mb-0">No record found matching this Traveler ID.</p>
            </div>
        {% endif %}
    </div>
</body>
</html>''',

    'audit_logs.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audit Logs - EPHI Portal</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container my-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2>System Audit Logs</h2>
            <a href="{{ url_for('dashboard') }}" class="btn btn-secondary">← Back to Dashboard</a>
        </div>

        <div class="table-responsive bg-white shadow-sm rounded">
            <table class="table table-striped align-middle mb-0">
                <thead class="table-dark">
                    <tr>
                        <th>#</th>
                        <th>Admin Username</th>
                        <th>Action</th>
                        <th>Timestamp (UTC)</th>
                    </tr>
                </thead>
                <tbody>
                    {% for log in logs %}
                    <tr>
                        <td>{{ log.id }}</td>
                        <td><strong>{{ log.admin_username }}</strong></td>
                        <td>{{ log.action }}</td>
                        <td>{{ log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '' }}</td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center py-3">Log-iin tokkollee hin argamne.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>'''
}

# Loop through the dictionary and write each file
for filename, content in templates.items():
    filepath = os.path.join('templates', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created: {filepath}")

print("\\n✅ All template files and folder created successfully!")
