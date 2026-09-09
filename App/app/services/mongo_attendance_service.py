"""Attendance adapter for the desktop timer – Backend API only (fast path).

Header timer and Attendance view share this service.
- Status is cached briefly so frequent polls do not wait ~1s on Render every tick.
- Live elapsed seconds are computed locally from clock_in_at (no network).
- Cache is cleared on clock-in / clock-out / break so UI stays correct.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from app.services.backend_api_client import BackendAPIClient, BackendAPIError
from app.services.attendance_service import AttendanceService


class MongoAttendanceService:
    """
    Surface expected by TimerWidget / AttendanceView while talking only to the API.
    """

    # How long a successful status payload may be reused (seconds).
    # Long enough to stop spam polling; short enough that multi-device stays sane.
    STATUS_CACHE_TTL = 12.0

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._inner = AttendanceService(backend)
        self._last_state: Dict[str, Any] = {}
        self._status_fetched_at: float = 0.0
        self._status_in_flight: bool = False

    # ------------------------------------------------------------------
    # Core API used by TimerWidget + AttendanceView
    # ------------------------------------------------------------------

    def refresh_state(self, employee_id: Any = None, *, force: bool = False) -> Dict[str, Any]:
        """Fetch attendance status. Uses a short TTL cache unless force=True."""
        now = time.monotonic()
        if (
            not force
            and self._last_state
            and (now - self._status_fetched_at) < self.STATUS_CACHE_TTL
            and self._last_state.get("status") not in (None, "unknown")
        ):
            return self._last_state

        try:
            data = self._backend.attendance_status()
        except BackendAPIError as exc:
            # Keep previous good state on transient failure
            if self._last_state and self._last_state.get("status") not in (None, "unknown"):
                return self._last_state
            data = {
                "error": str(exc),
                "state": "unknown",
                "status": "clocked_out",
                "record": None,
            }

        if not isinstance(data, dict):
            data = {}

        record = data.get("record")
        if not isinstance(record, dict):
            record = data.get("attendance") if isinstance(data.get("attendance"), dict) else {}
            if not isinstance(record, dict):
                record = {}
            for key in (
                "clock_in_at", "clock_out_at", "started_at", "start_time",
                "break_started_at", "break_duration_minutes", "hours_worked",
                "work_date", "employee_id", "employee_name", "status", "state",
                "elapsed_seconds", "seconds",
            ):
                if key in data and data[key] is not None and key not in record:
                    record[key] = data[key]

        raw_status = (
            data.get("status")
            or data.get("state")
            or record.get("status")
            or record.get("state")
            or ""
        )
        status = str(raw_status).strip().lower().replace(" ", "_").replace("-", "_")

        has_in = bool(record.get("clock_in_at") or record.get("started_at") or record.get("start_time"))
        has_out = bool(record.get("clock_out_at") or record.get("ended_at"))
        on_break = bool(record.get("break_started_at")) and not has_out

        # Prefer explicit clocked_in flag from API when present
        if data.get("clocked_in") is True and not has_out:
            status = "on_break" if data.get("on_break") or on_break else "clocked_in"
        elif status in ("clocked_in", "working", "in", "active", "checked_in"):
            status = "clocked_in"
        elif status in ("on_break", "break", "paused"):
            status = "on_break"
        elif status in ("clocked_out", "completed", "out", "checked_out", "done"):
            status = "clocked_out"
        elif has_in and not has_out:
            status = "on_break" if on_break else "clocked_in"
        elif has_in and has_out:
            status = "clocked_out"
        else:
            status = "not_started"

        state_map = {
            "clocked_in": "working",
            "working": "working",
            "on_break": "on_break",
            "clocked_out": "completed",
            "completed": "completed",
            "not_started": "not_started",
        }
        state = state_map.get(status, "not_started")

        if not record.get("clock_in_at"):
            for alt in ("started_at", "start_time", "clockInAt", "clock_in"):
                if record.get(alt):
                    record["clock_in_at"] = record[alt]
                    break
            if not record.get("clock_in_at") and data.get("clock_in_at"):
                record["clock_in_at"] = data["clock_in_at"]

        break_minutes = int(
            data.get("break_minutes")
            or data.get("break_duration_minutes")
            or record.get("break_duration_minutes")
            or 0
        )

        normalised = {
            "state": state,
            "status": status,
            "record": record if record else None,
            "clock_in_at": record.get("clock_in_at"),
            "break_started_at": record.get("break_started_at"),
            "break_minutes": break_minutes,
            "clocked_in": status in ("clocked_in", "on_break", "working"),
            "on_break": status == "on_break",
            "raw": data,
        }
        self._last_state = normalised
        self._status_fetched_at = time.monotonic()
        return normalised

    def invalidate_cache(self) -> None:
        self._status_fetched_at = 0.0

    def get_live_seconds(self, record: Optional[dict] = None) -> int:
        """Local elapsed seconds from last clock-in – no network."""
        record = record or (self._last_state.get("record") if self._last_state else {}) or {}
        if not isinstance(record, dict):
            record = {}

        start_raw = (
            record.get("clock_in_at")
            or record.get("started_at")
            or record.get("start_time")
            or self._last_state.get("clock_in_at")
        )
        if not start_raw:
            return int(record.get("elapsed_seconds") or record.get("seconds") or 0)

        try:
            if isinstance(start_raw, (int, float)):
                start = datetime.fromtimestamp(float(start_raw), tz=timezone.utc)
            else:
                text = str(start_raw).strip().replace("Z", "+00:00")
                start = datetime.fromisoformat(text)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            elapsed = max(0, int((now - start).total_seconds()))

            break_mins = int(record.get("break_duration_minutes") or 0)
            if break_mins > 0:
                elapsed = max(0, elapsed - break_mins * 60)
            return elapsed
        except Exception:
            return int(record.get("elapsed_seconds") or 0)

    def get_live_hours(self, record: Optional[dict] = None) -> float:
        return self.get_live_seconds(record) / 3600.0

    def clock_in(self, employee_id: Any = None, employee_name: Any = None) -> Dict[str, Any]:
        self._inner.clock_in(employee_id)
        self.invalidate_cache()
        return self.refresh_state(employee_id, force=True)

    def clock_out(self, employee_id: Any = None) -> Dict[str, Any]:
        self._inner.clock_out(employee_id)
        self.invalidate_cache()
        return self.refresh_state(employee_id, force=True)

    def start_break(self, employee_id: Any = None) -> Dict[str, Any]:
        self._inner.break_start(employee_id)
        self.invalidate_cache()
        return self.refresh_state(employee_id, force=True)

    def end_break(self, employee_id: Any = None) -> Dict[str, Any]:
        self._inner.break_end(employee_id)
        self.invalidate_cache()
        return self.refresh_state(employee_id, force=True)

    def break_start(self, employee_id: Any = None) -> Dict[str, Any]:
        return self.start_break(employee_id)

    def break_end(self, employee_id: Any = None) -> Dict[str, Any]:
        return self.end_break(employee_id)

    def status(self) -> Dict[str, Any]:
        return self.refresh_state()

    # ------------------------------------------------------------------
    # Helpers used by AttendanceView
    # ------------------------------------------------------------------

    def format_local_time(self, value: Any) -> str:
        if not value:
            return "—"
        try:
            sa = ZoneInfo("Africa/Johannesburg")
            utc = ZoneInfo("UTC")
            if isinstance(value, datetime):
                dt = value if value.tzinfo else value.replace(tzinfo=utc)
            else:
                text = str(value).strip().replace("Z", "+00:00")
                if "T" in text:
                    dt = datetime.fromisoformat(text)
                else:
                    dt = None
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                        try:
                            dt = datetime.strptime(text[:19], fmt)
                            break
                        except ValueError:
                            pass
                    if dt is None:
                        return str(value)[:16]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=utc)
            local = dt.astimezone(sa)
            return local.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return str(value)[:16]

    def get_weekly_timesheet(self, employee_id: Any = None) -> List[dict]:
        try:
            data = self._backend.request("GET", "/api/attendance/history?days=7")
            items = data.get("records") or data.get("items") or data.get("history") or []
            return [i for i in items if isinstance(i, dict)]
        except BackendAPIError:
            return []

    def get_weekly_total(self, employee_id: Any = None) -> float:
        total = 0.0
        for r in self.get_weekly_timesheet(employee_id):
            try:
                total += float(r.get("hours_worked") or 0)
            except (TypeError, ValueError):
                pass
        return total

    def get_monthly_total(self, employee_id: Any = None) -> float:
        try:
            data = self._backend.request("GET", "/api/attendance/history?days=31")
            items = data.get("records") or data.get("items") or data.get("history") or []
        except BackendAPIError:
            return 0.0
        total = 0.0
        for r in items:
            if not isinstance(r, dict):
                continue
            try:
                total += float(r.get("hours_worked") or 0)
            except (TypeError, ValueError):
                pass
        return total
