# Nexus API routes - Phase 3

Generated from the FastAPI application. Business routes require bearer authentication; root, health and readiness are public.

| Method | Path |
|---|---|
| GET | `/` |
| GET | `/api/admin/attendance` |
| GET | `/api/admin/attendance/history` |
| GET | `/api/admin/attendance/team` |
| GET | `/api/admin/attendance/today` |
| GET | `/api/admin/employees` |
| GET | `/api/admin/employees/{employee_id}` |
| GET | `/api/admin/roles` |
| GET | `/api/admin/users` |
| POST | `/api/admin/users` |
| DELETE | `/api/admin/users/{user_id}` |
| GET | `/api/admin/users/{user_id}` |
| PATCH | `/api/admin/users/{user_id}` |
| PUT | `/api/admin/users/{user_id}` |
| POST | `/api/admin/users/{user_id}/reset-password` |
| GET | `/api/approvals` |
| POST | `/api/approvals` |
| POST | `/api/approvals/{approval_id}/approve` |
| POST | `/api/approvals/{approval_id}/reject` |
| POST | `/api/attendance/break-end` |
| POST | `/api/attendance/break-start` |
| POST | `/api/attendance/break/end` |
| POST | `/api/attendance/break/start` |
| POST | `/api/attendance/clock-in` |
| POST | `/api/attendance/clock-out` |
| GET | `/api/attendance/history` |
| GET | `/api/attendance/records` |
| GET | `/api/attendance/status` |
| GET | `/api/attendance/team` |
| GET | `/api/attendance/today` |
| GET | `/api/attendance/working-now` |
| POST | `/api/auth/change-password` |
| POST | `/api/auth/login` |
| POST | `/api/auth/logout` |
| GET | `/api/auth/me` |
| GET | `/api/calendar/events` |
| POST | `/api/calendar/events` |
| GET | `/api/calendar/events/upcoming` |
| DELETE | `/api/calendar/events/{event_id}` |
| PATCH | `/api/calendar/events/{event_id}` |
| GET | `/api/dashboard/business-lead` |
| GET | `/api/dashboard/director` |
| GET | `/api/dashboard/operations` |
| GET | `/api/dashboard/summary` |
| GET | `/api/documents` |
| POST | `/api/documents` |
| POST | `/api/documents/upload` |
| GET | `/api/documents/{document_id}` |
| PATCH | `/api/documents/{document_id}` |
| GET | `/api/documents/{document_id}/download` |
| GET | `/api/employees` |
| GET | `/api/employees/{employee_id}` |
| GET | `/api/health` |
| GET | `/api/invoices` |
| GET | `/api/invoices/{invoice_id}` |
| POST | `/api/invoices/{invoice_id}/issue` |
| GET | `/api/leave` |
| POST | `/api/leave` |
| GET | `/api/leave/{leave_id}` |
| POST | `/api/leave/{leave_id}/approve` |
| POST | `/api/leave/{leave_id}/reject` |
| GET | `/api/notifications` |
| POST | `/api/notifications` |
| POST | `/api/notifications/mark-all-read` |
| POST | `/api/notifications/read-all` |
| GET | `/api/notifications/unread-count` |
| POST | `/api/notifications/{notification_id}/read` |
| GET | `/api/office-requests` |
| POST | `/api/office-requests` |
| GET | `/api/office-requests/items` |
| PATCH | `/api/office-requests/{request_id}` |
| GET | `/api/orders` |
| GET | `/api/orders/track` |
| GET | `/api/projects` |
| GET | `/api/projects/{project_id}` |
| GET | `/api/quotes` |
| GET | `/api/quotes/track` |
| POST | `/api/quotes/{reference}/approve` |
| PUT | `/api/quotes/{reference}/quotation` |
| GET | `/api/ready` |
| POST | `/api/reports/export` |
| GET | `/api/reports/preview` |
| GET | `/api/reports/types` |
| GET | `/api/tasks` |
| POST | `/api/tasks` |
| GET | `/api/tasks/decision-queue` |
| GET | `/api/tasks/workload` |
| GET | `/api/tasks/{task_id}` |
| PATCH | `/api/tasks/{task_id}` |
| PUT | `/api/tasks/{task_id}` |
| POST | `/api/tasks/{task_id}/approve-review` |
| POST | `/api/tasks/{task_id}/assign` |
| POST | `/api/tasks/{task_id}/cancel` |
| POST | `/api/tasks/{task_id}/complete` |
| POST | `/api/tasks/{task_id}/escalate` |
| POST | `/api/tasks/{task_id}/log-time` |
| POST | `/api/tasks/{task_id}/pause` |
| POST | `/api/tasks/{task_id}/reassign` |
| POST | `/api/tasks/{task_id}/resume` |
| POST | `/api/tasks/{task_id}/return` |
| POST | `/api/tasks/{task_id}/review` |
| POST | `/api/tasks/{task_id}/start` |
| POST | `/api/tasks/{task_id}/submit-review` |
| GET | `/api/v1/nexus/dashboard` |
| GET | `/health` |
| GET | `/ready` |

## Desktop contract comparison

All current core Nexus service routes are implemented: auth, people, attendance, tasks, calendar, approvals, office requests, notifications, admin users, reports and project readers. Existing primary notification read/read-all routes succeed; speculative fallback aliases are not needed. Task state PATCH requests go through the same authorization/state transitions as action routes. Invalid legacy fallback writes are rejected instead of bypassing permissions.

New leave and private document endpoints need desktop controls in later phases. Generic approval creation rejects Leave because that legacy form has no structured dates or document IDs. Use `/api/leave`. Password-change enforcement also requires a desktop password-change screen. Report exports return an authenticated relative download URL; desktop file downloading remains to be wired.

## Website-owned calls still present in the desktop

Public quote/order creation remains Website-owned. Authenticated Nexus operations now include quote assignment and status updates, Director reviews, quotation pricing, customer approval, linked invoice-draft creation and controlled invoice issue. Payment allocation, credit notes, statements and customer portal authentication are later quote-to-cash phases and must not be simulated through generic status changes.

## Data storage

Existing collection names are retained for employees, users, api_sessions, attendance, work_assignments, approvals, notifications, quotes, orders and projects. Invoices use a separate `invoices` collection with unique source-quote and invoice-number indexes; yearly invoice sequences use `counters`. Calendar events, office requests, documents and login attempts use their corresponding MongoDB collections. Leave is stored as a typed approval with dates and document IDs, avoiding competing approval state. Files contain BSON binary content, not just names/sizes.
