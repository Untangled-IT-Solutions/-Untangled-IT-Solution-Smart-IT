"""People controller."""

from __future__ import annotations

from typing import Any, List, Optional

from app.models.employee import Employee
from app.services.people_service import PeopleService


def _to_employee(raw: dict) -> Employee:
    full = raw.get("full_name") or raw.get("name") or ""
    parts = full.split(None, 1)
    first = raw.get("first_name") or (parts[0] if parts else "")
    last = raw.get("last_name") or (parts[1] if len(parts) > 1 else "")
    return Employee(
        id=raw.get("id") or raw.get("_id") or raw.get("employee_id"),
        employee_number=str(raw.get("employee_number") or raw.get("employee_id") or ""),
        first_name=first,
        last_name=last,
        full_name=full or f"{first} {last}".strip(),
        position=raw.get("position") or raw.get("job_title") or "",
        department=raw.get("department") or "",
        role=raw.get("role") or "employee",
        reports_to=raw.get("reports_to") or "",
        mentor=raw.get("mentor") or "",
        email=raw.get("email") or "",
        phone=raw.get("phone") or "",
        status=raw.get("status") or "active",
        employment_type=raw.get("employment_type") or "full_time",
        date_joined=str(raw.get("date_joined") or raw.get("joined_at") or ""),
        clocked_in=bool(raw.get("clocked_in") or False),
        current_task=raw.get("current_task") or "",
        profile_photo=raw.get("profile_photo") or "",
        skills=raw.get("skills") or "[]",
        permissions=raw.get("permissions") or "[]",
        performance_score=float(raw.get("performance_score") or 0),
        training_progress=float(raw.get("training_progress") or 0),
        notes=raw.get("notes") or "",
    )


class PeopleController:
    """Controls people/employee operations."""

    def __init__(self, people_service: PeopleService) -> None:
        self._people_service = people_service

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> List[Employee]:
        rows = self._people_service.get_employees(search, department, role, status)
        return [_to_employee(r) for r in rows]

    def get_employee(self, employee_id: Any) -> Optional[Employee]:
        raw = self._people_service.get_employee(employee_id)
        return _to_employee(raw) if raw else None

    def get_employee_by_name(self, full_name: str) -> Optional[Employee]:
        raw = self._people_service.get_employee_by_name(full_name)
        return _to_employee(raw) if raw else None

    def get_departments(self) -> list:
        return ["All"] + self._people_service.get_departments()

    def get_roles(self) -> list:
        return ["All"] + self._people_service.get_roles()

    def get_statuses(self) -> list:
        return ["All", "active", "inactive", "on_leave"]

    def get_current_tasks(self, employee_name: str = "") -> list:
        """Tasks currently assigned to an employee (best-effort via people data).

        PeopleView calls this for the profile panel. Full task lists live in Tasks;
        return empty when work service is not wired into this controller.
        """
        # Soft dependency: if a work service was attached later, use it
        work = getattr(self, "_work_service", None)
        if work is None:
            return []
        try:
            name = (employee_name or "").strip().lower()
            tasks = work.get_tasks("All") if hasattr(work, "get_tasks") else []
            out = []
            for t in tasks or []:
                assignee = (
                    getattr(t, "assigned_employee", None)
                    or (t.get("assigned_employee") if isinstance(t, dict) else "")
                    or ""
                )
                if name and str(assignee).strip().lower() != name:
                    continue
                status = str(getattr(t, "status", None) or (t.get("status") if isinstance(t, dict) else "") or "").lower()
                if status in ("completed", "cancelled", "canceled", "done", "closed"):
                    continue
                out.append(t)
            return out[:20]
        except Exception:
            return []
