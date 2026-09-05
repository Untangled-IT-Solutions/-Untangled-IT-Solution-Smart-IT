"""Attendance – Backend API only."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class AttendanceService:
    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def status(self) -> Dict[str, Any]:
        try:
            return self._backend.attendance_status()
        except BackendAPIError as exc:
            return {"error": str(exc), "state": "unknown"}

    def clock_in(self, employee_id: Optional[int] = None) -> Dict[str, Any]:
        return self._backend.clock_in(employee_id)

    def clock_out(self, employee_id: Optional[int] = None) -> Dict[str, Any]:
        return self._backend.clock_out(employee_id)

    def break_start(self, employee_id: Optional[int] = None) -> Dict[str, Any]:
        return self._backend.break_start(employee_id)

    def break_end(self, employee_id: Optional[int] = None) -> Dict[str, Any]:
        return self._backend.break_end(employee_id)

    # Compatibility helpers used by AttendanceController
    def can_manage_attendance(self) -> bool:
        return True

    def get_today(self, employee_id: Any = None) -> Dict[str, Any]:
        return self.status()

    def get_history(self, employee_id: Any = None, days: int = 30) -> List[dict]:
        try:
            data = self._backend.request("GET", f"/api/attendance/history?days={days}")
            return data.get("records") or data.get("items") or []
        except BackendAPIError:
            return []
