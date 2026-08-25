"""Minimal employee facade for the remote desktop client."""
from __future__ import annotations
from typing import Any
from app.models.employee import Employee
from app.services.backend_api_client import BackendAPIClient

class BackendPeopleService:
    def __init__(self, backend: BackendAPIClient):
        self._backend = backend
        self._employee = None

    def _current(self):
        data = self._backend.me()
        self._employee = data.get("employee") or {}
        return self._employee

    @staticmethod
    def _to_employee(d: dict[str, Any]) -> Employee:
        return Employee(
            id=d.get("employee_id") or d.get("id"),
            employee_number=str(d.get("employee_number") or d.get("employee_id") or ""),
            first_name=str(d.get("first_name") or str(d.get("full_name") or "").split(" ")[0]),
            last_name=str(d.get("last_name") or d.get("surname") or ""),
            full_name=str(d.get("full_name") or ""),
            position=str(d.get("position") or ""),
            department=str(d.get("department") or ""),
            role=str(d.get("role") or "Staff"),
            reports_to=str(d.get("reports_to") or ""), mentor=str(d.get("mentor") or ""),
            email=str(d.get("email") or ""), phone=str(d.get("phone") or ""),
            status=str(d.get("status") or "Active"), employment_type=str(d.get("employment_type") or ""),
            date_joined=str(d.get("date_joined") or ""), clocked_in=False, current_task="",
            profile_photo=str(d.get("profile_photo") or ""), skills=str(d.get("skills") or ""),
            permissions=str(d.get("permissions") or ""), performance_score=float(d.get("performance_score") or 0),
            training_progress=float(d.get("training_progress") or 0), notes=str(d.get("notes") or ""),
        )

    def current_employee(self):
        d = self._current()
        return self._to_employee(d) if d else None

    def get_employee(self, employee_id):
        d = self._current()
        if not d: return None
        return self._to_employee(d)

    def get_employee_by_name(self, full_name):
        d = self._current()
        if d and str(d.get("full_name") or "") == str(full_name or ""):
            return self._to_employee(d)
        return None

    def get_employees(self, search="", department="All", role="All", status="All"):
        d = self._current()
        if not d: return []
        e = self._to_employee(d)
        text = str(search or "").lower()
        if text and text not in e.full_name.lower() and text not in e.email.lower(): return []
        if department != "All" and e.department != department: return []
        if role != "All" and e.role != role: return []
        if status != "All" and e.status.lower() != str(status).lower(): return []
        return [e]

    def get_departments(self):
        e = self.current_employee(); return [e.department] if e and e.department else []
    def get_roles(self):
        e = self.current_employee(); return [e.role] if e and e.role else []
    def get_statuses(self):
        e = self.current_employee(); return [e.status] if e and e.status else []
    def get_employee_names(self):
        e = self.current_employee(); return [e.full_name] if e else []
    def get_current_tasks(self, employee_name=None): return []
