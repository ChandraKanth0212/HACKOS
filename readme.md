# HACKOS

**A Reliable Operating System for Hackathon Delivery**

HACKOS is a hackathon operations platform prototype for the WhyCode4U Hackathon 2026 problem statement. It brings registration, participant/team management, check-in, announcements, schedules, submissions, judging and reports into one application.

> Current status: Milestones 0–2 are complete: Flask foundation, database/seed, authentication, RBAC and the application shell. Participant/team workflows and event operations remain scheduled for later milestones.

## 1. Problem being addressed

Hackathon organizers often manage registrations, teams, attendance, announcements, submissions and judging across disconnected forms, spreadsheets and chat tools. HACKOS aims to provide a single source of truth and a clear participant journey from registration to results.

## 2. MVP feature scope

### Core features
- Role-based access: Organizer, Participant and Judge.
- Participant registration and duplicate detection.
- Team and member management.
- QR/code-based check-in.
- Announcements and event schedule.
- Timestamped project submission portal.
- Configurable judging rubric and score capture.
- Leaderboard and exportable CSV reports.
- Audit trail for important changes and judging scores.

### Planned automation using n8n
- Registration confirmation.
- Submission deadline reminders.
- Judge assignment notifications.

n8n handles automation; Flask remains responsible for data validation, authorization and persistence. Core application operations must continue to work if n8n is unavailable.

## 3. Proposed technology stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript, Bootstrap or custom CSS |
| Backend | Python, Flask |
| Database | SQLite for the hackathon MVP |
| ORM/data access | Flask-SQLAlchemy or parameterized SQL |
| QR generation | Python `qrcode` package |
| QR scanning | Browser camera library with manual-code fallback |
| Automation | n8n Cloud Pro |
| Version control | Git and GitHub |

The organizer's problem statement does not prescribe a stack; these are project implementation choices.

## 4. Repository structure

```text
hackos/
├── app/
│   ├── __init__.py
│   ├── auth/
│   ├── participants/
│   ├── teams/
│   ├── attendance/
│   ├── communications/
│   ├── submissions/
│   ├── judging/
│   ├── reports/
│   ├── templates/
│   └── static/
│       ├── css/
│       ├── js/
│       └── img/
├── migrations/              # If using Flask-Migrate
├── instance/                # Local database; never commit
├── tests/
├── n8n/
│   ├── registration-confirmation.json
│   ├── submission-reminders.json
│   └── judge-assignment-notification.json
├── docs/
├── .env.example
├── .gitignore
├── config.py
├── run.py
├── requirements.txt
└── README.md
```

The documentation files in this pack can be placed in the repository root or under `docs/`.

## 5. Prerequisites

- Python 3.11 or a compatible version supported by the selected dependencies.
- pip and `venv`.
- Git.
- A browser.
- An n8n Cloud account for the automation workflows (optional for core app development).

## 6. Local setup

The commands below assume that the Flask application entry point will be `run.py`. Adjust only if the implementation uses a different entry point.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -m flask --app run db upgrade
python run.py
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open the local URL printed by Flask, commonly `http://127.0.0.1:5000` in development.

### Initialize the synthetic demo database

Set a local-only seed password in the PowerShell session, then run the repeatable seed
command. The password is read from the environment and stored only as a secure hash.

```powershell
$env:HACKOS_SEED_PASSWORD = Read-Host "Local synthetic seed password"
python -m flask --app run seed
```

Run `python -m flask --app run seed` again to verify that existing synthetic records
are reused rather than duplicated. Do not publish the seed password or use it for
real accounts.

### Milestone 2 routes

- `/` — public placeholder
- `/login` — CSRF-protected email/password sign-in
- `POST /logout` — CSRF-protected sign-out
- `/organizer/dashboard` — organizer-only live metrics
- `/participant/dashboard` — participant-only event status
- `/judge/dashboard` — judge-only assignment metrics

Dashboard access is server-authorized by the account role. Cross-role requests return
HTTP 403 and unauthenticated requests redirect to `/login`.

## 7. Environment variables

Create `.env` from `.env.example`. Example variable names:

```dotenv
FLASK_ENV=development
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///hackos.db
N8N_WEBHOOK_BASE_URL=
N8N_WEBHOOK_SECRET=
APP_TIMEZONE=Asia/Kolkata
```

Do not commit `.env`, database files, production webhook URLs or secrets. Keep secrets in the deployment environment.

## 8. n8n setup

1. Create a workflow in the n8n Cloud workspace.
2. Add a Webhook trigger for the required application event.
3. Validate the incoming payload and use only the fields required for the task.
4. Add the notification or reporting steps.
5. Configure a stable event ID/idempotency strategy.
6. Activate/publish the workflow and use its production webhook URL.
7. Store the URL and shared secret in Flask environment variables.
8. Trigger it from the Flask server, not directly from browser JavaScript.
9. Test failure behavior: temporarily make the endpoint unavailable and confirm the main application record still saves.

Suggested initial workflows are described in `architecture.md` and `tasks.md`.

## 9. Demo accounts and data

Create clearly labelled synthetic demo accounts for each role. Do not use real participant personal information. Store initial passwords as hashes and change/remove demo credentials before any public deployment.

Suggested demonstration dataset:
- 1 organizer.
- 3 judges.
- 6 teams.
- 3–5 members per team.
- 4–6 sample announcements/schedule items.
- Several submitted and not-yet-submitted projects.

All demo statistics must be labelled as sample data.

## 10. Testing

Run automated tests, when configured:

```bash
pytest
```

At minimum, manually verify:
- Each role's permissions.
- Duplicate registration behavior.
- QR and manual check-in.
- Repeat check-in does not create duplicate attendance.
- Announcement publication visibility.
- Submission ownership and server timestamp.
- Judge assignment restrictions.
- Score range validation and leaderboard calculation.
- CSV export authorization and contents.
- n8n failure does not break a core transaction.
- Offline check-in sync, if implemented.

## 11. Security and privacy

See `security.md`. Use synthetic data for the hackathon demo. Apply server-side role checks, secure password hashing, CSRF protection for cookie-authenticated forms, input validation and secret management. Do not expose n8n credentials in frontend code.

## 12. Project documentation

- `PRD.md` — product requirements and acceptance criteria.
- `design.md` — visual system, screens and UX behavior.
- `architecture.md` — components, data flows and n8n integration.
- `database.md` — entities, relationships and constraints.
- `security.md` — security and privacy controls.
- `agents.md` — instructions for AI coding agents and contributors.
- `tasks.md` — prioritized implementation plan and demo checklist.

## 13. Known limitations

The first prototype is not a production-certified event platform. SQLite is intended for a single-instance demo. Email/WhatsApp/SMS delivery depends on provider configuration. Offline support is limited to check-in if implemented and tested. No AI judging or automatic clinical/safety decisions are part of HACKOS.

## 14. Submission checklist

- [ ] Working prototype/deployment link.
- [ ] GitHub repository with setup instructions.
- [ ] 2–5 minute demo video.
- [ ] 8–10 slide presentation PDF/PPT.
- [ ] Architecture/workflow diagram.
- [ ] Technology stack and limitations.
- [ ] Privacy and safety considerations.
