"""Task controller – Backend API only (Mongo lives on the server)."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from app.models.task import Task
from app.models.task_catalog import WORKSTREAM_CATEGORIES
from app.services.people_service import PeopleService
from app.services.work_service import WorkService

MANAGER_ROLES = {
    "Director",
    "Business Lead",
    "Operations Manager",
    "Super User",
}

PLANNING_ROLES = MANAGER_ROLES | {"HR", "Marketing", "Developer", "Super User"}

COMPLETED_STATUSES = {
    "completed", "done", "closed", "cancelled", "canceled", "archived",
}

WORKFLOW_STATUSES = [
    "Inbox",
    "To Do",
    "In Progress",
    "In Development",
    "In Review",
    "Completed",
    "Cancelled",
    "Archived",
]

SPRINT_BUCKETS = [
    "Backlog",
    "This Sprint",
    "Next Sprint",
    "Later",
]


class TaskController:
    WORKFLOW_STATUSES = WORKFLOW_STATUSES
    SPRINT_BUCKETS = SPRINT_BUCKETS

    def __init__(
        self,
        work_service: WorkService,
        people_service: PeopleService,
        notification_service: Any = None,
        get_current_account: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._service = work_service
        self._people_service = people_service
        self._notifications = notification_service
        self._get_current_account = get_current_account

    # ---- account helpers ----
    def current_account(self) -> Any:
        if self._get_current_account:
            return self._get_current_account()
        return None

    def current_role(self) -> str:
        acc = self.current_account()
        return (getattr(acc, "role", None) or "Staff") if acc else "Staff"

    def current_name(self) -> str:
        acc = self.current_account()
        if not acc:
            return ""
        return (
            getattr(acc, "full_name", None)
            or getattr(acc, "username", None)
            or getattr(acc, "email", None)
            or ""
        )

    def is_manager(self) -> bool:
        return self.current_role() in MANAGER_ROLES

    def can_create_tasks(self) -> bool:
        return self.is_manager()

    def can_assign_tasks(self, role: str = "", user: str = "") -> bool:
        r = (role or self.current_role() or "").strip()
        return r in MANAGER_ROLES

    def can_submit_planning_tasks(self, role: str = "", user: str = "") -> bool:
        r = (role or self.current_role() or "").strip()
        return r in PLANNING_ROLES or self.can_assign_tasks(r, user)

    # ---- people helpers ----
    def get_people_names(self) -> List[str]:
        try:
            people = self._people_service.get_employees() or []
        except Exception:
            people = []
        names: List[str] = []
        for p in people:
            if hasattr(p, "full_name"):
                n = p.full_name or getattr(p, "name", "") or ""
            elif isinstance(p, dict):
                n = p.get("full_name") or p.get("name") or p.get("username") or ""
            else:
                n = str(p)
            if n:
                names.append(str(n))
        return sorted(set(names), key=str.lower)

    def get_employee_names(self) -> List[str]:
        return self.get_people_names()

    def get_departments(self) -> List[str]:
        try:
            people = self._people_service.get_employees() or []
        except Exception:
            people = []
        depts: List[str] = []
        for p in people:
            if hasattr(p, "department"):
                d = p.department
            elif isinstance(p, dict):
                d = p.get("department")
            else:
                d = None
            if d:
                depts.append(str(d))
        return sorted(set(depts), key=str.lower) or [
            "Operations", "Hardware", "Development", "Administration",
        ]

    def get_employee_department(self, user_name: str) -> str:
        if not user_name:
            return ""
        key = user_name.strip().casefold()
        try:
            people = self._people_service.get_employees() or []
        except Exception:
            return ""
        for p in people:
            if hasattr(p, "full_name"):
                names = [
                    getattr(p, "full_name", "") or "",
                    getattr(p, "name", "") or "",
                    getattr(p, "username", "") or "",
                    getattr(p, "email", "") or "",
                ]
                dept = getattr(p, "department", "") or ""
            elif isinstance(p, dict):
                names = [
                    p.get("full_name") or "",
                    p.get("name") or "",
                    p.get("username") or "",
                    p.get("email") or "",
                ]
                dept = p.get("department") or ""
            else:
                continue
            if any(str(n).strip().casefold() == key for n in names if n):
                return str(dept)
        return ""

    # ---- reads (API) ----
    def get_tasks(
        self,
        scope: str = "All",
        search: str = "",
        category: str = "All",
        current_user: str = "",
        department: str = "",
        workstream: str = "All work",
    ) -> List[Task]:
        """Fetch tasks from Backend API and apply UI filters client-side."""
        # Map UI scope → API scope
        scope_key = (scope or "All").strip()
        if scope_key in {"My tasks", "Personal", "Mine"}:
            api_scope = "Personal"
        elif scope_key in {"Department"}:
            api_scope = "Department"
        else:
            api_scope = "All"

        if not self.is_manager() and not self.can_assign_tasks():
            api_scope = "Personal"

        try:
            tasks = self._service.get_tasks(api_scope) or []
        except Exception as exc:
            print(f"⚠️ get_tasks API failed: {exc}")
            raise

        # Filters
        q = (search or "").strip().casefold()
        cat = (category or "All").strip()
        ws = (workstream or "All work").strip()
        user_key = (current_user or "").strip().casefold()
        dept_key = (department or "").strip().casefold()

        out: List[Task] = []
        for t in tasks:
            if cat and cat != "All" and (t.category or "").strip() != cat:
                continue
            if ws and ws != "All work":
                allowed = WORKSTREAM_CATEGORIES.get(ws) or []
                if allowed and (t.category or "") not in allowed:
                    continue
            if scope_key in {"My tasks", "Personal", "Mine"} and user_key:
                assignee = (t.assigned_employee or "").strip().casefold()
                if assignee != user_key:
                    continue
            if scope_key == "Department" and dept_key:
                if (t.department or "").strip().casefold() != dept_key:
                    continue
            if q:
                blob = " ".join(
                    [
                        str(t.title or ""),
                        str(t.description or ""),
                        str(t.assigned_employee or ""),
                        str(t.category or ""),
                        str(t.department or ""),
                        str(t.status or ""),
                        str(t.id or ""),
                    ]
                ).casefold()
                if q not in blob:
                    continue
            out.append(t)
        return out

    def get_task(self, task_id: Any) -> Task | None:
        return self._service.get_task(task_id)

    def get_workload(self) -> list:
        if not self.is_manager():
            return []
        return self._service.get_workload()

    def get_decision_queue(self) -> dict:
        if not self.is_manager():
            return {}
        return self._service.get_decision_queue()

    # ---- writes (API) ----
    def create_task(self, data: dict) -> dict:
        result = self._service.create_task(data)
        assignee = (data.get("assigned_employee") or "").strip()
        if assignee and assignee.lower() not in {"unassigned", "no employees available"}:
            task_id = None
            if isinstance(result, dict):
                task = result.get("task") or result
                if isinstance(task, dict):
                    task_id = task.get("id") or task.get("_id")
            self._notify_assignment(
                assignee=assignee,
                task_id=task_id,
                title=data.get("title") or "",
            )
        return result

    def create_planning_task(
        self,
        data: dict,
        creator_name: str = "",
        creator_role: str = "",
    ) -> dict:
        payload = dict(data or {})
        payload["status"] = payload.get("status") or "Inbox"
        payload["assigned_employee"] = payload.get("assigned_employee") or ""
        payload["assigned_by"] = creator_name or payload.get("assigned_by") or "Sprint Planning"
        payload.setdefault("sprint_bucket", "Backlog")
        return self.create_task(payload)

    def create_self_task(
        self,
        data: dict,
        employee_name: str = "",
        department: str = "",
    ) -> dict:
        payload = dict(data or {})
        payload["assigned_employee"] = employee_name or payload.get("assigned_employee") or ""
        payload["department"] = department or payload.get("department") or ""
        payload["status"] = payload.get("status") or "To Do"
        payload["assigned_by"] = employee_name or payload.get("assigned_by") or ""
        return self.create_task(payload)

    def update_task(self, task_id: Any, data: dict) -> dict:
        result = self._service.update_task(task_id, data)
        assignee = (data.get("assigned_employee") or "").strip()
        if assignee:
            self._notify_assignment(
                assignee=assignee,
                task_id=task_id,
                title=data.get("title"),
            )
        return result

    def update_self_task(self, task_id: Any, data: dict, employee_name: str) -> dict:
        # Staff can only update limited fields on their own tasks
        allowed = {
            "due_date", "priority", "status", "hardware_serial",
            "external_reference", "description",
        }
        payload = {k: v for k, v in (data or {}).items() if k in allowed}
        return self._service.update_task(task_id, payload)

    def update_self_status(self, task_id: Any, status: str, employee_name: str) -> None:
        self._service.update_task(task_id, {"status": status})

    def delete_task(self, task_id: Any) -> dict:
        return self._service.delete_task(task_id)

    # workflow passthroughs
    def start_work(self, task_id: Any, note: str = "") -> None:
        self._service.start_work(task_id, note)

    def pause_work(self, task_id: Any, note: str = "") -> None:
        self._service.pause_work(task_id, note)

    def submit_for_review(self, task_id: Any, note: str = "") -> None:
        self._service.submit_for_review(task_id, note)

    def complete_work(self, task_id: Any, note: str = "") -> None:
        self._service.complete_work(task_id, note)

    def approve_review(self, task_id: Any, note: str = "") -> None:
        if not self.is_manager():
            raise PermissionError("Only managers can approve reviews.")
        self._service.approve_review(task_id, note)

    def return_to_work(self, task_id: Any, note: str = "") -> None:
        if not self.is_manager():
            raise PermissionError("Only managers can return tasks.")
        self._service.return_to_work(task_id, note)

    def escalate_to_director(self, task_id: Any, note: str = "") -> None:
        if not self.is_manager():
            raise PermissionError("Only managers can escalate tasks.")
        self._service.escalate_to_director(task_id, note)

    def cancel_task(self, task_id: Any, note: str = "") -> None:
        if not self.is_manager():
            raise PermissionError("Only managers can cancel tasks.")
        self._service.cancel_task(task_id, note)

    def _notify_assignment(
        self,
        *,
        assignee: str,
        task_id: Any = None,
        title: Optional[str] = None,
    ) -> None:
        if not self._notifications or not assignee:
            return
        try:
            message = f'You were assigned "{title}"' if title else "You have a new task assignment."
            self._notifications.notify_user(
                user_name=assignee,
                title="New task assigned",
                message=message,
                category="Task",
                reference_type="task",
                reference_id=str(task_id) if task_id else None,
            )
        except Exception as exc:
            print(f"⚠️ Task assignment notification failed: {exc}")


    def update_status(self, task_id, status: str) -> None:
        self._service.update_task(task_id, {"status": status})

    def move_task_to_sprint(self, task_id, bucket: str) -> None:
        self._service.update_task(task_id, {"sprint_bucket": bucket})
