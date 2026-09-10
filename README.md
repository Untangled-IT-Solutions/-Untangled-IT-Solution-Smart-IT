# Untangled Nexus

Untangled Nexus is the desktop operations platform for Untangled IT Solutions. Version 0.3 delivers the first usable business core using Python, CustomTkinter, SQLite, and an MVC-oriented architecture.

## Included Modules

- People Engine: seeded employee directory, filterable cards, and detailed employee profiles.
- Unified Work Engine: category-based operational work, editing, status tracking, checklists, comments, attachment placeholders, and history.
- Sprint Planning: Directors and Super Users submit unassigned work; the Operations Manager prioritises and assigns it before employees begin work.
- Attendance Engine: clock in/out, break tracking, daily totals, weekly totals, monthly totals, and generated timesheet records.
- Calendar Engine: a non-duplicated operational calendar derived from Work due dates.
- Written Meeting Reports: consent-controlled live transcription, an AI summary,
  a Word transcript report, and optional email delivery without retaining an audio file.
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
## Written meeting reports and email

Install the project packages, copy `.env.example` to `.env`, and add the real OpenAI
and SMTP values to `.env`. Set `NEXUS_EMAIL_ENABLED=true` when SMTP is ready. Keep
`.env` private; it is ignored by Git.

On Windows PowerShell, do not type `NAME=value` as a command. Either use the `.env`
file (recommended), or set a value for the current terminal with:

```powershell
$env:NEXUS_EMAIL_ENABLED = "true"
$env:OPENAI_MEETING_NOTES_MODEL = "gpt-5.4-mini"
python main.py
```

## Sprint Planning workflow

The Tasks workspace follows the SprintFlow Pro structure imported from Lovable:
**Current Sprint**, **Next Sprint**, and **Backlog** board columns, story-point
estimates, progress, priority, owner, quick status changes, **Pull In**, **Defer**,
and **Close Sprint**. Search, workstream, and category filters continue to work
across the board.

Full sprint access is assigned to **Ubuntu Hadebe** (Operations Manager),
**Zandile Johanna Maredi** (Director; also recognised as Zandil Maredi), and
**Benny Moremi** (Director; also recognised as Benny). They can create, assign,
edit, prioritise, move, and close sprint work. The assignment list is limited to
Siyanda Nkosi, Nonhlanhla Hlatshwayo, Ubuntu Hadebe, Gift Wesi, Dipuo Tlowana,
Bongiwe Ngobese, and Botshelo Lehasa.

Employees can create their own tasks and update their own non-destructive fields
and statuses. New employee-created work enters **Backlog / Inbox** for review.
Directors and Super Users can also submit planning work. When a full-access user
assigns an Inbox task, Nexus moves it to **To Do** and sends the employee an in-app
notification plus the configured assignment email. Employees cannot delete tasks;
they use Cancelled or Archived so the audit history is preserved.

In Calendar, add an event, enter one or more report email addresses, confirm that
everyone agreed to transcription, and select **Start transcription**. Select
**Stop & create report** when the meeting ends. The summary is added to Event
Details, the full report is saved under `data/meeting_reports`, and the Word report
is emailed when SMTP is enabled. Microphone audio is held only in memory while the
transcription request runs and is not saved or emailed.
