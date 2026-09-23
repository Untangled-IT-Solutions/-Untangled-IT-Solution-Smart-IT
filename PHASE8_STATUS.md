# Phase 8 status — backend authorization

## Result

Phase 8 is complete. FastAPI is authoritative for identity and action-level
permissions; desktop visibility is only a usability aid.

## Enforced role boundaries

| Role | Server-authorized scope |
| --- | --- |
| Business Lead | Create unassigned task dumps; view own, created, and same-department work; review Business-stage approvals; use non-HR business reports. |
| Operations Manager | Assign/reassign work; operate review queues; manage operational requests; view people and attendance; administer lower-privilege accounts. |
| Director | Executive visibility; Director-stage approvals; people oversight; escalated task review; administration below Director rank. |
| Branch Manager | People/account oversight plus management visibility under the existing canonical model. |
| Staff / Intern | Own assigned work, attendance, leave, documents, requests, events, projects, and notifications. |

`Super Admin` remains a server-level compatibility role and cannot be granted
through the normal user-management API.

## Changes

- Added explicit `PEOPLE_OVERSIGHT`, `TASK_OVERSIGHT`, and `BUSINESS_WORK`
  policy groups to the shared backend domain module.
- Business Leads no longer inherit global HR/attendance access simply because
  they are management users.
- Employee lists are personal for Staff/Intern, department-scoped for Business
  Leads, and organization-wide only for people-oversight roles.
- Attendance team/history access is limited to Director, Branch Manager,
  Operations Manager, and Super Admin. Attendance actions always use the
  authenticated employee.
- Business Lead task views and workload summaries are restricted to their own,
  created, assigned, or same-department tasks.
- The Operations decision queue and all task/quote/order assignment operations
  require Operations Manager or Super Admin.
- Business Leads can create task dumps but cannot choose another department or
  pre-assign an employee.
- Approval lists expose only personal and Business-stage records to Business
  Leads. Office requests are personal unless the user has people oversight.
- Business Leads may see same-department calendar/project records but cannot
  modify another employee's calendar event.
- Attendance reports are removed from Business Lead report options and rejected
  server-side. Task and approval report rows use the same scoped queries as the
  live screens.
- Manual role-wide/employee notifications require people-oversight permission.
- The desktop task controller now hides assignment choices from Business Leads
  and rejects assignment, decision-queue, escalation, and cancellation calls
  unless the authenticated role is Operations Manager.

## Untrusted client fields

Approval and request ownership is derived from the authenticated employee.
`requested_by`, `reviewer_name`, `reviewer_role`, usernames, and display names
sent by the client do not determine authorization or audit identity. Approval
history records the authenticated Operations Manager, Business Lead, and
Director at their respective stages.

## Privilege escalation

- Staff cannot call user administration.
- Operations Managers cannot promote a user to Director.
- Directors cannot grant Director to a peer or create `Super Admin` through the
  standard API.
- Business Leads cannot administer accounts, assign work, access attendance
  teams, send management notifications, or forge approval authority.

## Verification

- FastAPI authorization matrix: 4 passed
- Full FastAPI suite: 21 passed
- Desktop role/auth/data-boundary tests: 10 passed
- Python compilation: passed
- Dependency checks: passed

The authorization matrix exercises allowed and denied requests through the real
ASGI application with isolated MongoDB test storage. It includes task visibility,
department isolation, attendance and employee privacy, forged reviewer fields,
multi-stage approvals, account promotion attempts, reports, notifications, and
quote assignment.

## Opening the application

The source application can be launched now for visual inspection if a reachable
FastAPI instance and a valid account are configured. The stable review point for
the complete staff experience is after the remaining workflow, attendance,
leave, dashboard, Website-protection, and packaging phases. The user should be
notified again when that review build is ready.

## Next phase

Phase 9 implements and verifies the complete task dump, Operations inbox,
assignment, work timer, submission, completion, and correction workflow.
