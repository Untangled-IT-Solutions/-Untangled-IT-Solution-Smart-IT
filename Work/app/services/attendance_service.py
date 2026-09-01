"""Attendance tracking and timesheet service with caching."""

import sqlite3
from datetime import date, datetime, timedelta, timezone, time as datetime_time  # ← FIX: alias time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
import time as time_module  # ← FIX: alias time module
from typing import Optional

from app.database.database import Database
from app.models.attendance import AttendanceRecord
from app.services.notification_service import NotificationService


class AttendanceService:
    """Owns attendance state transitions and automatic timesheet calculations with caching."""

    _TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    _ATTENDANCE_TIMEZONE = "Africa/Johannesburg"
    _START_TIME = datetime_time(8, 0, 0)  # ← FIX: use datetime_time
    _LATE_AFTER = datetime_time(9, 0, 0)  # ← FIX: use datetime_time
    
    # Cache settings
    _CACHE_TTL = 2  # 2 seconds cache TTL for timer status
    _CACHE_HISTORY_TTL = 30  # 30 seconds for history

    @classmethod
    def get_punctuality_status(cls, clock_in_at: str) -> str:
        """Classify a clock-in using local company time."""
        if not clock_in_at:
            return "absent"
        local = cls._parse_time(clock_in_at).astimezone(cls._local_zone())
        if local.time() < cls._START_TIME:
            return "early"
        if local.time() <= cls._LATE_AFTER:
            return "on_time"
        return "late"

    def __init__(
        self,
        database: Database,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._database = database
        self._notifications = notification_service
        
        # Initialize caches
        self._timer_cache = {}  # employee_id -> (timestamp, result)
        self._record_cache = {}  # employee_id -> (timestamp, record)
        self._weekly_cache = {}  # (employee_id, anchor_date) -> (timestamp, records)
        self._today_records_cache = None  # (timestamp, records)
        self._today_records_cache_time = 0

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def clock_in(self, employee_id: int) -> AttendanceRecord:
        """Start the employee's daily attendance record."""
        # Clear caches for this employee
        self._clear_employee_cache(employee_id)
        
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

        punctuality = self.get_punctuality_status(record.clock_in_at)
        self._record_attendance_activity(record, f"clocked in ({punctuality})")
        return record

    def get_attendance_status(self, employee_id: int) -> dict:
        """Return today's timer state and punctuality state with caching."""
        # Check cache
        if employee_id in self._timer_cache:
            cached_time, cached_result = self._timer_cache[employee_id]
            if time_module.time() - cached_time < self._CACHE_TTL:  # ← FIX: use time_module
                # Still valid, but update elapsed time
                result = cached_result.copy()
                if result.get("elapsed_seconds") is not None:
                    # Add elapsed time since cache
                    elapsed_since = time_module.time() - cached_time  # ← FIX: use time_module
                    result["elapsed_seconds"] = result.get("elapsed_seconds", 0) + elapsed_since
                return result
        
        # Get fresh data
        record = self.get_today_record(employee_id)
        if record is None:
            result = {"status": "not_started", "punctuality": "absent", "emoji": "⚫", "elapsed_seconds": 0}
            self._timer_cache[employee_id] = (time_module.time(), result)  # ← FIX: use time_module
            return result
            
        punctuality = self.get_punctuality_status(record.clock_in_at)
        emoji = {"early": "🟡", "on_time": "🟢", "late": "🔴"}.get(punctuality, "⚪")
        
        status = "on_break" if record.is_on_break else ("clocked_in" if record.is_clocked_in else "clocked_out")
        
        # Calculate elapsed seconds
        elapsed_seconds = 0
        break_minutes = record.break_duration_minutes or 0
        
        if record.is_clocked_in:
            now = self._now()
            clock_in_time = self._parse_time(record.clock_in_at)
            elapsed_seconds = int((now - clock_in_time).total_seconds())
            
            # Subtract break time
            if record.break_started_at:
                break_start = self._parse_time(record.break_started_at)
                break_minutes += int((now - break_start).total_seconds() // 60)
            
            elapsed_seconds = max(0, elapsed_seconds - (break_minutes * 60))
        elif record.clock_out_at:
            # Completed record - use hours_worked
            elapsed_seconds = int(record.hours_worked * 3600) if record.hours_worked else 0
            
        result = {
            "status": status,
            "punctuality": punctuality,
            "emoji": emoji,
            "elapsed_seconds": elapsed_seconds,
            "break_minutes": break_minutes,
            "record": record,
        }
        
        # Cache the result
        self._timer_cache[employee_id] = (time_module.time(), result)  # ← FIX: use time_module
        return result

    def get_timer_status(self, employee_id: int) -> dict:
        """Alias for get_attendance_status for compatibility."""
        return self.get_attendance_status(employee_id)

    def start_break(self, employee_id: int) -> AttendanceRecord:
        """Start an active employee break."""
        # Clear caches
        self._clear_employee_cache(employee_id)
        
        now = self._now()
        with self._connect() as connection:
            record = self._require_active_record(connection, employee_id, now.date().isoformat())
            if record.break_started_at:
                raise ValueError("A break is already in progress.")
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
        # Clear caches
        self._clear_employee_cache(employee_id)
        
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
        # Clear caches
        self._clear_employee_cache(employee_id)
        
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
        """Return the selected employee's record for the current day with caching."""
        # Check cache
        if employee_id in self._record_cache:
            cached_time, cached_record = self._record_cache[employee_id]
            if time_module.time() - cached_time < self._CACHE_TTL:  # ← FIX: use time_module
                return cached_record
        
        # Get from database
        with self._connect() as connection:
            record = self._get_record_for_date(connection, employee_id, date.today().isoformat())
        
        # Cache the result
        self._record_cache[employee_id] = (time_module.time(), record)  # ← FIX: use time_module
        return record

    def get_today_records(self) -> list[AttendanceRecord]:
        """Return all attendance records created today with caching."""
        # Check cache
        if self._today_records_cache is not None:
            cached_time, cached_records = self._today_records_cache
            if time_module.time() - cached_time < self._CACHE_TTL:  # ← FIX: use time_module
                return cached_records
        
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM attendance_records
                WHERE work_date = ?
                ORDER BY employee_name ASC;
                """,
                (date.today().isoformat(),),
            ).fetchall()
        
        records = [self._row_to_record(row) for row in rows]
        self._today_records_cache = (time_module.time(), records)  # ← FIX: use time_module
        return records

    def get_weekly_timesheet(
        self,
        employee_id: int,
        anchor_date: date | None = None,
    ) -> list[AttendanceRecord]:
        """Return the current week's automatically generated daily timesheet rows with caching."""
        anchor = anchor_date or date.today()
        week_start = anchor - timedelta(days=anchor.weekday())
        week_end = week_start + timedelta(days=6)
        
        cache_key = (employee_id, week_start.isoformat())
        
        # Check cache
        if cache_key in self._weekly_cache:
            cached_time, cached_records = self._weekly_cache[cache_key]
            if time_module.time() - cached_time < self._CACHE_HISTORY_TTL:  # ← FIX: use time_module
                return cached_records
        
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM attendance_records
                WHERE employee_id = ? AND work_date BETWEEN ? AND ?
                ORDER BY work_date ASC;
                """,
                (employee_id, week_start.isoformat(), week_end.isoformat()),
            ).fetchall()
        
        records = [self._row_to_record(row) for row in rows]
        self._weekly_cache[cache_key] = (time_module.time(), records)  # ← FIX: use time_module
        return records

    def get_weekly_total(self, employee_id: int, anchor_date: date | None = None) -> float:
        """Calculate an employee's net weekly total from attendance records."""
        records = self.get_weekly_timesheet(employee_id, anchor_date)
        return round(sum(record.hours_worked for record in records), 2)

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
        if not record.is_clocked_in:
            return record.hours_worked
        now = self._now()
        break_minutes = record.break_duration_minutes
        if record.break_started_at:
            break_minutes += max(
                0,
                int((now - self._parse_time(record.break_started_at)).total_seconds() // 60),
            )
        elapsed_seconds = (now - self._parse_time(record.clock_in_at)).total_seconds()
        return round(max(0, elapsed_seconds - (break_minutes * 60)) / 3600, 2)

    def _clear_employee_cache(self, employee_id: int) -> None:
        """Clear all caches for a specific employee."""
        self._timer_cache.pop(employee_id, None)
        self._record_cache.pop(employee_id, None)
        # Clear weekly cache
        keys_to_remove = []
        for key in self._weekly_cache:
            if key[0] == employee_id:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self._weekly_cache.pop(key, None)
        # Clear today records cache
        self._today_records_cache = None

    def clear_all_caches(self) -> None:
        """Clear all caches."""
        self._timer_cache.clear()
        self._record_cache.clear()
        self._weekly_cache.clear()
        self._today_records_cache = None

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

    @classmethod
    def _local_zone(cls):
        try:
            return ZoneInfo(cls._ATTENDANCE_TIMEZONE)
        except ZoneInfoNotFoundError:
            return timezone(timedelta(hours=2), cls._ATTENDANCE_TIMEZONE)

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
