# HACKOS — Design Specification

**Version:** 1.0  
**Product direction:** Clear, operational, trustworthy event-management SaaS

## 1. Design principles

1. **Operational clarity first:** Organizers should immediately understand event status and what needs attention.
2. **Role-specific simplicity:** Participants and judges should see only the tools relevant to their tasks.
3. **Consistent status language:** Use the same labels for registration, attendance, submission and judging states.
4. **Trust through traceability:** Show timestamps, ownership and status wherever they affect event operations.
5. **Responsive and accessible:** Support laptop-first organizer workflows and mobile-friendly participant/check-in screens.
6. **No decorative complexity:** Prioritize readable data tables, clear forms and focused dashboards over unnecessary animation.

## 2. Visual direction

Use a modern, calm SaaS interface. Recommended palette:

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#2563EB` | Primary actions, active navigation |
| `--color-primary-dark` | `#1D4ED8` | Hover/active state |
| `--color-accent` | `#0F766E` | Positive secondary emphasis |
| `--color-success` | `#15803D` | Completed/success states |
| `--color-warning` | `#B45309` | Attention/late/pending states |
| `--color-danger` | `#B91C1C` | Errors/destructive actions |
| `--color-bg` | `#F8FAFC` | Application background |
| `--color-surface` | `#FFFFFF` | Cards, panels and tables |
| `--color-text` | `#0F172A` | Primary text |
| `--color-muted` | `#64748B` | Secondary text |
| `--color-border` | `#E2E8F0` | Dividers and borders |

### Typography

- Primary font: Inter, system-ui, sans-serif.
- Page title: 24–30 px, semibold.
- Section title: 16–20 px, semibold.
- Body: 14–16 px.
- Table/helper text: 12–14 px.
- Use tabular numerals for metrics and scores.

### Spacing and shape

- Base spacing unit: 4 px.
- Common card padding: 16–20 px.
- Card radius: 12 px.
- Input/button radius: 8 px.
- Use subtle borders; avoid heavy shadows.
- Keep primary action placement consistent, usually top-right of page content or at the end of a form.

## 3. Application shell

### Desktop layout

- Left navigation sidebar: 232–256 px.
- Top bar: event selector/name, current role, notifications and account menu.
- Main content: responsive content area with a maximum comfortable reading width.
- Sidebar collapses to an icon rail or drawer on smaller screens.

### Suggested navigation

**Organizer**
- Overview
- Participants
- Teams
- Check-in
- Announcements
- Schedule
- Submissions
- Judges & assignments
- Judging results
- Reports
- Settings

**Participant**
- My overview
- My team
- Schedule
- Announcements
- Check-in pass
- Project submission

**Judge**
- Assigned projects
- Evaluation history
- Profile

## 4. Key screens

### 4.1 Login

Elements:
- HACKOS logo/wordmark and event name.
- Email and password fields.
- Show/hide password control.
- Clear validation and authentication errors.
- No public role selector; role comes from the authenticated account.

### 4.2 Organizer overview

Top row of metric cards:
- Registered participants.
- Active teams.
- Checked-in participants.
- Submissions received.

Below metrics:
- Attendance progress chart or progress bar.
- Submission status summary.
- Upcoming schedule items.
- Latest announcements.
- Recent activity/audit feed.

All numbers must be calculated from stored records or explicitly marked as seeded demo data.

### 4.3 Participants

- Search by name, email or participant ID.
- Filters: team, registration status, attendance status.
- Table columns: participant, email, ID, team, status, check-in time, actions.
- Add/edit participant form in a modal or dedicated page.
- Duplicate warning must identify the likely matching record without leaking private fields to unauthorized users.

### 4.4 Teams

- Team list with team ID, team name, members, problem statement/category and submission status.
- Team detail page showing membership history and project submission.
- Add/remove member actions with confirmation and audit entry.
- Clearly show team-size rule configured for the event.

### 4.5 Check-in

- Large scan area with clear camera permission instructions.
- Manual participant code input as a fallback.
- High-visibility result state: Checked in, Already checked in, Invalid code, Offline queued, Sync conflict.
- Show participant name and team only to authorized check-in staff.
- Prevent double submissions through disabled/working states and server-side idempotency.

### 4.6 Announcements and schedule

- Announcement list with Draft/Published status and publish time.
- Editor fields: title, message, audience (MVP may use all participants), publication status.
- Schedule list/calendar with start, end, location/meeting link and description.
- Use a consistent event timezone and display it clearly.

### 4.7 Submission portal

Participant form:
- Project title.
- Short description.
- Problem statement/category.
- Repository URL.
- Demo/deployment URL.
- Optional attachment only if file handling is safely implemented.
- Submission deadline and current status.

Show a confirmation with server-recorded timestamp. Make late/locked state explicit.

### 4.8 Judge workspace

- Assigned project queue.
- Project summary and submitted links.
- Rubric criteria with maximum score/weight shown next to each input.
- Comment box for concise feedback.
- Save draft and Submit evaluation actions.
- Confirmation before final submission.
- Submitted evaluation becomes read-only unless organizer reopens it through an audited action.

### 4.9 Results and reports

- Leaderboard with project/team, total score, evaluation completion and rank.
- Clearly disclose the scoring formula and treatment of missing evaluations.
- Organizer-only exports for participants, teams, attendance, submissions and results.
- Avoid exposing judge comments or private participant details in public views.

## 5. Component states

Every data-driven screen should define:

- Loading state.
- Empty state with a useful next action.
- Success state.
- Validation error state.
- Permission-denied state.
- Network/server error state.
- Pending/retry state for asynchronous automation.

Use inline errors near fields, not only toast notifications. Toasts are appropriate for non-blocking confirmation.

## 6. Status labels

Recommended shared statuses:

| Domain | Statuses |
|---|---|
| Registration | Pending, Confirmed, Cancelled, Flagged duplicate |
| Attendance | Not checked in, Checked in, Offline queued, Sync conflict |
| Submission | Not submitted, Submitted, Updated, Late, Locked |
| Judging | Unassigned, Assigned, In progress, Submitted, Reopened |
| Announcement | Draft, Published, Archived |

Do not use color alone to communicate status; always show text or an icon with an accessible label.

## 7. Responsive behavior

- At widths below 768 px, sidebar becomes a drawer.
- Tables can scroll horizontally or switch to stacked cards; key identifiers must remain visible.
- QR scan controls should use the available camera width and retain manual-code fallback.
- Forms use one column on mobile and can use two columns on wide screens.
- Primary actions remain reachable without horizontal scrolling.

## 8. Accessibility checklist

- Semantic page headings and landmarks.
- Labels associated with every form control.
- Keyboard access to navigation, dialogs and actions.
- Visible focus indicator.
- Adequate contrast for text and controls.
- Error messages announced or associated with invalid fields.
- QR scanner has a manual code alternative.
- Charts include text summaries or tabular equivalents.

## 9. Design acceptance checklist

- [ ] The active role and event are visible.
- [ ] Navigation items match the user's role.
- [ ] Tables have search/filter and useful empty states.
- [ ] All forms show required fields and validation.
- [ ] Critical actions require confirmation where appropriate.
- [ ] Statuses are consistent across screens.
- [ ] Mobile-width layout remains usable.
- [ ] Demo metrics are labelled as synthetic when seeded.
