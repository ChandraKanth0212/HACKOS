# HACKOS — Instructions for AI Coding Agents and Contributors

These instructions apply to AI coding assistants and human contributors working in this repository.

## 1. Mission

Build HACKOS as a reliable hackathon operations platform that satisfies the HACKOS problem statement. Prioritize complete, testable end-to-end workflows over feature count or decorative UI.

## 2. Source of truth

Read these documents before making substantial changes:

1. `PRD.md` — requirements and acceptance criteria.
2. `architecture.md` — system boundaries and integration patterns.
3. `database.md` — schema and data integrity rules.
4. `security.md` — required security controls.
5. `design.md` — interface and accessibility requirements.
6. `tasks.md` — implementation priorities.

If documents conflict, follow this order: `PRD.md` for product behavior, `security.md` for security controls, `database.md` for data integrity, `architecture.md` for system boundaries, then `design.md` for presentation. Record material decisions in the relevant document rather than silently changing scope.

## 3. Required working principles

- Inspect the existing repository before creating or replacing files.
- Make small, coherent changes and test them before moving to the next task.
- Do not overwrite working code or user-authored content without inspecting it.
- Do not invent completed features, test results or deployment status.
- Use synthetic data for demos and tests.
- Keep the application usable without n8n; automation is a secondary integration.
- Keep the database as the source of truth for participants, teams, attendance, submissions and scores.
- Prefer simple, maintainable implementations appropriate to a short hackathon build.

## 4. Technical conventions

### Backend
- Use Flask blueprints or similarly clear module boundaries.
- Keep routes thin; put business rules in service functions.
- Validate all request data server-side.
- Use parameterized queries or a well-configured ORM.
- Use database transactions for multi-record operations.
- Use explicit timezone-aware timestamps; store timestamps consistently in UTC and render in the event timezone where practical.
- Return consistent JSON error structures for API endpoints.

### Frontend
- Use semantic HTML and accessible labels.
- Keep API calls in small reusable JavaScript modules.
- Do not trust hidden UI controls as access control; the backend must authorize requests.
- Provide loading, empty, success and error states.
- Provide manual participant-code entry as a fallback to camera scanning.

### Database
- Enforce uniqueness and foreign keys in the database, not only in UI code.
- Use migrations or a controlled schema initialization process.
- Do not store secrets or plaintext passwords in database seed files.
- Never delete or rewrite audit history as a normal update operation.

### n8n
- Trigger workflows from server-side Flask code.
- Do not put webhook URLs with secrets in frontend bundles.
- Persist the primary application record before triggering an automation.
- Use a stable event ID and idempotent handling to prevent duplicate notifications.
- Log failures and provide bounded retries; never make core registration/check-in/submission dependent on n8n being available.

## 5. Security rules — must follow

- Hash passwords using a suitable password hashing function (for example, Werkzeug's password hashing utilities or Argon2/bcrypt).
- Use secure, HTTP-only, SameSite cookies for session authentication; use Secure cookies in HTTPS deployment.
- Protect cookie-authenticated state-changing requests against CSRF.
- Enforce role and resource-level authorization on every protected endpoint.
- Validate and normalize emails, URLs, IDs, scores and text lengths.
- Escape rendered user content to prevent XSS.
- Use safe file handling if uploads are added; avoid uploads in the MVP unless necessary.
- Keep `.env`, database files and credentials out of Git.
- Avoid logging passwords, session tokens, webhook secrets or unnecessary personal data.
- Use synthetic sample data only in public demonstrations.

## 6. Definition of done

A task is complete only when:

1. The implementation meets its acceptance criteria in `PRD.md`.
2. Relevant automated tests pass or manual test steps are recorded.
3. Authorization and input validation are implemented server-side.
4. The UI includes useful loading/empty/error/success states.
5. No secrets or real personal data are committed.
6. Documentation is updated if behavior, endpoints, schema or setup changed.
7. The feature works in the intended end-to-end user journey.

## 7. Coding-agent workflow

For each task:

1. Read the relevant requirements and inspect related files.
2. State the smallest intended change.
3. Implement the change without broad refactoring.
4. Add/adjust tests for success, invalid input and unauthorized access.
5. Run tests or provide reproducible manual verification steps.
6. Update `tasks.md` only after evidence that the task is complete.
7. Report files changed, commands run, test results and known limitations.

## 8. Time management

Use this order under hackathon time pressure:

- P0: login/roles, participant/team records, check-in, announcements/schedule, submissions, judging, leaderboard/report.
- P1: n8n workflows, audit improvements, offline check-in sync, UI polish.
- Defer: nonessential AI, complex analytics, external messaging integrations and enterprise features.

Do not sacrifice data integrity or authorization to add a visual feature.

## 9. Prohibited shortcuts

- Do not hardcode admin credentials into the application.
- Do not trust participant IDs supplied by the browser without checking ownership.
- Do not allow judges to score projects outside their assignments.
- Do not let a browser send arbitrary n8n webhook calls containing secrets.
- Do not use client-provided timestamps as authoritative submission or attendance times.
- Do not claim offline capability without testing with the network disabled and verifying synchronization.
- Do not claim AI is used unless a real, working AI component is present and explained.
