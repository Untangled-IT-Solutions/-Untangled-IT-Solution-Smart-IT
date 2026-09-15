# Phase 3 - Nexus API completeness

The dedicated FastAPI source has been extended in place. The Website and its Node/TypeScript backend were not modified during Phase 3. No production deployment, employee/account provisioning or live MongoDB writes were performed.

## Implemented

| Area | Result |
|---|---|
| Auth | Login, current user, logout, configurable expiry, hashed bearer tokens, login throttling, password hashing/upgrades, reset-session revocation and enforced password change endpoint. |
| People/accounts | Employee lists/details, sanitized responses, existing-record account linking, roles, status changes, reset and soft disable with backend hierarchy checks. |
| Attendance | Self clock in/out and breaks with server timestamps, invalid-transition rejection, South Africa dates, history, working-now and restricted team views. |
| Tasks | Business task dump, Operations queue and assignment/reassignment, personal work visibility, actual active timer accumulation, manual time, updates, submit/review/return/complete/cancel/escalation, audit history and workflow notifications. |
| Calendar | Stored events, personal/team visibility, CRUD, upcoming dates and bounded recurrence expansion. |
| Approvals | Stored requests; Manager -> Business -> optional Director stage transitions; authenticated reviewer identity, no self approval and reasons for rejection. |
| Office requests | Stored requests with quantity validation, management review and optional Director stage. |
| Notifications | Recipient-scoped list/count/read/read-all, authenticated creation and deterministic workflow event keys. |
| Leave | Dated requests, overlap detection, own/authorized review visibility, supporting document references and approval/rejection using shared approval state. |
| Documents | Actual bounded BSON file bytes, extension/signature checks, macro-free Office container checks, authenticated authorized downloads, metadata and expiry classification. |
| Reports/projects | Existing project readers only; actual database report preview and private CSV/PDF/Excel exports for current desktop report types. |
| Dashboards | Database-derived scoped summary and role endpoints, actual task hours and attendance/leave counts; no shared cross-user summary cache. |
| Commerce readers | Existing quote/order readers now require authentication and appropriate visibility. Public commerce functionality stays with Node. |

Required settings and the API route inventory are in `untangled-nexus-api-main/README.md`, `.env.example` and `API_ROUTES.md`. The inventory contains 86 paths, including aliases and health routes.

## Validation

Python 3.12: `python -m pytest -q --tb=short` — **13 passed**.
`python -m pip check` — **No broken requirements found**.
FastAPI import and OpenAPI generation succeeded.

Tests exercise real HTTP handlers with an isolated test-only MongoDB adapter. Production still requires Motor/MongoDB and has no mock-data fallback. Coverage includes all six canonical role logins; invalid/expired sessions; protected routes and private fields; reset/forced password change; task assignment, timing, correction and completion; attendance transitions; actual file retrieval and denied cross-employee access; staged leave approvals; calendar CRUD; office requests; reports in three formats; project visibility; dashboard scoping and Director queue selection; stale revision rejection.

Dependency deprecation warnings are from mongomock and ReportLab. They did not fail tests. No real MongoDB instance or production credentials were available for a live database integration run. This suite does not prove real MongoDB race behavior, deployment startup or existing production-record compatibility.

## Contract and rollout boundaries

- Core Nexus service endpoints now exist. Unsupported Website-owned commerce mutation/review calls still present in desktop code are explicitly listed in `API_ROUTES.md`; they were not copied into FastAPI.
- The legacy generic Leave approval form lacks dates and document IDs. It now receives a clear validation error; later desktop work must use the structured leave endpoints.
- Private document/report download and forced password-change interfaces need desktop integration. Files are never exposed at public URLs.
- Sick-leave supporting documents are configurable with `SICK_LEAVE_DOCUMENT_REQUIRED`. The default does not invent an organization-wide documentation policy. Uploads are accepted and securely linked when provided.
- Startup creates additive Nexus indexes; it does not rewrite existing employees or remove legacy accounts. Existing mixed identifier formats are supported, but live records still need validation before rollout.
- Individual task/review/timer mutations use revision checks. Related records and notifications are not a cross-collection transaction; notification delivery recovery, retry idempotency for create requests and simultaneous overlapping leave submissions need live integration/concurrency review before release.
- File validation checks type signatures/container structure, size and access. It is not malware scanning. Stored files are served as authenticated downloads with no-store and nosniff headers.
- Expiry classification exists; scheduled idempotent expiry notifications remain Phase 12.
- Named management account activation remains Phase 7. No duplicate employee records or production passwords were created.
- UI responsiveness, all screen wiring, EXE/install/update checks and the final security/rollout audit remain later phases. Nexus is **not yet declared ready for staff distribution**.

## Changed files

Within `untangled-nexus-api-main`: `app/domain.py`, `app/security.py`, `app/config.py`, `app/db.py`, `app/main.py`; routers `auth.py`, `employees.py`, `users.py`, `attendance.py`, `tasks.py`, `calendar.py`, `approvals.py`, `office_requests.py`, `notifications.py`, `leave.py`, `documents.py`, `projects.py`, `reports.py`, `dashboard.py`, `quotes.py`, `health.py`; `requirements.txt`, `requirements-dev.txt`, `pytest.ini`, `tests/conftest.py`, `tests/test_workflows.py`, `.env.example`, `README.md`, and `API_ROUTES.md`. This report is at the repository root.

## Next phase

Phase 4: audit every Tkinter network call, improve the existing async queue/dispatcher, move blocking operations off the main thread, protect navigation/destruction callbacks and test with intentionally delayed API responses of 3-5 seconds. Continue using the existing desktop architecture.
