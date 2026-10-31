# HACKOS

**A Reliable Operating System for Hackathon Delivery**

HACKOS is a hackathon operations platform prototype for the WhyCode4U Hackathon 2026 problem statement. It brings registration, participant/team management, check-in, announcements, schedules, submissions, judging and reports into one application.

> Current status: Milestones 0–2 and 4–12 are complete: Flask foundation, database/seed, authentication, RBAC, event, participant, team, attendance, communications, submissions, judging, results, and organizer reporting workflows. Automation and final UI polish remain scheduled for later milestones.

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

- `/` — public cinematic landing page with a synthetic operations preview
- `/demo` — public, client-only synthetic walkthrough of the hackathon lifecycle
- `/register/organizer` — public CSRF-protected organizer account creation
- `/login` — CSRF-protected email/password sign-in
- `POST /logout` — CSRF-protected sign-out
- `/organizer/dashboard` — organizer-only live metrics
- `/participant/dashboard` — participant-only event status
- `/judge/dashboard` — judge-only assignment metrics

Dashboard access is server-authorized by the account role. Cross-role requests return
HTTP 403 and unauthenticated requests redirect to `/login`.

### Milestone 4 event management routes

- `/organizer/events` — organizer-only list of authorized events
- `/organizer/events/new` — CSRF-protected event creation; a new organizer is bound
  to their first event as its owner and active event
- `/organizer/events/<event_id>` — event details
- `/organizer/events/<event_id>/edit` — CSRF-protected event editing

Event dates are entered in the configured IANA timezone and stored in UTC. Server-side
validation enforces date ordering, positive capacity/team sizes, and the maximum/minimum
team-size relationship. Create and update actions write non-sensitive `AuditLog` records.

### Milestone 5 participant routes

- `/register/<event_slug>` — public participant registration for an eligible active event
- `/organizer/participants` — organizer-only participant list with search and status filtering
- `/organizer/participants/new` — organizer-only participant creation
- `/organizer/participants/<participant_id>` — organizer-only participant details
- `/organizer/participants/<participant_id>/edit` — organizer-only participant editing
- `/participant/profile` — authenticated participant's own profile only

Registration normalizes email addresses, enforces event-scoped duplicate and capacity
checks, generates a unique participant code, creates a participant account with a
Werkzeug password hash, and records an automation outbox entry for later notification.
Registration eligibility is controlled by event status and registration start/end times.

### Milestone 6 team management routes

- `/organizer/teams` — organizer-only team list for the current event
- `/organizer/teams/new` — organizer-only team creation
- `/organizer/teams/<team_id>` — team details and membership history
- `/organizer/teams/<team_id>/edit` — organizer-only team editing
- `POST /organizer/teams/<team_id>/members/add` — add an eligible participant
- `POST /organizer/teams/<team_id>/members/<participant_id>/remove` — close an active membership
- `POST /organizer/teams/<team_id>/members/<participant_id>/transfer` — transfer a participant
- `/participant/team` — authenticated participant's current team and members

Membership changes are transactional and preserve history using `joined_at` and
`left_at`. Active membership uniqueness, event isolation, team status, and configured
minimum/maximum team sizes are enforced server-side. Team and membership mutations
write non-sensitive `AuditLog` records; all mutation forms require CSRF protection.

### Milestone 7 attendance and check-in routes

- `/organizer/attendance` — organizer-only attendance dashboard with search and live metrics
- `POST /organizer/attendance/check-in` — CSRF-protected manual participant-code check-in
- `POST /organizer/attendance/check-in/qr` — CSRF-protected QR credential check-in
- `/participant/check-in-pass` — authenticated participant QR pass and manual fallback credential
- `/participant/attendance` — authenticated participant attendance status

Check-in credentials are derived from a cryptographically random per-participant nonce,
stored as a hash plus revocation metadata, and never contain participant IDs. QR
credentials are validated against the current event and rejected when unknown or revoked.
Attendance uses the existing `(event_id, participant_id)` uniqueness constraint and
`operation_id` idempotency key. Timestamps and operators are recorded server-side, and
successful check-ins create non-sensitive audit records. Camera access is optional;
manual participant-code entry remains available as a fallback. Offline queuing is not
implemented in this milestone.

### Milestone 8 announcements and schedule routes

Organizer routes:

- `/organizer/announcements` — list all announcements for the organizer's event
- `/organizer/announcements/new` — create a draft or published announcement
- `/organizer/announcements/<announcement_id>/edit` — edit or publish/unpublish an announcement
- `POST /organizer/announcements/<announcement_id>/delete` — delete an announcement
- `/organizer/schedule` — list event schedule items in event-local time
- `/organizer/schedule/new` — create a schedule item
- `/organizer/schedule/<item_id>/edit` — edit a schedule item
- `POST /organizer/schedule/<item_id>/delete` — delete a schedule item

Participant routes:

- `/participant/announcements` — published announcements only
- `/participant/schedule` — published schedule items only

Announcement and schedule mutations are CSRF-protected and scoped to the authenticated
organizer's event. Schedule form times are entered in the configured event timezone and
stored in UTC. Organizer actions create non-sensitive audit records. Participant views
use event-local display times and never expose draft or unpublished content.

### Milestone 9 project submission routes

Participant routes:

- `/participant/submission` — create or edit the authenticated participant's active team's submission

Organizer routes:

- `/organizer/submissions` — list event submissions with team/project search and status filtering
- `/organizer/submissions/<submission_id>` — view a submission scoped to the organizer's event
- `/organizer/submissions/<submission_id>/edit` — correct submission content without changing its original submission time

Submission creation requires active membership in an active team. The database's
one-submission-per-event/team constraint and a transaction-safe conflict handler
prevent repeated requests from creating duplicates. Project title and description
are required; optional repository and demo URLs accept only HTTP(S) URLs. Submission
timestamps are generated in UTC. The event `settings_json` key
`late_submission_policy` supports `reject`, `accept_and_flag` (the default), and
`allow`; late accepted submissions are marked `late`. Participant and organizer
actions create non-sensitive audit records, and all mutation forms use CSRF
protection. Separate problem-statement, solution, and technologies columns are not
present in the approved schema, so the existing description field is used for the
project narrative.

### Milestone 10 judge assignment and evaluation routes

Organizer routes:

- `/organizer/judging` — event-scoped judge, submission, and assignment management
- `POST /organizer/judging/assign` — assign or reactivate a judge assignment
- `POST /organizer/judging/<assignment_id>/revoke` — revoke an assignment while preserving its history
- `/organizer/judging/evaluations/<evaluation_id>` — inspect an evaluation for the organizer's event

Judge routes:

- `/judge/assignments` — list only active assignments for the authenticated judge
- `/judge/assignments/<submission_id>/evaluate` — save a draft or submit a rubric evaluation

Assignments require matching event ownership for the organizer, judge, and submission.
Duplicate assignments are rejected by both service validation and the database
constraint. Revoked assignments can be reactivated without creating a duplicate row.
Judges can only evaluate active assignments, and submitted evaluations are read-only.
Each active criterion is validated against its configured maximum score; submission
requires every active criterion. The configured weighted formula normalizes each
criterion score by its maximum, applies its configured weight, normalizes by total
weight, and expresses the result as a 0–100 judge total. Missing scores are never
treated as zero. Evaluation and assignment actions are audited without private
credentials or session data.

### Milestone 11 leaderboard and result publication

Organizer routes:

- `/organizer/results` — view the event-scoped leaderboard and evaluation completion status
- `POST /organizer/results` — publish or unpublish results with CSRF protection

Participant route:

- `/participant/results` — view final results only after organizer publication

Results reuse the judging formula
`weighted_criterion_sum_then_average_submitted_judges`: only complete submitted
evaluations count, each judge total is normalized to 0–100, and a submission's
score is the average of its submitted judge totals. Draft, missing, or incomplete
evaluations are excluded and leave a submission pending/unranked. Ordering is
deterministic and ties use competition ranking (`1, 1, 3`).

Publication metadata is stored in the existing extensible `Event.settings_json`
(`results_published` and `results_published_at`), so no migration is required.
Publishing and unpublishing are audited. Participant output contains only rank,
team, project title, and final score; judge identities, comments, and drafts are
never exposed. All result data is restricted to the authenticated user's event.

### Milestone 12 organizer reports and CSV exports

Organizer-only reporting routes:

- `/organizer/reports` — live participant, team, attendance, submission, judging, and publication metrics
- `/organizer/reports/participants.csv`
- `/organizer/reports/teams.csv`
- `/organizer/reports/attendance.csv`
- `/organizer/reports/submissions.csv`
- `/organizer/reports/judging.csv`
- `/organizer/reports/leaderboard.csv`

Exports use stable headers, UTF-8 BOM CSV output, event-local timestamps, and
formula-injection neutralization for spreadsheet values beginning with `=`, `+`,
`-`, or `@`. Empty reports still include headers. Export actions are audited
without storing report contents. Password hashes, session or QR credentials,
secrets, and private judge comments are excluded. All queries are restricted to
the organizer's event and no migration was required.

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

The latest application audit verified startup, clean migrations, repeatable synthetic
seeding, SQLite foreign-key enforcement, authentication edge cases, authorization,
database integrity, reporting privacy, and the complete automated suite. The current
regression result is 85 passed with 32 existing WTForms deprecation warnings. Full
camera-permission testing and exhaustive multi-session browser verification remain
manual follow-up items.

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
