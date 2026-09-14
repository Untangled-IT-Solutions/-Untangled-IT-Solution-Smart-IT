# Untangled Nexus – UI Freeze Fix

## Why the UI froze

CustomTkinter runs its event loop on **one main thread**.  
Any synchronous `requests` / API call made on that thread blocks painting and input until the network returns.  
Cold starts on Render free tier (30–60 s) made this especially visible.

## What was fixed

1. **Login** – now runs authentication in a background thread via `run_in_background`. The login window stays responsive and shows “Signing in…”.
2. **Dashboard / Attendance / Orders / Quotes** – already used threading; left intact.
3. **Tasks, People, Notifications, Approvals, Calendar, Projects** – `refresh()` methods now use `run_in_background` so list loads never freeze the UI.
4. **Startup health probe** – no longer blocks application launch.
5. **UI dispatcher** – started on the login window as well as the main window (required for Python 3.13+/3.14 cross-thread safety).

All UI updates are marshalled back to the main thread via the existing `app/utils/async_tasks.py` helper.

## How to run

```powershell
# From this folder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Optional `.env`:

```
API_BASE_URL=https://untangled-nexus-api.onrender.com
ENVIRONMENT=production
```

## Assets / branding

This package contains the full fixed **source**.  
If icons / logos / notification.wav are missing, copy the `app/assets` folder from your original `app.zip` into `app/assets` here. The app will still run without them (fallback icons).

## Files changed

- `app/views/login_view.py`
- `app/views/task_view.py`
- `app/views/people_view.py`
- `app/views/notification_view.py`
- `app/views/approval_view.py`
- `app/views/calendar_view.py`
- `app/views/project_view.py`
- `app/application.py`

The rest of the architecture (controllers, services, BackendAPIClient) is unchanged.

## Navigation loader (sidebar)

Every sidebar click now:

1. Shows a workspace-wide loading overlay immediately (“Loading Dashboard…”, etc.).
2. Builds and displays the target view.
3. Triggers `refresh()` on the view (async API load).
4. Hides the loader when data arrives (or on error), via `run_in_background` / view-specific hide.

Fallback: loader auto-hides after 12 seconds if a view never signals ready (e.g. Settings).

## Architecture refactor (God Views)

See `app/ARCHITECTURE.md`.

Delivered in this package:

1. **`app/ui/base_workspace_view.py`** – shared load/error/destroy lifecycle
2. **`app/presenters/`** – presenter base (no Tk)
3. **`app/views/quotes/`** – feature package (constants, formatting, view)
4. **`quote_management_view.py`** – thin compatibility shim
5. **`people_view.py`** – rewritten as `BaseWorkspaceView` template (~220 lines)
6. **`quote_service.py`** – API facade for quotes (no UI)

Remaining large files (`order_management`, `user_management`, `task_view`, …)
should follow the same checklist in ARCHITECTURE.md.
