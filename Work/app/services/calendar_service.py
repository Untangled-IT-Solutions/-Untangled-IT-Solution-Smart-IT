"""Database-backed operational calendar service."""

import sqlite3
from calendar import monthrange
from datetime import date, datetime, timezone
from pathlib import Path

from app.database.database import Database
from app.models.calendar_event import CalendarEvent
from app.services.notification_service import NotificationService


class CalendarService:
    """Combines manually scheduled events with due dates from unified Work records."""

    EVENT_TYPES = (
        "Meeting",
        "Leave",
        "Birthday",
        "Project",
        "Company Event",
        "Approval Deadline",
        "RFQ Deadline",
        "Supplier Deadline",
        "Technical Visit",
        "Software Milestone",
        "Training",
        "Other",
    )
    RECURRENCE_OPTIONS = ("None", "Daily", "Weekly", "Monthly", "Yearly")

    def __init__(
        self,
        database: Database,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._database = database
        self._notifications = notification_service

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def get_month_events(self, year: int, month: int) -> list[CalendarEvent]:
        """Return all manual and Work-derived events visible in a month."""
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])
        with self._connect() as connection:
            manual_rows = connection.execute(
                """
                SELECT * FROM calendar_events
                WHERE (
                    start_date <= ?
                    OR recurrence IN ('Daily', 'Weekly', 'Monthly', 'Yearly')
                )
                AND (end_date IS NULL OR end_date = '' OR end_date >= ?)
                ORDER BY start_date ASC, id ASC;
                """,
                (last_day.isoformat(), first_day.isoformat()),
            ).fetchall()
            task_rows = connection.execute(
                """
                SELECT id, title, category, due_date, department, description, created_at
                FROM tasks
                WHERE due_date BETWEEN ? AND ?
                AND status NOT IN ('Completed', 'Cancelled')
                ORDER BY due_date ASC, id ASC;
                """,
                (first_day.isoformat(), last_day.isoformat()),
            ).fetchall()

        events = []
        for row in manual_rows:
            event = self._row_to_event(row)
            events.extend(self._expand_recurring_event(event, first_day, last_day))
        events.extend(self._task_to_event(row) for row in task_rows)
        return sorted(events, key=lambda event: (event.start_date, event.title.lower()))

    def get_upcoming_events(self, days: int = 7) -> list[CalendarEvent]:
        """Return upcoming database calendar entries without duplicate derived events."""
        today = date.today()
        from datetime import timedelta
        end_date = today + timedelta(days=max(days - 1, 0))
        events: list[CalendarEvent] = []
        current = today.replace(day=1)
        while current <= end_date.replace(day=1):
            events.extend(self.get_month_events(current.year, current.month))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return [event for event in events if today.isoformat() <= event.start_date <= end_date.isoformat()]

    def create_event(
        self,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ) -> CalendarEvent:
        """Create one manual event after rejecting an exact duplicate."""
        self._validate_date(start_date, "Start date")
        if end_date:
            self._validate_date(end_date, "End date")
            if end_date < start_date:
                raise ValueError("End date cannot be before the start date.")
        if not title.strip():
            raise ValueError("Event title is required.")
        recurrence = recurrence if recurrence in self.RECURRENCE_OPTIONS else "None"

        with self._connect() as connection:
            duplicate = connection.execute(
                """
                SELECT id FROM calendar_events
                WHERE source_type = 'Manual'
                AND title = ? AND event_type = ? AND start_date = ?;
                """,
                (title.strip(), event_type, start_date),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("A matching calendar event already exists for this date.")
            now_ts = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
            cursor = connection.execute(
                """
                INSERT INTO calendar_events (
                    title, event_type, start_date, end_date, department, details, source_type, recurrence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'Manual', ?, ?);
                """,
                (title.strip(), event_type, start_date, end_date, department, details.strip(), recurrence, now_ts),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM calendar_events WHERE id = ?;", (cursor.lastrowid,)
            ).fetchone()
        event = self._row_to_event(row)

        if self._notifications is not None:
            self._notifications.record_activity(
                "Calendar",
                f"Calendar event created: {event.title}",
                "CalendarEvent",
                event.id,
            )
            self._notifications.notify_operational(
                ("Operations Manager",),
                "Calendar update",
                f"{event.event_type}: {event.title} on {event.start_date}",
                "Calendar",
                "CalendarEvent",
                event.id,
            )
        return event

    def update_event(
        self,
        event_id: int,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ) -> CalendarEvent:
        """Update one manual calendar event."""
        self._validate_manual_event(event_id)
        self._validate_date(start_date, "Start date")
        if end_date:
            self._validate_date(end_date, "End date")
            if end_date < start_date:
                raise ValueError("End date cannot be before the start date.")
        if not title.strip():
            raise ValueError("Event title is required.")
        recurrence = recurrence if recurrence in self.RECURRENCE_OPTIONS else "None"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE calendar_events
                SET title = ?, event_type = ?, start_date = ?, end_date = ?,
                    department = ?, details = ?, recurrence = ?
                WHERE id = ? AND source_type = 'Manual';
                """,
                (
                    title.strip(),
                    event_type,
                    start_date,
                    end_date,
                    department,
                    details.strip(),
                    recurrence,
                    event_id,
                ),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM calendar_events WHERE id = ?;", (event_id,)
            ).fetchone()
        event = self._row_to_event(row)
        if self._notifications is not None:
            self._notifications.record_activity(
                "Calendar", f"Calendar event updated: {event.title}", "CalendarEvent", event.id
            )
        return event

    def delete_event(self, event_id: int) -> None:
        """Delete one manual calendar event."""
        self._validate_manual_event(event_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT title FROM calendar_events WHERE id = ?;", (event_id,)
            ).fetchone()
            connection.execute(
                "DELETE FROM calendar_events WHERE id = ? AND source_type = 'Manual';",
                (event_id,),
            )
            connection.commit()
        if self._notifications is not None and row is not None:
            self._notifications.record_activity(
                "Calendar", f"Calendar event deleted: {row['title']}", "CalendarEvent", event_id
            )

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @classmethod
    def _task_to_event(cls, row: sqlite3.Row) -> CalendarEvent:
        category = row["category"] or "Administration"
        event_type = {
            "RFQ": "RFQ Deadline",
            "Tender": "RFQ Deadline",
            "Technical": "Technical Visit",
            "Software": "Software Milestone",
            "Website": "Software Milestone",
            "Supplier Registration": "Supplier Deadline",
            "Training": "Training",
        }.get(category, "Work Due")
        return CalendarEvent(
            id=row["id"],
            title=row["title"],
            event_type=event_type,
            start_date=row["due_date"],
            end_date="",
            department=row["department"] or "",
            details=row["description"] or "",
            source_type="Task",
            source_id=row["id"],
            recurrence="None",
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> CalendarEvent:
        return CalendarEvent(
            id=row["id"],
            title=row["title"],
            event_type=row["event_type"],
            start_date=row["start_date"],
            end_date=row["end_date"] or "",
            department=row["department"] or "",
            details=row["details"] or "",
            source_type=row["source_type"],
            source_id=row["source_id"],
            recurrence=row["recurrence"] if "recurrence" in row.keys() else "None",
            created_at=row["created_at"],
        )

    def _validate_manual_event(self, event_id: int) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT source_type FROM calendar_events WHERE id = ?;", (event_id,)
            ).fetchone()
        if row is None:
            raise ValueError("Calendar event was not found.")
        if row["source_type"] != "Manual":
            raise ValueError("Only manually created calendar events can be edited.")

    @staticmethod
    def _expand_recurring_event(
        event: CalendarEvent, first_day: date, last_day: date
    ) -> list[CalendarEvent]:
        if event.recurrence == "None":
            return [event]
        start = datetime.strptime(event.start_date, "%Y-%m-%d").date()
        if start > last_day:
            return []
        expanded: list[CalendarEvent] = []
        current = max(start, first_day)
        while current <= last_day:
            include = False
            if event.recurrence == "Daily":
                include = current >= start
            elif event.recurrence == "Weekly":
                include = current >= start and current.weekday() == start.weekday()
            elif event.recurrence == "Monthly":
                include = current >= start and current.day == start.day
            elif event.recurrence == "Yearly":
                include = current >= start and current.month == start.month and current.day == start.day
            if include:
                expanded.append(
                    CalendarEvent(
                        id=event.id,
                        title=event.title,
                        event_type=event.event_type,
                        start_date=current.isoformat(),
                        end_date=event.end_date,
                        department=event.department,
                        details=event.details,
                        source_type=event.source_type,
                        source_id=event.source_id,
                        recurrence=event.recurrence,
                        created_at=event.created_at,
                    )
                )
            current = current.fromordinal(current.toordinal() + 1)
        return expanded

    @staticmethod
    def _validate_date(value: str, label: str) -> None:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError(f"{label} must use YYYY-MM-DD.") from error
