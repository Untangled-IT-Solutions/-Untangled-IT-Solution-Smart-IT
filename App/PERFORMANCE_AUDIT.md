# Untangled Nexus — Performance & UX Fix Report

## Scope

This revision improves the existing Python/CustomTkinter application without replacing the business system or removing working modules.

## Changes implemented

### 1. Non-blocking quote and order loading

Quote and order data, plus employee assignment lists, are now loaded in background workers. Tkinter widgets are only updated on the UI thread.

Affected files:

- `app/views/quote_management_view.py`
- `app/views/order_management_view.py`
- `app/utils/async_tasks.py`

### 2. HTTP connection reuse

`BackendAPIClient` now uses a pooled `requests.Session` rather than opening a fresh HTTP connection for every request. This reduces repeated TCP/TLS setup time when employees move between API-backed screens.

Affected file:

- `app/services/backend_api_client.py`

### 3. Dashboard request caching

Dashboard summaries are cached briefly (5 seconds) to prevent repeated identical requests during rapid navigation/refresh activity.

Affected file:

- `app/services/backend_dashboard_service.py`

### 4. Stop unnecessary view reconstruction

Navigating to the screen that is already open no longer destroys and rebuilds the entire CustomTkinter view. Views that expose `refresh()` are refreshed in place.

This is particularly important for dashboard refreshes because reconstructing a large widget tree is expensive.

Affected files:

- `app/controllers/app_controller.py`
- `app/views/dashboard_view.py`
- `app/views/quote_management_view.py`
- `app/views/order_management_view.py`

### 5. SQLite runtime tuning

SQLite connections now use a reasonable busy timeout, WAL journal mode and `synchronous=NORMAL` to improve concurrent read/write responsiveness while retaining SQLite reliability.

Affected file:

- `app/database/database.py`

### 6. MongoDB startup diagnostics reduced

The legacy MongoDB service previously performed extra database listing and collection count operations during connection startup. Those diagnostics have been removed from the startup path. Connection pooling and shorter connection selection timeouts were also added.

Affected file:

- `app/services/mongodb_service.py`

### 7. Demo credentials removed from source code

A hard-coded demo password was removed from `login_view.py`. Demo credentials are now optional local environment variables:

- `DEMO_USERNAME`
- `DEMO_PASSWORD`

Use `.env.example` as the template and keep the real `.env` local.

### 8. Project cleanup

The release archive should not contain the Python virtual environment, Python bytecode caches, `.pytest_cache`, or real `.env` credentials.

## Validation performed

- Python bytecode compilation completed successfully for the application source after the changes.
- No external backend or GUI integration test was claimed because the uploaded project contains a Windows virtual environment and the execution environment here does not have a graphical CustomTkinter display.
- The existing `pytest` invocation reported no tests were collected; therefore there is no existing automated regression suite to rely on.

## Remaining architectural work

The largest remaining performance risk is the number of very large CustomTkinter views and any synchronous database work still present in legacy/unused paths. The next engineering stage should profile real user workflows on Windows with production-like data and then refactor the slowest screens into smaller components with database-side pagination.

## Target

The application should behave as an employee operations platform: immediate feedback, background data loading, minimal repeated queries, simple navigation, and clear workflows — while keeping Python and the existing business functionality.
