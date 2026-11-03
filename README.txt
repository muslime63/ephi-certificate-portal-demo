EPHI PERSONAL RECORD PORTAL (DEMONSTRATION)

Files:
- app.py
- requirements.txt
- templates/login.html
- templates/admin.html
- templates/issue.html
- templates/verify.html

Local run:
1. Install Python 3.10+.
2. Run: pip install -r requirements.txt
3. Set environment variables:
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=choose-a-strong-password
   SECRET_KEY=use-a-long-random-secret
4. Run: python app.py
5. Open http://127.0.0.1:5000/login

Render:
- Build command: pip install -r requirements.txt
- Start command: gunicorn app:app
- Set ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY in Environment.
- For persistent SQLite storage, attach a Render persistent disk and set:
  DATABASE_PATH=/var/data/certificates.db
  The mount path must match the disk mount path configured in Render.
- Without persistent storage, SQLite data may be lost on redeploy/restart.

This application creates demonstration personal records only. It is not an official
international vaccination certificate system. Enter only authentic information from
the original vaccination source documents. Never fabricate vaccine details.
