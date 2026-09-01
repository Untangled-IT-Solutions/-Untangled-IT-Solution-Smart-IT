"""Employee facade for the remote desktop client via Backend API."""
from __future__ import annotations

from typing import Any, List, Optional

from app.models.employee import Employee
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class BackendPeopleService:
    """Reads people data from the backend instead of MongoDB or SQLite."""

    def __init__(self, backend: BackendAPIClient):
        self._backend = backend
        self._cache: Optional[List[dict[str, Any]]] = None
        self._current_employee: Optional[dict[str, Any]] = None

    def _load_employees(self, force: bool = False) -> List[dict[str, Any]]:
        if self._cache is not None and not force:
            return self._cache
        try:
            # Prefer authenticated admin list when logged in; fall back to public list.
            if self._backend.token:
                try:
                    data = self._backend.request("GET", "/api/admin/employees")
                    employees = data.get("employees") or []
                    if employees:
                        self._cache = employees
                        return self._cache
                except BackendAPIError:
                    pass
            data = self._backend.request("GET", "/api/employees")
            self._cache = data.get("employees") or []
        except BackendAPIError as exc:
            print(f"People service: failed to load employees: {exc}")
            self._cache = []
        return self._cache

    def _current(self) -> dict[str, Any]:
        if self._current_employee is not None:
            return self._current_employee
        if not self._backend.token:
            return {}
        try:
            data = self._backend.me()
            self._current_employee = data.get("employee") or {}
        except BackendAPIError as exc:
            print(f"People service: /api/auth/me failed: {exc}")
            self._current_employee = {}
        return self._current_employee

    def invalidate_cache(self) -> None:
        self._cache = None
        self._current_employee = None

    @staticmethod
    def _to_employee(d: dict[str, Any]) -> Employee:
        return Employee(
            id=d.get("employee_id") or d.get("id"),
            employee_number=str(d.get("employee_number") or d.get("employee_id") or d.get("id") or ""),
            first_name=str(d.get("first_name") or str(d.get("full_name") or "").split(" ")[0]),
            last_name=str(d.get("last_name") or d.get("surname") or ""),
            full_name=str(d.get("full_name") or ""),
            position=str(d.get("position") or ""),
            department=str(d.get("department") or ""),
            role=str(d.get("role") or "Staff"),
            reports_to=str(d.get("reports_to") or ""),
            mentor=str(d.get("mentor") or ""),
            email=str(d.get("email") or ""),
            phone=str(d.get("phone") or ""),
            status=str(d.get("status") or "Active"),
            employment_type=str(d.get("employment_type") or ""),
            date_joined=str(d.get("date_joined") or ""),
            clocked_in=bool(d.get("clocked_in") or False),
            current_task=str(d.get("current_task") or ""),
            profile_photo=str(d.get("profile_photo") or ""),
            skills=str(d.get("skills") or ""),
            permissions=str(d.get("permissions") or ""),
            performance_score=float(d.get("performance_score") or 0),
            training_progress=float(d.get("training_progress") or 0),
            notes=str(d.get("notes") or ""),
        )

    def current_employee(self) -> Optional[Employee]:
        d = self._current()
        return self._to_employee(d) if d else None

    def get_employee(self, employee_id: Any) -> Optional[Employee]:
        target = str(employee_id)
        for row in self._load_employees():
            if str(row.get("employee_id") or row.get("id") or "") == target:
                return self._to_employee(row)
        d = self._current()
        if d and str(d.get("employee_id") or d.get("id") or "") == target:
            return self._to_employee(d)
        return None

    def get_employee_by_name(self, full_name: str) -> Optional[Employee]:
        name = str(full_name or "").strip().lower()
        for row in self._load_employees():
            if str(row.get("full_name") or "").strip().lower() == name:
                return self._to_employee(row)
        return None

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> List[Employee]:
        results: List[Employee] = []
        text = str(search or "").lower().strip()
        for row in self._load_employees():
            e = self._to_employee(row)
            if text and text not in e.full_name.lower() and text not in e.email.lower() and text not in e.department.lower():
                continue
            if department != "All" and e.department != department:
                continue
            if role != "All" and e.role != role:
                continue
            if status != "All" and e.status.lower() != str(status).lower():
                continue
            results.append(e)
        return results

    def get_departments(self) -> List[str]:
        return sorted({e.department for e in self.get_employees() if e.department})

    def get_roles(self) -> List[str]:
        return sorted({e.role for e in self.get_employees() if e.role})

    def get_statuses(self) -> List[str]:
        return sorted({e.status for e in self.get_employees() if e.status})

    def get_employee_names(self) -> List[str]:
        return [e.full_name for e in self.get_employees() if e.full_name]

    def get_current_tasks(self, employee_name: Any = None) -> list:
        return []