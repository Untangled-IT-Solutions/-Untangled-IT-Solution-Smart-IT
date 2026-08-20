# Untangled Nexus

Untangled Nexus is the desktop operations platform for Untangled IT Solutions. Version 0.3 delivers the first usable business core using Python, CustomTkinter, SQLite, and an MVC-oriented architecture.

## Included Modules

- People Engine: seeded employee directory, filterable cards, and detailed employee profiles.
- Unified Work Engine: category-based operational work, editing, status tracking, checklists, comments, attachment placeholders, and history.
- Attendance Engine: clock in/out, break tracking, daily totals, weekly totals, monthly totals, and generated timesheet records.
- Calendar Engine: a non-duplicated operational calendar derived from Work due dates.
- Approval Engine: staged Operations Manager, Business Lead, and optional Director workflow.
- Office Requests: approval-backed requests for supplies and equipment.
- Executive Dashboards: operational, Business Lead, and Director perspectives backed by SQLite.
- Notification Engine: central role-aware operational notifications and Director executive briefs.
- Global Search: People, Work, RFQs, projects, suppliers, and clients.

## Project Structure

```text
UntangledNexus/
  app/
    controllers/     UI orchestration and commands
    database/        SQLite initialization and additive migrations
    models/          Domain and dashboard view models
    services/        Business rules and persistence
    utils/           Shared theme tokens
    views/           CustomTkinter workspace views
    widgets/         Reusable cards and navigation controls
  data/              Automatically created local SQLite database
  docs/              Architecture and module documentation
  tests/             Service-level regression tests
  main.py            Application entry point
```

## Database

The application creates and migrates `data/untangled_nexus.db` automatically. It never recreates an existing database.

The v0.3 schema includes employee, Work, attendance, calendar, approval, notification, activity, Office Request, supplier, and client tables. Existing `work_items` records are imported once into the unified `tasks` Work store for compatibility.

## Placeholder Login

```text
Username: admin
Password: admin
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Test

```powershell
python -m pytest
```

See [the architecture guide](docs/architecture.md) and [the changelog](CHANGELOG.md) for module and release details.
