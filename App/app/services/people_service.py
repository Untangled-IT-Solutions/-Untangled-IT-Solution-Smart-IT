"""People / Employees – Backend API only with caching."""

from __future__ import annotations

from typing import Any, List, Optional

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class PeopleService:
    """Facade over /api/employees and /api/admin/employees."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._current_employee: Optional[dict[str, Any]] = None

    def get_all(self, force: bool = False) -> List[dict[str, Any]]:
        try:
            return self._backend.get_employees(force=force)
        except BackendAPIError:
            return []

    # ------------------------------------------------------------------
    # Methods expected by PeopleController / AttendanceController
    # ------------------------------------------------------------------

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> List[dict[str, Any]]:
        employees = self.get_all()
        result = []
        search_l = (search or "").strip().lower()
        for emp in employees:
            name = (emp.get("full_name") or emp.get("name") or "").lower()
            dept = (emp.get("department") or "").lower()
            emp_role = (emp.get("role") or "").lower()
            emp_status = (emp.get("status") or "active").lower()

            if search_l and search_l not in name:
                continue
            if department and department != "All" and department.lower() != dept:
                continue
            if role and role != "All" and role.lower() != emp_role:
                continue
            if status and status != "All" and status.lower() != emp_status:
                continue
            result.append(emp)
        return result

    def get_employee(self, employee_id: Any) -> Optional[dict[str, Any]]:
        for emp in self.get_all():
            if str(emp.get("id") or emp.get("_id") or emp.get("employee_id")) == str(employee_id):
                return emp
        return None

    def get_employee_by_name(self, full_name: str) -> Optional[dict[str, Any]]:
        target = (full_name or "").strip().lower()
        for emp in self.get_all():
            name = (emp.get("full_name") or emp.get("name") or "").strip().lower()
            if name == target:
                return emp
        return None

    def get_departments(self) -> List[str]:
        depts = set()
        for emp in self.get_all():
            d = emp.get("department")
            if d:
                depts.add(str(d))
        return sorted(depts)

    def get_roles(self) -> List[str]:
        roles = set()
        for emp in self.get_all():
            r = emp.get("role")
            if r:
                roles.add(str(r))
        return sorted(roles)

    def get_names(self) -> List[str]:
        names = []
        for emp in self.get_all():
            name = (emp.get("full_name") or emp.get("name") or emp.get("display_name") or "").strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def get_employee_names(self) -> List[str]:
        return self.get_names()

    def get_by_id(self, employee_id: Any) -> Optional[dict[str, Any]]:
        return self.get_employee(employee_id)

    def set_current(self, employee: dict[str, Any]) -> None:
        self._current_employee = employee

    def current_employee(self) -> Optional[dict[str, Any]]:
        return self._current_employee

    @property
    def current(self) -> Optional[dict[str, Any]]:
        return self._current_employee
