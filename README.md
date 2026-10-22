# Cloud-Based Student Attendance System

A beginner-friendly Flask web app for teachers to manage students, mark daily attendance, review attendance summaries, and download CSV reports.

## Features
- Teacher registration/login (passwords are hashed)
- Add and delete students; roll numbers must be unique
- Mark Present, Absent, or Late by date
- Dashboard summary and per-student attendance totals
- Download attendance records as CSV
- Health check endpoint at `/health`
- Render deployment configuration included

## Run on Windows / VS Code
Open PowerShell in this folder:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open http://127.0.0.1:5000, register a teacher account, sign in, add students, then mark attendance.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the current terminal and activate again.

## Deploy on Render
Push the project to GitHub, then in Render choose **New + → Blueprint** and select the repository containing `render.yaml`. The file configures Gunicorn and a persistent disk path for SQLite.

**Important:** Check Render's current plan and persistent-disk availability. If no persistent disk is attached, local SQLite data can be lost after redeploys/restarts. For production or multiple app instances, use a managed PostgreSQL database. Set a unique `SECRET_KEY` in deployment settings.

## Security note
This is a student-project starter. Before production, add CSRF protection, rate limiting, account recovery, backups, and stronger access/role management. Never commit `.env`, database files, passwords, or real student data to GitHub.
