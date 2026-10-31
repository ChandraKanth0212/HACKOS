# HACKOS — Security and Privacy Specification

**Version:** 1.0  
**Classification:** Hackathon prototype security baseline

## 1. Security objectives

- Protect participant, team, submission and judging information.
- Ensure users can perform only actions permitted by their role and resource ownership.
- Preserve integrity of check-in, submissions and judging results.
- Protect passwords, sessions, n8n credentials and application secrets.
- Minimize personal data collected and exposed.

This specification is a practical prototype baseline, not a claim of formal security certification or a substitute for a production security assessment.

## 2. Data classification

| Data | Classification | Handling |
|---|---|---|
| Public event schedule/announcements | Public after publication | May be displayed without authentication if event policy allows |
| Participant name/team affiliation | Internal event data | Show only to roles with a business need |
| Email/phone | Personal data | Restrict to organizer and participant owner as appropriate |
| Project submission links | Event-confidential until published | Limit to team, assigned judges and organizers |
| Judge scores/comments | Restricted | Judge sees own evaluation; organizer sees results according to policy |
| Password hashes/session secrets/webhook secrets | Highly restricted | Never expose in API responses, logs, exports or frontend code |

## 3. Authentication

- Require authentication for all non-public operations.
- Store password hashes using a recognized password hashing function such as Argon2id or Werkzeug's secure password hashing utilities.
- Never store or log plaintext passwords.
- Use generic login failure messages to avoid account enumeration.
- Rate-limit repeated login attempts where possible.
- Provide logout and invalidate the session.
- Do not hardcode production/admin credentials in source code.

## 4. Session and browser security

For cookie-based sessions:

- Set `HttpOnly`.
- Set `Secure` in HTTPS deployment.
- Use an appropriate `SameSite` value, typically `Lax` for the application.
- Rotate session identifiers after authentication/privilege changes where supported.
- Set a reasonable session lifetime.
- Protect state-changing requests against CSRF.
- Do not store session secrets in local storage.

## 5. Authorization

Implement server-side role-based and resource-level checks.

| Action | Organizer | Participant | Judge |
|---|---:|---:|---:|
| View organizer dashboard | Yes | No | No |
| Manage participants/teams | Yes | No | No |
| View own participant/team record | Yes | Yes, own scope | No, unless assigned context requires it |
| Check in participants | Yes | No | No |
| View published announcements/schedule | Yes | Yes | Yes |
| Publish announcements/schedule | Yes | No | No |
| Create/update team submission | Yes, override with audit | Own team only | No |
| Assign judges | Yes | No | No |
| View assigned submissions | Yes | Own team submission | Assigned only |
| Submit judging evaluation | No, except controlled admin correction | No | Assigned only |
| View full results/export reports | Yes | Only if explicitly published | Only as authorized |

Always check ownership and assignment in the backend. Hiding a button or route in the frontend is not authorization.

## 6. Input validation and output encoding

- Validate every field server-side.
- Normalize email addresses consistently before duplicate checks.
- Enforce length limits for names, titles, descriptions and comments.
- Validate URL schemes and reject unsafe schemes such as `javascript:`.
- Use parameterized SQL or ORM query parameters.
- Escape user-generated content before rendering HTML.
- Avoid rendering untrusted HTML from announcements or project descriptions.
- Validate score values against active rubric bounds on the server.
- Treat QR/check-in tokens as untrusted input and validate them against stored records.

## 7. CSRF, XSS and injection controls

- Enable CSRF protection for cookie-authenticated state-changing forms/API requests.
- Use template auto-escaping and avoid unsafe HTML rendering.
- Use parameterized database queries.
- Do not interpolate untrusted values into SQL, shell commands or filesystem paths.
- Set a restrictive Content Security Policy where practical; allow only required scripts, styles and camera functionality.

## 8. Check-in token security

- Generate random, non-sequential participant tokens; do not encode email or phone in the QR payload.
- Store only the token or a suitable token hash if the implementation supports lookup safely.
- Allow check-in only to authorized staff.
- Make check-in idempotent; a repeated scan must not create a second attendance row.
- Rate-limit invalid token attempts where practical.
- If offline check-in is implemented, limit cached data and reconcile operations on the server. Clearly distinguish locally queued from server-confirmed check-ins.

## 9. Submission and judging integrity

- Use server-generated timestamps for submission and evaluation records.
- Enforce team ownership for participant submission changes.
- Enforce judge assignment before allowing score submission.
- Validate all scores on the server.
- Record who changed an assignment, rubric, evaluation or score and when.
- Make submitted evaluations read-only unless an organizer performs an explicit, audited reopen/correction action.
- Display scoring formula and incomplete-evaluation state transparently.

## 10. n8n and integration secrets

- Store n8n webhook URLs, shared secrets and provider credentials in environment variables or a secret manager.
- Never place webhook credentials in HTML, CSS, browser JavaScript, public GitHub files or screenshots.
- Call n8n from the Flask server only.
- Authenticate internal callbacks using a shared secret or stronger mechanism supported by the deployment.
- Send the minimum data required by each workflow.
- Avoid including passwords, full profiles or sensitive fields in webhook payloads.
- Use event IDs to deduplicate retries.
- Treat n8n execution logs as potentially sensitive and configure retention/access accordingly.
- n8n failure must not roll back primary application transactions.

## 11. File upload policy

The MVP should prefer repository and demo URLs over file uploads. If uploads are implemented:

- Allow only required file types and enforce size limits.
- Verify file signatures where applicable; do not trust filename extensions alone.
- Generate server-side filenames.
- Store files outside the public web root or in a controlled object store.
- Prevent path traversal and executable content delivery.
- Scan files if an appropriate scanning service is available.
- Restrict download access by role and resource ownership.

## 12. Privacy and data minimization

- Use synthetic names, emails and scores for demo data.
- Collect only fields required to operate the hackathon.
- Make phone number and institution optional unless the organizer establishes a need.
- Do not collect government ID, medical information or other sensitive personal data for this use case.
- Restrict participant contact details to organizers and the participant concerned.
- Do not publish private judging comments or personal contact data in the leaderboard.
- Define a retention/deletion policy before using real participant data.

## 13. Logging and audit

- Log authentication events and important business actions without logging secrets.
- Record actor, action, affected entity and timestamp in audit logs.
- Sanitize errors before storing/displaying them.
- Avoid logging full request bodies where they may contain personal data or credentials.
- Limit audit-log access to authorized organizers.

## 14. Configuration and repository hygiene

- Keep `.env`, database files, exported participant lists and credentials out of version control.
- Commit `.env.example` with placeholder values only.
- Use separate development and production secrets.
- Use HTTPS for public deployment.
- Disable debug mode in production.
- Back up the database before schema changes and final demonstration.

## 15. Minimum security test checklist

- [ ] Participant cannot access organizer pages or API endpoints.
- [ ] Judge cannot access a project not assigned to them.
- [ ] Participant cannot edit another team's submission by changing an ID.
- [ ] Invalid and repeated check-in tokens are handled safely.
- [ ] Repeated check-in does not duplicate attendance.
- [ ] Score above maximum or below zero is rejected.
- [ ] CSRF protection is enabled for state-changing cookie-authenticated requests.
- [ ] User content is escaped in pages.
- [ ] SQL uses parameterized queries/ORM.
- [ ] `.env` and DB files are excluded from Git.
- [ ] n8n secrets do not appear in browser code or logs.
- [ ] n8n failure does not lose a core business transaction.
- [ ] Public exports do not reveal private contact details or judge comments.
