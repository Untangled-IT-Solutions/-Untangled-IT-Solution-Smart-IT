"""Attendance tracking and timesheet service."""

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.database.database import Database
from app.models.attendance import AttendanceRecord
from app.services.notification_service import NotificationService


class AttendanceService:
    """Owns attendance state transitions and automatic timesheet calculations."""

    _TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    MAX_BREAK_MINUTES = 60

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

    def clock_in(self, employee_id: int) -> AttendanceRecord:
        """Start the employee's daily attendance record."""
        now = self._now()
        work_date = now.date().isoformat()
        with self._connect() as connection:
            employee = self._get_employee(connection, employee_id)
            existing = self._get_record_for_date(connection, employee_id, work_date)
            if existing is not None and existing.is_clocked_in:
                raise ValueError(f"{employee['full_name']} is already clocked in.")
            if existing is not None and existing.clock_out_at:
                raise ValueError(f"{employee['full_name']} has already clocked out today.")

            cursor = connection.execute(
                """
                INSERT INTO attendance_records (
                    employee_id, employee_name, work_date, clock_in_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    employee_id,
                    employee["full_name"],
                    work_date,
                    self._format_time(now),
                    self._format_time(now),
                    self._format_time(now),
                ),
            )
            connection.execute("UPDATE employees SET clocked_in = 1 WHERE id = ?;", (employee_id,))
            connection.commit()
            record = self._get_by_id(connection, int(cursor.lastrowid))

        self._record_attendance_activity(record, "clocked in")
        return record

    def start_break(self, employee_id: int) -> AttendanceRecord:
        """Start an active employee break."""
        now = self._now()
        with self._connect() as connection:
            record = self._require_active_record(connection, employee_id, now.date().isoformat())
            if record.break_started_at:
                raise ValueError("A break is already in progress.")
            if record.break_duration_minutes >= self.MAX_BREAK_MINUTES:
                raise ValueError("The daily break allowance of 60 minutes has already been used.")
            connection.execute(
                """
                UPDATE attendance_records
                SET break_started_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (self._format_time(now), self._format_time(now), record.id),
            )
            connection.commit()
            updated = self._get_by_id(connection, self._required_id(record))

        self._record_attendance_activity(updated, "started a break")
        return updated

    def end_break(self, employee_id: int) -> AttendanceRecord:
        """Finish a break and accumulate its duration."""
        now = self._now()
        with self._connect() as connection:
            record = self._require_active_record(connection, employee_id, now.date().isoformat())
            if not record.break_started_at:
                raise ValueError("No active break was found.")
            updated = self._close_break(connection, record, now)
            connection.commit()

        self._record_attendance_activity(updated, "ended a break")
        return updated

    def clock_out(self, employee_id: int) -> AttendanceRecord:
        """Finish the work day and calculate net daily hours automatically."""
        now = self._now()
        with self._connect() as connection:
            record = self._require_active_record(connection, employee_id, now.date().isoformat())
            if record.break_started_at:
                record = self._close_break(connection, record, now)

            elapsed_seconds = (now - self._parse_time(record.clock_in_at)).total_seconds()
            break_seconds = record.break_duration_minutes * 60
            hours_worked = round(max(0, elapsed_seconds - break_seconds) / 3600, 2)
            connection.execute(
                """
                UPDATE attendance_records
                SET clock_out_at = ?, hours_worked = ?, updated_at = ?
                WHERE id = ?;
                """,
                (self._format_time(now), hours_worked, self._format_time(now), record.id),
            )
            connection.execute("UPDATE employees SET clocked_in = 0 WHERE id = ?;", (employee_id,))
            connection.commit()
            completed = self._get_by_id(connection, self._required_id(record))

        self._record_attendance_activity(completed, "clocked out")
        return completed

    def get_today_record(self, employee_id: int) -> AttendanceRecord | None:
        """Return the selected employee's record for the current day."""
        with self._connect() as connection:
            return self._get_record_for_date(connection, employee_id, date.today().isoformat())

    def get_today_records(self) -> list[AttendanceRecord]:
        """Return all attendance records created today."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM attendance_records
                WHERE work_date = ?
                ORDER BY employee_name ASC;
                """,
                (date.today().isoformat(),),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_weekly_timesheet(
        self,
        employee_id: int,
        anchor_date: date | None = None,
    ) -> list[AttendanceRecord]:
        """Return the current week's automatically generated daily timesheet rows."""
        anchor = anchor_date or date.today()
        week_start = anchor - timedelta(days=anchor.weekday())
        week_end = week_start + timedelta(days=6)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM attendance_records
                WHERE employee_id = ? AND work_date BETWEEN ? AND ?
                ORDER BY work_date ASC;
                """,
                (employee_id, week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_weekly_total(self, employee_id: int, anchor_date: date | None = None) -> float:
        """Calculate an employee's net weekly total from attendance records."""
        return round(sum(record.hours_worked for record in self.get_weekly_timesheet(employee_id, anchor_date)), 2)

    def get_monthly_total(self, employee_id: int, anchor_date: date | None = None) -> float:
        """Calculate a monthly total from the automatically generated timesheet rows."""
        anchor = anchor_date or date.today()
        month_start = anchor.replace(day=1).isoformat()
        if anchor.month == 12:
            next_month = anchor.replace(year=anchor.year + 1, month=1, day=1)
        else:
            next_month = anchor.replace(month=anchor.month + 1, day=1)
        with self._connect() as connection:
            value = connection.execute(
                """
                SELECT COALESCE(SUM(hours_worked), 0) FROM attendance_records
                WHERE employee_id = ? AND work_date >= ? AND work_date < ?;
                """,
                (employee_id, month_start, next_month.isoformat()),
            ).fetchone()[0]
        return round(float(value or 0), 2)

    def get_live_hours(self, record: AttendanceRecord) -> float:
        """Calculate elapsed net hours for an active record without persisting a mutation."""
        return round(self.get_live_seconds(record) / 3600, 2)

    def get_live_seconds(self, record: AttendanceRecord) -> int:
        """Return the exact net worked time, including seconds, for the live attendance timer."""
        if not record.is_clocked_in:
            return int(record.hours_worked * 3600)
        now = self._now()
        break_minutes = record.break_duration_minutes
        if record.break_started_at:
            break_minutes += self._active_break_minutes(record, now)
        elapsed_seconds = (now - self._parse_time(record.clock_in_at)).total_seconds()
        return int(max(0, elapsed_seconds - (break_minutes * 60)))

    def get_live_break_seconds(self, record: AttendanceRecord) -> int:
        """Return break time used today, capped at the one-hour allowance."""
        completed_seconds = min(record.break_duration_minutes, self.MAX_BREAK_MINUTES) * 60
        if not record.break_started_at:
            return completed_seconds
        active_seconds = max(0, int((self._now() - self._parse_time(record.break_started_at)).total_seconds()))
        remaining_seconds = max(0, (self.MAX_BREAK_MINUTES * 60) - completed_seconds)
        return completed_seconds + min(active_seconds, remaining_seconds)

    def _record_attendance_activity(self, record: AttendanceRecord, action: str) -> None:
        if self._notifications is None:
            return
        message = f"{record.employee_name} {action}."
        self._notifications.record_activity("Attendance", message, "Attendance", record.id)
        self._notifications.notify_operational(
            ("Operations Manager",),
            "Attendance update",
            message,
            "Attendance",
            "Attendance",
            record.id,
        )

    def _require_active_record(
        self,
        connection: sqlite3.Connection,
        employee_id: int,
        work_date: str,
    ) -> AttendanceRecord:
        record = self._get_record_for_date(connection, employee_id, work_date)
        if record is None or not record.is_clocked_in:
            raise ValueError("Clock in before using this attendance action.")
        return record

    def _close_break(
        self,
        connection: sqlite3.Connection,
        record: AttendanceRecord,
        ended_at: datetime,
    ) -> AttendanceRecord:
        started_at = self._parse_time(record.break_started_at)
        duration = max(0, int((ended_at - started_at).total_seconds() // 60))
        remaining_minutes = max(0, self.MAX_BREAK_MINUTES - record.break_duration_minutes)
        duration = min(duration, remaining_minutes)
        connection.execute(
            """
            UPDATE attendance_records
            SET break_started_at = NULL,
                break_duration_minutes = break_duration_minutes + ?,
                updated_at = ?
            WHERE id = ?;
            """,
            (duration, self._format_time(ended_at), record.id),
        )
        return self._get_by_id(connection, self._required_id(record))

    def _active_break_minutes(self, record: AttendanceRecord, now: datetime) -> int:
        """Return the currently active break amount that may reduce worked time."""
        if not record.break_started_at:
            return 0
        elapsed = max(0, int((now - self._parse_time(record.break_started_at)).total_seconds() // 60))
        remaining = max(0, self.MAX_BREAK_MINUTES - record.break_duration_minutes)
        return min(elapsed, remaining)

    @staticmethod
    def _get_employee(connection: sqlite3.Connection, employee_id: int) -> sqlite3.Row:
        employee = connection.execute(
            "SELECT id, full_name FROM employees WHERE id = ?;", (employee_id,)
        ).fetchone()
        if employee is None:
            raise ValueError("Employee was not found.")
        return employee

    def _get_record_for_date(
        self,
        connection: sqlite3.Connection,
        employee_id: int,
        work_date: str,
    ) -> AttendanceRecord | None:
        row = connection.execute(
            """
            SELECT * FROM attendance_records
            WHERE employee_id = ? AND work_date = ?;
            """,
            (employee_id, work_date),
        ).fetchone()
        return self._row_to_record(row) if row is not None else None

    def _get_by_id(self, connection: sqlite3.Connection, record_id: int) -> AttendanceRecord:
        row = connection.execute(
            "SELECT * FROM attendance_records WHERE id = ?;", (record_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Attendance record was not found.")
        return self._row_to_record(row)

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _required_id(record: AttendanceRecord) -> int:
        if record.id is None:
            raise ValueError("Attendance record is missing an identifier.")
        return record.id

    @classmethod
    def _format_time(cls, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime(cls._TIME_FORMAT)

    @classmethod
    def _parse_time(cls, value: str) -> datetime:
        return datetime.strptime(value, cls._TIME_FORMAT).replace(tzinfo=timezone.utc)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(microsecond=0)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AttendanceRecord:
        return AttendanceRecord(
            id=row["id"],
            employee_id=row["employee_id"],
            employee_name=row["employee_name"],
            work_date=row["work_date"],
            clock_in_at=row["clock_in_at"] or "",
            clock_out_at=row["clock_out_at"] or "",
            break_started_at=row["break_started_at"] or "",
            break_duration_minutes=int(row["break_duration_minutes"] or 0),
            hours_worked=float(row["hours_worked"] or 0),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
