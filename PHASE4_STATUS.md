# Phase 4 - Tkinter responsiveness

Implemented the async fixes in the existing Nexus desktop. The public Website,
Node backend and FastAPI source were not changed. No deployment, account changes
or production API writes were performed.

## Findings and fixes

The existing dispatcher queued results but also tried `winfo_toplevel` and
`after` from worker threads. It now only enqueues from workers. Pollers belong to
each root's lifetime, and delivery checks that the destination view still exists.
Queue draining is bounded so a burst of completions cannot starve normal events.

Several views fetched data during construction, refresh and form submission.
Their remote calls now explicitly yield to the existing worker dispatcher and
resume on Tk. Widget reads occur before a call is handed to a worker; widget
creation, rendering, error handling and success callbacks remain on Tk.

The continuation helper preserves dependent operation order, including a form's
save followed by refresh. It adds loading state, blocks duplicate mutations and
coalesces repeated refresh/filter requests. Navigating away destroys the old
view, so its later result cannot repaint the new view. In-flight HTTP operations
are not forcibly killed; existing transport timeouts still bound them.

## Screen audit

| Area | Result |
|---|---|
| Startup/Login | Health check runs in a worker; login shows Signing in, prevents repeated submit, and invokes the successful navigation callback on Tk. |
| Dashboard | Retained the working background queue; exercised it in the Tk tests. |
| People | Filter options, directory loads, profiles and current-task lookups use worker boundaries. |
| Attendance | Employee loading and supporting history/totals now use workers. Rendering uses the retrieved snapshot instead of fetching again. Existing status/action queues and local timer remain. |
| Tasks/Work navigation | Task list, manager/employee actions, assignment options and create modal use workers. Action inputs are read on Tk before submission. Work navigation already uses TaskView. |
| Calendar | Event loads, form options, saves and deletes use workers; existing Calendar view is now reachable through the factory. |
| Approvals | Lists, form options, submission and stage decisions use workers; existing view is now reachable. |
| Office Requests | Lists, option loading and submission use workers; existing view is now reachable. |
| Notifications | List/read/read-all work uses workers. Shell badge polling is also asynchronous and prevents overlap. |
| Projects | Existing project list load uses a worker; view is reachable. |
| Reports | Type loading, previews and export requests use workers; view is reachable. |
| User Management | Employee/account loading, statistics, creation, resets, status changes and deletion use workers. |
| Settings | Existing account-related operations use worker boundaries; local theme changes stay on Tk. |
| Quote/Order views | Existing background readers preserved; remaining active API mutation/notification calls moved to workers. Their Website-owned mutation endpoints remain a separate integration boundary from Phase 3. |
| Updater/Logout | Worker update-check/download callbacks now use queue delivery, including progress. Logout's remote request is asynchronous. |

The unused legacy `work_view.py` still contains old collection-oriented code;
normal Work navigation uses TaskView. Quote/Order legacy collection branches are
inactive because their constructors explicitly set `_mongodb = None`. No direct
MongoDB access was enabled or newly introduced. Broader legacy-data cleanup stays
with Phase 6.

## Errors and sessions

The API client now rejects I/O attempted on the active Tk thread as a regression
guard. This supplements moving actual calls; it is not a replacement for those
changes. Existing network timeouts were not increased.

HTTP 401 responses enqueue session expiry on Tk. The callback checks the session
token, prevents duplicate prompts and signs the user out asynchronously. Old
responses cannot cache data into a newer session. Other API failures appear in a
shared error banner, including failures swallowed by older service wrappers.

## Validation

`App/.venv/Scripts/python.exe -m pytest tests -q --tb=short`: **51 passed**.
`python -m compileall -q App/app`: passed.

The new tests use real, hidden Tk windows. A local HTTP server deliberately waits
**4 seconds** before responding. The test confirms submission returns in under
0.5 seconds, more than 80 Tk heartbeat callbacks run during the wait, and heartbeat
gaps stay below 0.5 seconds. Duplicate mutation submission performs one operation.

Additional tests exercise initial loading through the actual controllers and
services for People, Tasks, Calendar, Approvals, Office Requests, Notifications,
Projects, Reports, User Management and Settings. API calls assert that they are
off Tk; violations remain test failures even if a service catches the exception.
Attendance supporting data, the existing Dashboard queue, login success callbacks,
task action input capture, destroyed-owner delivery, timeout recovery and session
expiry are covered. Tests use synthetic records and localhost only.

The bundled Python 3.12 Tcl/Tk could not initialize on this machine. Tests were
therefore run with system Python 3.14 and the declared desktop dependencies.
Repeated Tcl initialization also showed intermittent runtime file-read errors;
the GUI suite uses a shared hidden root with per-test widget/timer cleanup.

These checks verify event-loop responsiveness and callback safety, not production
workflow correctness or a packaged EXE. No live MongoDB, production login or staff
installation was used. Document/report download wiring and first-login password
change still need their planned desktop integration.

## Files

- `App/app/utils/async_tasks.py` and new `ui_tasks.py`.
- `App/app/application.py`, controllers `app_controller.py`, `login_controller.py`,
  `navigation_controller.py`, and `services/backend_api_client.py`.
- Views: `login_view.py`, `main_window.py`, `people_view.py`, `attendance_view.py`,
  `task_view.py`, `calendar_view.py`, `approval_view.py`, `office_request_view.py`,
  `notification_view.py`, `project_view.py`, `report_view.py`,
  `user_management_view.py`, `settings_view.py`, `quote_management_view.py`,
  `order_management_view.py`, and `update_dialog.py`.
- New `App/tests/test_ui_async.py`, `App/README.md`, and `App/.gitignore`.

## Next

Phase 5: finish focused login/startup validation and integration. Its asynchronous
foundation overlaps Phase 4 and is now implemented. Nexus is not yet declared
ready for staff distribution; the remaining phases and deployed-system checks
still apply.
