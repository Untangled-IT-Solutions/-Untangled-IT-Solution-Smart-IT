"""Fast attendance adapter.

The desktop client treats the backend as the source of truth for attendance
state, but never polls it for the live clock.  After the initial state is
loaded, elapsed time is calculated locally from the server timestamps.  The
backend is contacted only for state-changing actions or an explicit refresh.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import time
from zoneinfo import ZoneInfo

from app.services.backend_api_client import BackendAPIClient


class MongoAttendanceService:
    LOCAL_ZONE = ZoneInfo("Africa/Johannesburg")
    UTC = timezone.utc
    STATE_CACHE_SECONDS = 30.0

    def __init__(self, backend: BackendAPIClient):
        self._backend = backend
        self._today_cache: Optional[dict[str, Any]] = None
        self._today_cache_at = 0.0
        self._state: Optional[dict[str, Any]] = None
        self._state_at = 0.0
        self._summary_cache = (0.0, 0.0, 0.0)
        self._server_offset_seconds = 0.0

    @classmethod
    def _parse_datetime(cls, value: Any) -> Any:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value

    @classmethod
    def _as_local(cls, value: Any) -> Optional[datetime]:
        value = cls._parse_datetime(value)
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=cls.UTC)
        return value.astimezone(cls.LOCAL_ZONE)

    @classmethod
    def format_local_time(cls, value: Any) -> str:
        local = cls._as_local(value)
        return local.strftime("%H:%M:%S") if local else "--:--:--"

    @classmethod
    def format_local_datetime(cls, value: Any) -> str:
        local = cls._as_local(value)
        return local.strftime("%Y-%m-%d %H:%M:%S") if local else "--"

    @classmethod
    def _normalise_record(cls, record: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not record:
            return None
        result = dict(record)
        for key in (
            "clock_in_at", "clock_out_at", "break_started_at", "break_ended_at",
            "lunch_started_at", "lunch_ended_at", "created_at", "updated_at",
        ):
            if key in result:
                result[key] = cls._parse_datetime(result[key])
        return result

    @staticmethod
    def _state_from_record(record: Optional[dict[str, Any]]) -> dict[str, Any]:
        if not record:
            return {
                "success": True,
                "state": "not_started",
                "status": "not_started",
                "elapsed_seconds": 0,
                "elapsed_hours": 0,
                "record": None,
            }

        status = record.get("status") or "not_started"
        if record.get("clock_out_at"):
            state = "completed"
            elapsed = float(record.get("hours_worked") or 0) * 3600
        elif record.get("break_started_at"):
            state = "on_break"
            elapsed = 0
        elif record.get("clock_in_at"):
            state = "working"
            elapsed = 0
        else:
            state = "not_started"
            elapsed = 0

        return {
            "success": True,
            "state": state,
            "status": status,
            "elapsed_seconds": elapsed,
            "elapsed_hours": elapsed / 3600,
            "clock_in_at": record.get("clock_in_at"),
            "clock_out_at": record.get("clock_out_at"),
            "break_started_at": record.get("break_started_at"),
            "break_duration_minutes": float(record.get("break_duration_minutes") or 0),
            "record": record,
        }

    def _set_state(self, state: dict[str, Any]) -> dict[str, Any]:
        state = dict(state)
        state["record"] = self._normalise_record(state.get("record"))

        # Keep the timer aligned to the backend clock so a workstation with
        # an incorrect Windows clock does not make attendance hours drift.
        server_time = self._parse_datetime(state.get("server_time"))
        if isinstance(server_time, datetime):
            if server_time.tzinfo is None:
                server_time = server_time.replace(tzinfo=self.UTC)
            self._server_offset_seconds = (server_time - datetime.now(self.UTC)).total_seconds()

        self._state = state
        self._state_at = time.monotonic()
        self._today_cache = state.get("record")
        self._today_cache_at = self._state_at
        return state

    def refresh_state(self, employee_id: Any = None) -> dict[str, Any]:
        """Fetch authoritative attendance state once from the backend."""
        data = self._backend.attendance("/api/attendance/status")
        return self._set_state(data)

    def get_today_record(self, employee_id: Any, force: bool = False) -> Optional[dict[str, Any]]:
        now = time.monotonic()
        if not force and self._today_cache is not None and now - self._today_cache_at < self.STATE_CACHE_SECONDS:
            return self._today_cache

        # The state endpoint contains the same today's record, so do not make
        # a second HTTP request to /attendance/today for normal UI refreshes.
        state = self.refresh_state(employee_id)
        return state.get("record")

    def get_timer_status(self, employee_id: Any, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and self._state is not None and now - self._state_at < self.STATE_CACHE_SECONDS:
            return dict(self._state)
        return self.refresh_state(employee_id)

    def _apply_action_response(self, data: dict[str, Any]) -> dict[str, Any]:
        record = self._normalise_record(data.get("record"))
        if record is not None:
            state = self._state_from_record(record)
            state.update({k: v for k, v in data.items() if k not in {"record"}})
            return self._set_state(state)
        return self._set_state(data)

    def _invalidate_summaries(self) -> None:
        self._summary_cache = (0.0, 0.0, 0.0)
        self._server_offset_seconds = 0.0

    def clock_in(self, employee_id: Any, employee_name: str = "") -> dict[str, Any]:
        data = self._backend.attendance("/api/attendance/clock-in", {})
        self._invalidate_summaries()
        return self._apply_action_response(data)

    def clock_out(self, employee_id: Any) -> dict[str, Any]:
        data = self._backend.attendance("/api/attendance/clock-out", {})
        self._invalidate_summaries()
        return self._apply_action_response(data)

    def start_break(self, employee_id: Any) -> dict[str, Any]:
        data = self._backend.attendance("/api/attendance/break/start", {})
        self._invalidate_summaries()
        return self._apply_action_response(data)

    def end_break(self, employee_id: Any) -> dict[str, Any]:
        data = self._backend.attendance("/api/attendance/break/end", {})
        self._invalidate_summaries()
        return self._apply_action_response(data)

    def get_live_seconds(self, record: Optional[dict[str, Any]]) -> int:
        if not record:
            return 0
        if record.get("status") == "clocked_out":
            return int(round(float(record.get("hours_worked") or 0) * 3600))

        start = self._as_local(record.get("clock_in_at"))
        if not start:
            return 0

        now = datetime.now(self.LOCAL_ZONE) + timedelta(seconds=self._server_offset_seconds)
        seconds = max(0.0, (now - start).total_seconds())
        seconds -= float(record.get("break_duration_minutes") or 0) * 60
        seconds -= float(record.get("lunch_duration_minutes") or 0) * 60

        active_break = self._as_local(record.get("break_started_at"))
        if active_break:
            seconds -= max(0.0, (now - active_break).total_seconds())

        active_lunch = self._as_local(record.get("lunch_started_at"))
        if active_lunch:
            seconds -= max(0.0, (now - active_lunch).total_seconds())

        return max(0, int(seconds))

    def get_live_hours(self, record: Optional[dict[str, Any]]) -> float:
        return self.get_live_seconds(record) / 3600.0

    def get_attendance_history(self, employee_id: Any = None, days: int = 30) -> list[dict[str, Any]]:
        """Load clock-in history from Backend (Mongo). Default last 30 days."""
        days = max(1, min(int(days or 30), 90))
        try:
            data = self._backend.attendance(f"/api/attendance/history?days={days}")
        except Exception as exc:
            print(f"⚠️ attendance history request failed: {exc}")
            return []

        if not isinstance(data, dict):
            return []
        records = data.get("records") or data.get("attendance") or []
        if not isinstance(records, list):
            return []
        out: list[dict[str, Any]] = []
        for row in records:
            normalised = self._normalise_record(row if isinstance(row, dict) else None)
            if normalised:
                out.append(normalised)
        return out

    def get_weekly_timesheet(self, employee_id: Any):
        """Recent Activity list: last 7 days of attendance (not only today)."""
        records = self.get_attendance_history(employee_id, days=7)
        if records:
            return records
        # Fallback: at least show today if history endpoint unavailable
        record = self.get_today_record(employee_id)
        return [record] if record else []

    def get_weekly_total(self, employee_id: Any) -> float:
        now = time.monotonic()
        if now - self._summary_cache[0] < 30.0:
            return self._summary_cache[1]
        records = self.get_attendance_history(employee_id, days=7)
        total = 0.0
        for record in records:
            if record.get("status") == "clocked_out" or record.get("clock_out_at"):
                total += float(record.get("hours_worked") or 0)
            else:
                # Open session today – use live hours
                if str(record.get("work_date") or "") == str(
                    datetime.now(self.LOCAL_ZONE).date()
                ):
                    total += self.get_live_hours(record)
                else:
                    total += float(record.get("hours_worked") or 0)
        # monthly approx: 30-day sum for cache slot 2
        monthly_records = self.get_attendance_history(employee_id, days=30)
        monthly = 0.0
        for record in monthly_records:
            monthly += float(record.get("hours_worked") or 0)
        self._summary_cache = (now, total, monthly)
        return total

    def get_monthly_total(self, employee_id: Any) -> float:
        now = time.monotonic()
        if now - self._summary_cache[0] < 30.0:
            return self._summary_cache[2]
        self.get_weekly_total(employee_id)
        return self._summary_cache[2]

    def is_clocked_in(self, employee_id: Any) -> bool:
        return self.get_timer_status(employee_id).get("status") == "clocked_in"

    def is_on_break(self, employee_id: Any) -> bool:
        return self.get_timer_status(employee_id).get("status") == "on_break"

    def is_clocked_out(self, employee_id: Any) -> bool:
        return self.get_timer_status(employee_id).get("status") == "clocked_out"
