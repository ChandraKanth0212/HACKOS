# HACKOS — Product Requirements Document

**Product:** HACKOS — A Reliable Operating System for Hackathon Delivery  
**Track:** The Future of Hackathons  
**Version:** 1.0  
**Status:** Hackathon MVP specification  
**Target build window:** WhyCode4U Hackathon, 31 October–1 November 2026

> This document translates the organizer's HACKOS problem statement into an implementable prototype specification. Requirements explicitly listed in the problem statement are treated as core requirements. Detailed workflows and technical choices below are implementation recommendations for the MVP.

## 1. Product summary

HACKOS is a centralized web platform that helps hackathon organizers manage the participant journey from registration to final results. It brings participant and team records, check-in, announcements, schedules, project submissions, judging and reports into one operational system.

The application has three primary user roles: **Organizer**, **Participant** and **Judge**. A system administrator may use the Organizer role for the MVP.

## 2. Problem statement

Hackathon operations are frequently spread across forms, spreadsheets, chat groups and file-sharing services. This can create duplicate records, missed updates, manual work and poor visibility into event progress. Organizers need a single source of truth for teams and attendance while participants need clear access to schedules, announcements, problem statements and submission status.

HACKOS addresses this by providing a modular platform for event operations, with support for both online and offline workflows.

## 3. Product goals

1. Maintain a consistent record of participants, teams and attendance.
2. Provide organizer, participant and judge experiences with role-appropriate access.
3. Make participant check-in fast using QR codes or unique codes.
4. Publish schedules and announcements in one place.
5. Accept project submissions and record submission timestamps.
6. Support configurable judging rubrics and score capture.
7. Produce exportable reports for event operations and results.
8. Preserve an audit trail for important edits and judging scores.
9. Demonstrate a low-connectivity check-in workflow with later synchronization.

## 4. Success measures for the prototype

The prototype is successful when a judge can complete and observe this end-to-end demonstration:

- An organizer creates or configures an event.
- Participants and teams appear in the organizer dashboard.
- A participant's QR/code is checked in and attendance is recorded once.
- An organizer publishes an announcement and schedule item.
- A team submits a project; the server records the submission timestamp.
- An organizer assigns a judge to a project.
- The judge evaluates the project against configured criteria.
- The system calculates and displays a leaderboard using the configured scoring rule.
- The organizer exports a report.
- Important edits and score submissions are traceable in an audit log.

Use synthetic demonstration data. Do not represent sample counts or outcomes as real event statistics.

## 5. Users and permissions

### 5.1 Organizer

Needs to configure the event, manage participants and teams, check attendance, post announcements, track submissions, assign judges, configure rubrics, review results and export reports.

### 5.2 Participant

Needs to view their own event information, team, schedule and announcements; present a check-in code; submit project details; and view submission status.

### 5.3 Judge

Needs to see only assigned projects and submit evaluations using the active rubric. Judges must not be able to change another judge's evaluation.

### 5.4 System administrator

For the MVP, administrator privileges may be combined with Organizer access. Keep account creation and role assignment restricted.

## 6. Scope

### 6.1 P0 — Required MVP capabilities

| ID | Capability | Requirement |
|---|---|---|
| FR-01 | Authentication | Users sign in and receive access according to their role. |
| FR-02 | Participant records | Organizers can create, view and update participant records. |
| FR-03 | Team management | Organizers can create teams, add/remove members and manage team changes. |
| FR-04 | Duplicate handling | The system detects likely duplicate registrations and prevents accidental duplicate records using a defined unique identifier, such as normalized email. |
| FR-05 | Check-in | The system supports QR scanning or manual code entry and records attendance with a timestamp. |
| FR-06 | Announcements | Organizers can publish announcements visible to participants. |
| FR-07 | Schedule | Organizers can publish schedule items with date/time and description. |
| FR-08 | Submissions | Teams can submit project title, description, repository URL and demo URL. |
| FR-09 | Submission timestamp | The server records the authoritative submission creation/update timestamp. |
| FR-10 | Judging rubric | Organizers can configure judging criteria and their weights or maximum scores. |
| FR-11 | Score capture | Assigned judges can score their assigned projects and save a short evaluation note. |
| FR-12 | Results | The system calculates totals from submitted evaluations and shows an organizer-visible ranking. |
| FR-13 | Reports | Organizers can export participant, team, attendance, submission and judging data. |
| FR-14 | Role-based access | Organizer, Participant and Judge operations are authorized on the server, not merely hidden in the UI. |
| FR-15 | Audit trail | Important participant/team edits and judging score changes are recorded with actor and timestamp. |

### 6.2 P1 — Important, time-permitting

- Offline check-in queue stored in the browser and synchronized when connectivity returns.
- Duplicate check-in prevention and clear conflict handling during sync.
- Judge assignment based on category/expertise using transparent rules.
- n8n notifications for registration confirmation, submission reminders and judge assignment.
- CSV export with clear export timestamp and event identifier.

### 6.3 Out of scope for the 24-hour MVP

- Payment collection and ticket sales.
- Native mobile applications.
- Live video, chat or conferencing.
- AI-based automated judging or winner selection.
- Guaranteed WhatsApp/SMS delivery without configured providers and consent.
- A full mentor marketplace or complex mentor-slot booking.
- Production-grade multi-tenant SaaS administration.
- Fully offline support for every module.

## 7. Functional detail and acceptance criteria

### 7.1 Authentication and role access

- Users can sign in using email and password.
- Passwords are stored as secure hashes, never as plaintext.
- Each protected endpoint checks the user's role and resource ownership.
- A participant cannot view another participant's private profile or edit another team's submission.
- A judge can access only projects assigned to that judge.

**Acceptance:** Directly requesting a restricted URL or API endpoint returns an authorization error even if the user bypasses the UI.

### 7.2 Participant and team management

- Organizer can search and filter participants.
- Organizer can create teams and manage team membership.
- Membership rules such as maximum team size are configurable or clearly stated as event assumptions.
- Duplicate email or participant identifier is detected before creating another record.
- Team changes retain a history or audit entry.

**Acceptance:** A repeated registration with the same normalized email is rejected or flagged for organizer review; a team-member change is recorded in the audit log.

### 7.3 Check-in

- Each participant has a unique, non-guessable check-in token represented by a QR code or code string.
- An authorized organizer can scan the QR or enter the code manually.
- Attendance stores participant, event, timestamp and checking-in user.
- Repeated scans do not create duplicate attendance rows; the interface explains that the person is already checked in.

**Acceptance:** Scanning a valid code records one attendance record; scanning it again shows the existing check-in without duplicating it.

### 7.4 Announcements and schedule

- Organizer can create, edit and publish announcements.
- Participants can view published announcements and schedule entries.
- Draft or unpublished content is not visible to participants.

**Acceptance:** A published announcement appears in participant view; an unpublished draft does not.

### 7.5 Project submissions

- A participant can submit or update a submission for their own team before the configured deadline.
- Required fields are validated server-side.
- URLs are validated for permitted schemes (`https` preferred).
- Server-side timestamps are authoritative; client timestamps are not trusted.
- Late submission behavior is configurable: reject, accept but flag late, or allow organizer override. The MVP default should be documented in the event settings.

**Acceptance:** A valid submission is saved with a server timestamp and appears in organizer and assigned-judge views. A user from another team cannot edit it.

### 7.6 Judging and leaderboard

- Organizer configures criteria and maximum score/weight.
- Organizer assigns judges to projects/teams.
- Judge can save and submit an evaluation for assigned projects only.
- Scores are validated against each criterion's range.
- The aggregation method is documented and consistent. Recommended MVP default: normalize each criterion to its configured weight, sum criterion contributions per judge, then average submitted judge totals for each project. Clearly label incomplete evaluations.
- Changes to submitted scores create audit records.

**Acceptance:** Out-of-range scores are rejected; a judge cannot score an unassigned project; leaderboard totals match the documented formula.

### 7.7 Reporting

- Organizer can export CSV files for participants, teams, attendance, submissions and evaluations.
- Reports include event name, generated-at timestamp and relevant identifiers.
- Export endpoints are organizer-only.

**Acceptance:** Exported CSV opens as a structured table and includes the same records shown in the organizer dashboard.

### 7.8 Offline check-in — P1

- The check-in page can cache a limited roster or accept signed/issued participant tokens before connectivity loss.
- Offline scans are stored locally with a client-generated operation ID and timestamp.
- On reconnection, the server reconciles each operation idempotently.
- Conflicts such as an already-checked-in participant are reported for organizer review.
- Do not claim the feature is offline-capable until tested with the network disabled and subsequent synchronization verified.

**Acceptance:** A test check-in performed with network access disabled is queued locally and synchronized once connectivity returns, without duplicate attendance records.

## 8. n8n automation requirements

n8n is an automation layer, not the source of truth for event data. Flask validates and persists business records first; n8n handles secondary actions.

Suggested MVP workflows:

1. **Registration notification:** after a participant is saved, Flask sends an authenticated event to an n8n webhook; n8n logs or sends a confirmation through a configured channel.
2. **Submission reminder:** a Schedule Trigger queries a Flask endpoint for teams without a submission; n8n sends reminders through a configured provider or demonstrates a logged notification.
3. **Judge assignment notification:** after an assignment is saved, Flask triggers n8n to notify the assigned judge.

Workflow failures must not undo registration, check-in, submission or judging transactions. The app should log automation failure and allow retry. Do not expose n8n webhook secrets in browser code.

## 9. Non-functional requirements

- **Usability:** common organizer tasks should be discoverable without training.
- **Responsive design:** core pages should work on laptop and mobile-width screens.
- **Performance:** common list and dashboard actions should respond quickly on the demo dataset; paginate or limit large tables.
- **Reliability:** validation and database constraints protect critical records.
- **Security:** enforce authentication, authorization, CSRF protection, safe password storage and input validation.
- **Privacy:** use synthetic data for demos; collect only data needed to operate the event.
- **Traceability:** retain timestamps and audit history for consequential actions.
- **Accessibility:** semantic HTML, keyboard-accessible forms, visible focus and adequate contrast.

## 10. Assumptions and open decisions

The official brief does not prescribe a programming language, database, hosting provider, notification provider, team-size limit, exact judging weights or exact offline-sync protocol. The following are MVP recommendations, not organizer mandates:

- Backend: Python Flask.
- Database: SQLite for the local hackathon prototype.
- Frontend: HTML, CSS, JavaScript and Bootstrap or a small custom design system.
- Automation: n8n Cloud Pro via server-to-server webhooks.
- Demo data: synthetic participants, teams, judges and submissions.
- Deployment: local-first; deploy only after the complete flow works.

Resolve these decisions in event configuration or document them in the demo README.

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Too much scope for the build window | Deliver P0 flows first; treat offline sync and advanced automations as P1. |
| n8n outage or misconfiguration | Persist core transaction first; automation is best-effort and retryable. |
| Duplicate check-ins | Unique database constraint and idempotent check-in operation. |
| Score disputes | Configurable rubric, clear aggregation formula and audit log. |
| Privacy exposure | Synthetic demo data, minimal data collection and role checks. |
| Connectivity loss | Demonstrate only the offline check-in scope that has been tested. |

## 12. Demo acceptance checklist

- [ ] Organizer, Participant and Judge accounts can sign in.
- [ ] Role permissions work on both pages and API endpoints.
- [ ] Organizer can create participants and teams.
- [ ] Duplicate registration is detected.
- [ ] QR/code check-in works and repeated scans are idempotent.
- [ ] Announcement and schedule can be published.
- [ ] Team can submit a project and see its timestamp.
- [ ] Judge assignment and score entry work.
- [ ] Leaderboard uses the documented formula.
- [ ] Organizer can export reports.
- [ ] Audit records are visible to authorized organizers.
- [ ] At least one n8n workflow completes end-to-end, or its failure is safely logged.
- [ ] README setup instructions work on a clean machine.
