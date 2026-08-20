# Untangled Nexus Architecture

## Application Flow

`Application` is the composition root. It initializes SQLite, creates services, supplies them to controllers, and starts the login flow. `AppController` owns the transition from login to the main desktop shell. `NavigationController` creates one workspace view at a time.

## MVC Boundaries

- Models are immutable dataclasses representing employees, Work, attendance, approvals, calendar events, notifications, office requests, and search results.
- Views are CustomTkinter frames and dialogs. They do not issue SQL statements or implement business rules.
- Controllers validate UI-oriented input and invoke services.
- Services own SQLite queries, workflow transitions, calculated values, activity recording, and notifications.

## Data Ownership

- `employees` is the People source of truth.
- `tasks` is the unified Work source of truth. The retained `work_items` table is migrated once for compatibility only.
- `attendance_records` stores one generated record per employee per day.
- `calendar_events` supports existing database events; the Calendar view derives Work due-date entries directly from `tasks` and does not copy them.
- `approvals` holds staged workflow state. `office_requests` references an approval record.
- `notifications` holds role-targeted messages. The Director receives executive brief records only.
- `activity_log` is the dashboard activity feed.

## SQLite Migrations

`Database.initialize()` uses `CREATE TABLE IF NOT EXISTS` plus additive column migrations. It seeds departments and the initial Untangled organisational structure without overwriting existing employee data.

## Role Policy

`app/models/role_permission.py` centralizes default role permissions and module access policy for Director, Business Lead, Operations Manager, and Staff. The placeholder login currently retains its existing behavior; future authentication can inject the authenticated role into this policy without restructuring the application.
