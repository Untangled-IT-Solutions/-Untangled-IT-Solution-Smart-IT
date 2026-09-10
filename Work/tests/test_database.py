"""Database initialization tests."""

import sqlite3
from datetime import date, datetime, timezone

from app.database.database import Database


def test_database_initializes_required_tables(tmp_path) -> None:
    db_path = tmp_path / "untangled_nexus.db"

    Database(db_path).initialize()

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table';"
            ).fetchall()
        }

    assert {
        "users", "departments", "tasks", "projects", "employees", "work_items",
        "attendance_records", "calendar_events", "approvals", "notifications",
        "activity_log", "work_history", "office_requests", "suppliers", "clients",
        "auth_sessions",
    }.issubset(table_names)


def test_database_normalizes_old_local_timestamps_to_utc(tmp_path) -> None:
    db_path = tmp_path / "untangled_nexus.db"
    database = Database(db_path)
    database.initialize()

    utc_value = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    local_tz = datetime.now().astimezone().tzinfo
    local_value = utc_value.astimezone(local_tz).strftime("%Y-%m-%d %H:%M:%S")

    with database.connection() as connection:
        connection.execute(
            "INSERT INTO attendance_records (employee_id, employee_name, work_date, clock_in_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?);",
            (1, "Test User", date.today().isoformat(), local_value, local_value, local_value),
        )
        connection.execute(
            "INSERT INTO calendar_events (title, event_type, start_date, department, details, source_type, recurrence, created_at) VALUES (?, ?, ?, ?, ?, 'Manual', 'None', ?);",
            ("Migration Event", "Meeting", date.today().isoformat(), "Operations", "Migration record", local_value),
        )
        connection.execute("PRAGMA user_version = 0;")

    database.initialize()

    with database.connection() as connection:
        row = connection.execute(
            "SELECT clock_in_at, created_at, updated_at FROM attendance_records WHERE employee_name = ?;",
            ("Test User",),
        ).fetchone()
        assert row is not None
        assert row["clock_in_at"] == "2024-01-01 12:00:00"
        assert row["created_at"] == "2024-01-01 12:00:00"
        assert row["updated_at"] == "2024-01-01 12:00:00"

        event_row = connection.execute(
            "SELECT created_at FROM calendar_events WHERE title = ?;",
            ("Migration Event",),
        ).fetchone()
        assert event_row is not None
        assert event_row["created_at"] == "2024-01-01 12:00:00"
