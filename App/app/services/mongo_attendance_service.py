"""Attendance adapter for the desktop timer – Backend API only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.backend_api_client import BackendAPIClient, BackendAPIError
from app.services.attendance_service import AttendanceService


class MongoAttendanceService:
    """
    Provides the surface the TimerWidget expects while talking only to the Backend API.
    Live elapsed seconds are computed on the client from the last known clock-in time.
    """

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._inner = AttendanceService(backend)
        self._last_state: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Core API used by TimerWidget
    # ------------------------------------------------------------------

    def refresh_state(self, employee_id: Any = None) -> Dict[str, Any]:
        """Fetch authoritative attendance status from the backend."""
        try:
            data = self._backend.attendance_status()
        except BackendAPIError as exc:
            data = {"error": str(exc), "state": "unknown", "status": "clocked_out"}

        # Normalise into the shape TimerWidget understands
        status = (data.get("status") or data.get("state") or "clocked_out").lower()
        state_map = {
            "clocked_in": "working",
            "working": "working",
            "on_break": "on_break",
            "break": "on_break",
            "clocked_out": "not_started",
            "completed": "completed",
        }
        normalised = {
            "state": state_map.get(status, status),
            "status": status,
            "record": data.get("record") or data,
            "clock_in_at": data.get("clock_in_at") or data.get("started_at"),
            "break_started_at": data.get("break_started_at"),
            "raw": data,
        }
        self._last_state = normalised
        return normalised

    def get_live_seconds(self, record: Optional[dict] = None) -> int:
        """Compute elapsed working seconds from the last clock-in timestamp."""
        record = record or (self._last_state.get("record") if self._last_state else {}) or {}
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
                start = datetime.fromtimestamp(start_raw, tz=timezone.utc)
            else:
                text = str(start_raw).replace("Z", "+00:00")
                start = datetime.fromisoformat(text)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return max(0, int((now - start).total_seconds()))
        except Exception:
            return int(record.get("elapsed_seconds") or 0)

    def clock_in(self, employee_id: Any = None) -> Dict[str, Any]:
        result = self._inner.clock_in(employee_id)
        return self.refresh_state(employee_id)

    def clock_out(self, employee_id: Any = None) -> Dict[str, Any]:
        result = self._inner.clock_out(employee_id)
        return self.refresh_state(employee_id)

    def start_break(self, employee_id: Any = None) -> Dict[str, Any]:
        self._inner.break_start(employee_id)
        return self.refresh_state(employee_id)

    def end_break(self, employee_id: Any = None) -> Dict[str, Any]:
        self._inner.break_end(employee_id)
        return self.refresh_state(employee_id)

    # Aliases
    def break_start(self, employee_id: Any = None) -> Dict[str, Any]:
        return self.start_break(employee_id)

    def break_end(self, employee_id: Any = None) -> Dict[str, Any]:
        return self.end_break(employee_id)

    def status(self) -> Dict[str, Any]:
        return self.refresh_state()
