# Untangled Nexus – Client Architecture

## Goal

Stop **God Views** (2k–3k line files that mix layout, networking, and business rules).

## Layers

```
┌─────────────────────────────────────────┐
│  views/          widgets only + events  │
│  presenters/     orchestrate use-cases  │
│  controllers/    app wiring / nav       │
│  services/       Backend API I/O        │
│  models/         dataclasses            │
│  ui/             BaseWorkspaceView etc. │
└─────────────────────────────────────────┘
```

### Rules

1. **Views**
   - Create widgets and bind events.
   - Call `presenter` / `controller` / `refresh()` — never call `BackendAPIClient` directly for new code.
   - Inherit `BaseWorkspaceView` for sidebar pages when practical.
   - `load_data()` runs off the UI thread; `apply_data()` on the main thread.

2. **Presenters**
   - No `customtkinter` imports.
   - Accept services in `__init__`.
   - Return plain data (dicts / models) for the view to render.

3. **Services**
   - Only place that performs HTTP (`BackendAPIClient`).
   - Raise `BackendAPIError`; do not show message boxes.

4. **Controllers**
   - Composition root helpers and navigation factory.
   - Keep thin; do not accumulate UI code.

## Feature packages

Large features live under `app/views/<feature>/`:

```
views/quotes/
  constants.py    # status enums, colors
  formatting.py   # pure helpers
  view.py         # UI (target: further split list/detail panels)
```

Navigation keeps importing:

```python
from app.views.quote_management_view import QuoteManagementView
```

that module is a **compatibility shim** re-exporting the package view.

## Migrating a God View (checklist)

1. Extract constants → `constants.py`
2. Extract pure functions → `formatting.py` / `*helpers.py`
3. Move API calls → `services/*_service.py`
4. Move orchestration → `presenters/*_presenter.py`
5. Leave view with `build()` + `apply_data()` only
6. Cap new view files at **~400 lines**; split panels if larger

## Target sizes

| Layer        | Soft limit |
|-------------|------------|
| View file   | 400 lines  |
| Presenter   | 250 lines  |
| Service     | 300 lines  |
| Widget      | 150 lines  |

## Do not

- Add new network calls inside `*_view.py`
- Swallow all exceptions with bare `except Exception: pass`
- Schedule `after()` without tracking jobs for cancel on destroy
