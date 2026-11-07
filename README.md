# TOTAL GRACE SCHOOL — Result Checking Portal

A starter web application for Primary and Secondary result checking. Nursery classes are not included. It supports administrator sign-in, manual student/result entry, CSV result imports, parent/student lookup by admission number + PIN, term comments, and print/save-to-PDF result sheets.

## Important result setup

The portal uses Primary CA / 40 + Exam / 60 = 100, and Secondary CA / 30 + Exam / 70 = 100. Grade bands A (75–100), B (65–74), C (50–64), D (40–49), F (0–39). **Confirm or change these rules to match Total Grace School's approved grading policy before using real results.**

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run `python -m venv .venv` and activate it.
4. Run `pip install -r requirements.txt`.
5. Set environment variables before starting:
   - `SECRET_KEY`: a long random secret string.
   - `ADMIN_USERNAME`: your private administrator username.
   - `ADMIN_PASSWORD`: a strong unique password.
6. Run `python app.py` and open `http://127.0.0.1:5000`.

For a quick local test only, defaults are `admin` / `ChangeMe123!`. Change them before deployment and do not use the defaults for a public site.

## Deploying online

This app needs a Python host that supports persistent storage (for the SQLite database). Create a web service from this folder, install `requirements.txt`, and use the start command `gunicorn app:app`. Configure the environment variables above. Attach a persistent disk and set `DATABASE_PATH` to a file on that disk (for example `/var/data/total_grace.db`). Enable HTTPS. Do not deploy without a persistent disk: an ephemeral filesystem can lose student records during redeploys/restarts.

The owner must create and control the hosting account and domain. This source package does not itself publish a live website or register a domain.

## CSV import

Sign in as administrator, download the sample CSV, fill it in, save as CSV UTF-8, and upload. Required columns:

`admission_no,full_name,section,class_name,pin,session,term,subject,ca,exam,teacher_remark`

Use exactly `Primary` or `Secondary` for section, and `First Term`, `Second Term`, or `Third Term` for term. For Primary, CA must be 0–40 and exam 0–60. For Secondary, CA must be 0–30 and exam 0–70. One row represents one subject result. A student's PIN is stored as a password hash, not plain text.

## Before using real student data

- Replace default credentials and set a strong `SECRET_KEY`.
- Deploy only over HTTPS, restrict administrator access, and use individual staff accounts in a production upgrade.
- Make encrypted backups and test restoring them.
- Establish who may access, correct, export, and delete student records; follow applicable Nigerian privacy and child-data requirements.
- Do not put real student names, admission numbers, PINs, or scores in public demo/testing environments.
- Review grading bands, remarks, and report-card layout with the school before issuing results.

This is a functional starter, not a security-audited enterprise school information system. A production deployment should add stronger rate limiting, password/PIN reset workflows, audit logs, staff roles, backup automation, and secure account recovery.
