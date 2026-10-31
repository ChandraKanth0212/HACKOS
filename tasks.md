# HACKOS — Implementation Tasks and Delivery Plan

**Priority:** P0 = required working MVP; P1 = important if time permits; P2 = future scope.  
**Status convention:** `[ ]` Not started · `[~]` In progress · `[x]` Tested complete

## 1. Build strategy

Deliver one complete vertical slice at a time. First create the app shell and database, then implement the Organizer → Participant → Judge lifecycle. Keep n8n secondary to the core app. The hackathon schedule in the organizer's revised timeline has a progress checkpoint at 5:00 PM on 31 October and final submission from 8:00–9:00 AM on 1 November 2026.

## 2. P0 — Foundation

### Project setup
- [x] Create Flask project and application factory.
- [ ] Create blueprints/modules for auth, participants, teams, attendance, communications, submissions, judging and reports.
- [x] Add `requirements.txt`, `.env.example`, `.gitignore` and local setup instructions.
- [x] Configure app secret and database connection from environment variables.
- [x] Add health-check route.
- [x] Initialize database schema and seed clearly labelled synthetic data.

### Authentication and authorization
- [x] Create user model and password hashing.
- [x] Implement login/logout.
- [x] Implement Organizer, Participant and Judge role checks.
- [ ] Add resource ownership checks for participant/team/submission routes.
- [x] Test unauthorized route and API access.

## 3. P0 — Participant and team management

- [ ] Build organizer participant list with search/filter.
- [ ] Build participant create/edit form.
- [ ] Normalize email and reject/flag duplicates.
- [ ] Build team list and team detail.
- [ ] Add/remove team members.
- [ ] Validate membership and configured team-size rule.
- [ ] Record team membership changes in audit log.

**Checkpoint acceptance:** Organizer can create multiple synthetic participants and teams, detect a duplicate registration and change team membership with a history entry.

## 4. P0 — Check-in

- [ ] Generate a unique, non-guessable check-in token for each participant.
- [ ] Render QR code for token.
- [ ] Build check-in page with camera scan if feasible.
- [ ] Add manual code entry fallback.
- [ ] Implement authenticated check-in endpoint.
- [ ] Add unique constraint/idempotency to prevent duplicate attendance.
- [ ] Display checked-in/already-checked-in/invalid-code states.

**Checkpoint acceptance:** A participant can be checked in from a valid token, and rescanning does not create a second attendance row.

## 5. P0 — Announcements and schedule

- [ ] Build organizer announcement create/edit/publish flow.
- [ ] Display published announcements to participants.
- [ ] Build schedule item management.
- [ ] Display event schedule with timezone.
- [ ] Hide drafts from participant role.

## 6. P0 — Project submissions

- [ ] Build participant submission form.
- [ ] Enforce team ownership.
- [ ] Validate project fields and repository/demo URLs.
- [ ] Save authoritative server timestamp.
- [ ] Implement deadline and late-submission rule.
- [ ] Display submission status to participant and organizer.
- [ ] Test that one team cannot alter another team's submission.

## 7. P0 — Judging and results

- [ ] Build rubric criterion configuration for organizer.
- [ ] Validate that configured maximum scores/weights are sensible.
- [ ] Build judge account and assignment management.
- [ ] Show only assigned projects to each judge.
- [ ] Build evaluation form with per-criterion score limits.
- [ ] Save evaluation and audit event.
- [ ] Implement documented aggregation formula.
- [ ] Build organizer leaderboard with completion status.
- [ ] Test score boundaries, judge restrictions and score calculation.

## 8. P0 — Reports and audit

- [ ] Add audit log for participant/team edits, attendance corrections, submission changes, judge assignments and score changes.
- [ ] Build participant CSV export.
- [ ] Build team CSV export.
- [ ] Build attendance CSV export.
- [ ] Build submission CSV export.
- [ ] Build judging/results CSV export.
- [ ] Restrict exports to Organizer role.

## 9. P1 — n8n automation

### Integration foundation
- [ ] Create n8n webhook for registration confirmation.
- [ ] Add server-side n8n URL/secret configuration.
- [ ] Add `automation_outbox` table or equivalent retry log.
- [ ] Persist business transaction before dispatching the automation event.
- [ ] Add timeout and bounded retry behavior.
- [ ] Test that n8n failure does not undo participant registration.

### Workflows
- [ ] Registration confirmation workflow.
- [ ] Submission reminder workflow using Schedule Trigger and a Flask endpoint for pending teams.
- [ ] Judge assignment notification workflow.
- [ ] Use stable event IDs to avoid duplicate notifications.
- [ ] Record workflow result or execution reference where feasible.

## 10. P1 — Offline check-in

- [ ] Cache minimal check-in roster/token information while online.
- [ ] Queue offline check-in actions with unique operation IDs.
- [ ] Clearly label queued records as not yet synchronized.
- [ ] Sync queued records when connection returns.
- [ ] Handle already-checked-in and invalid-token conflicts.
- [ ] Test with browser network disabled, then re-enabled.

## 11. P1 — UI and demo polish

- [ ] Apply consistent navigation and visual tokens from `design.md`.
- [ ] Add responsive layouts for core screens.
- [ ] Add empty/loading/error/success states.
- [ ] Add clear sample-data labels.
- [ ] Add accessible labels and keyboard focus states.
- [ ] Check camera permission and manual fallback on demo machine.

## 12. Final integration and submission

- [ ] Run full end-to-end test from registration through leaderboard.
- [ ] Test each role using separate browser sessions.
- [ ] Verify database constraints and authorization.
- [ ] Verify n8n workflow or show a clear recorded fallback if the provider is unavailable.
- [ ] Push source code to GitHub.
- [ ] Verify README setup instructions on a clean environment.
- [ ] Create architecture/workflow diagram.
- [ ] Prepare 8–10 slide presentation.
- [ ] Record 2–5 minute demo video.
- [ ] Document limitations, assumptions, synthetic data and privacy safeguards.
- [ ] Submit before the organizer's deadline.

## 13. Suggested timebox from the official event schedule

| Event time | Target outcome |
|---|---|
| 10:30 AM–1:00 PM, 31 Oct | Scope, app setup, initial frontend/backend foundation |
| 2:00–5:00 PM | Participant/team records and a working checkpoint demo |
| 5:30–8:00 PM | Check-in, submissions and first judging flow |
| 9:00–11:00 PM | Judging completion and n8n integration |
| 12:00–6:00 AM, 1 Nov | Integration, testing, reports and polish |
| 6:00–8:00 AM | Final verification, README, presentation and video |
| 8:00–9:00 AM | Final project submission and wrap-up |

This is a proposed allocation, not an organizer-mandated feature schedule. Protect time for integration and submission packaging.

## 14. Must-pass demo script

- [ ] Sign in as Organizer.
- [ ] Show seeded participant/team dashboard.
- [ ] Register a new participant; show duplicate detection.
- [ ] Open participant check-in pass and scan/enter the code.
- [ ] Repeat check-in and show idempotent result.
- [ ] Publish an announcement and view it as Participant.
- [ ] Submit a project and show server timestamp.
- [ ] Assign a Judge and sign in as that Judge.
- [ ] Submit rubric scores and show validation.
- [ ] Return as Organizer and show leaderboard and CSV export.
- [ ] Show audit log and one n8n execution.
