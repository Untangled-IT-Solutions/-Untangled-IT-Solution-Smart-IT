# Phase 13 — Role-Specific Dashboards

Status: **Complete**

## Authenticated role boundary

- `GET /api/dashboard/summary` derives its dashboard shape and data scope from the authenticated session.
- Query-string or payload role claims cannot select a more privileged dashboard.
- Dedicated Director, Business Lead, and Operations routes enforce their allowed roles on the server.
- Staff and Intern responses contain personal work, attendance, leave, and notification information only.

## Dashboard surfaces

- **Director:** a compact executive business summary with business health, people working and on leave, important and overdue work, compliance attention, and Director-stage approvals.
- **Business Lead:** a department-scoped business overview with the task dump, team work and assignees, elapsed and estimated task duration, clock-in/out activity, and recent business activity.
- **Operations Manager:** an operational command centre with incoming and assignment queues, employee workload, task states and duration, attendance, leave and approvals, HR status, office requests, calendar items, notifications, QA/review, and operational issues.
- **Staff and Intern:** a personal dashboard with only their own tasks, work hours, attendance status, leave state, and unread-notification count.

The desktop controller selects the matching authenticated endpoint and the desktop view renders distinct Director, Business Lead, Operations, and personal layouts. Management information is no longer displayed through a shared one-size dashboard.

## Navigation

- Sidebar modules now come from a role-to-module allowlist.
- Staff and Intern accounts do not see People, Projects, Reports, Quote Management, Order Management, or User Management.
- Operations accounts retain the modules needed to run daily operations.

## Validation

- FastAPI suite: **29 passed**
- Desktop suite: **70 passed**
- Compilation checks passed for the API dashboard router and all changed desktop modules.

Coverage verifies authenticated dashboard shaping, forged-role resistance, protected role endpoints, management surface contents, controller endpoint selection, and personal versus Operations navigation.
