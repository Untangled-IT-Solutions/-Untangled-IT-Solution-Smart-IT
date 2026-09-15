# Phase 5 - Login and startup

Phase 5 is complete in the Nexus desktop. The Website, Node backend and FastAPI
source were not changed in this phase. No production credentials or accounts
were used.

## Implemented behavior

- Startup creates the login interface immediately while `/api/health` runs in a
  worker. A slow or unavailable health endpoint cannot delay the login window.
- Login runs outside Tk's main thread. The button changes to `Signing in...`,
  duplicate submissions are ignored, and controls recover with a readable error
  after invalid credentials, timeout or connection failure.
- Successful session creation returns to Tk before application navigation occurs.
- A backend `require_password_change` flag blocks entry to the main window and
  opens a mandatory password-change dialog.
- The new password must be at least eight characters, match confirmation and
  differ from the temporary password. The authenticated API performs secure
  password verification and hashing.
- Password-change requests run in a worker. Failures leave the dialog open and
  restore its controls for retry.
- Cancelling the required-password dialog revokes the temporary session in a
  worker and resets the login form.
- Password values remain in memory only for the active operation. The original
  login field and retained temporary value are cleared as the flow progresses.
- Session-expiry responses continue through the Phase 4 queue, create one prompt
  and sign out without blocking the window.

## Validation

The focused login/startup suite passed with **27 tests**. It includes:

- a real Tk login failure delayed for three seconds, with continuing event-loop
  heartbeats and restored controls;
- an application health check delayed for three seconds while construction
  completes in under half a second;
- a real hidden password-change dialog that blocks login, suppresses duplicate
  saves and completes only after its worker returns;
- a failed password change that keeps the dialog open for retry;
- tracking and clearing `require_password_change` in the backend auth service;
- the Phase 4 four-second HTTP response test, screen worker checks, destroyed
  callback protection, task input capture and session-expiry handling.

Tests use hidden local Tk windows, synthetic credentials and a localhost delay
server. They do not contact the production API.

Final regression results:

- Desktop: `python -m pytest tests -q --tb=short` — **56 passed**.
- Dedicated FastAPI: `python -m pytest -q --tb=short` — **13 passed**.
- Desktop source compilation — passed.
- Installed dependency consistency — no broken requirements.

The FastAPI suite reports dependency deprecation warnings from its test-only
MongoDB adapter and ReportLab. There were no test failures.

## Remaining rollout work

Phase 6 must verify that business-critical desktop data has no active SQLite,
in-memory or direct-Mongo fallback and keep only justified local UI state/cache.
Live deployment, real employee-role provisioning, end-to-end staff workflows and
EXE validation remain later phases. Nexus is not yet ready for staff distribution.
