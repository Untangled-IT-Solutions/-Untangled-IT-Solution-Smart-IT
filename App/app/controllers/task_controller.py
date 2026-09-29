"""Task controller – Backend-only task workflow and role rules."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from app.services.work_service import WorkService
from app.services.people_service import PeopleService
from app.models.task import Task

MANAGER_ROLES = {
    "Director",
    "Business Lead",
    "Operations Manager",
}
OPERATIONS_ROLES = {"Operations Manager", "Super Admin"}
REVIEW_ROLES = OPERATIONS_ROLES | {"Director"}

COMPLETED_STATUSES = {
    "completed", "done", "closed", "cancelled", "canceled",
}


class TaskController:
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

    # ---- role helpers ----
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

    def can_assign_tasks(self) -> bool:
        return self.current_role() in OPERATIONS_ROLES

    def can_review_tasks(self) -> bool:
        return self.current_role() in REVIEW_ROLES

    def is_current_assignee(self, task: Task) -> bool:
        current = self.current_name().strip().casefold()
        assignee = (task.assigned_employee or "").strip().casefold()
        return bool(current and assignee and current == assignee)

    def get_tasks(self, scope: str = "All") -> List[Task]:
        # Employees: only their open assigned tasks (never create queue scopes)
        if not self.is_manager():
            # Backend personal scope = tasks for this user; hide finished ones.
            tasks = self._service.get_tasks("Personal")
            return [
                t for t in tasks
                if (t.status or "").strip().lower() not in COMPLETED_STATUSES
            ]
        return self._service.get_tasks(scope)

    def get_task(self, task_id: Any) -> Task | None:
        return self._service.get_task(task_id)

    def get_workload(self) -> list:
        if not self.is_manager():
            return []
        return self._service.get_workload()

    def get_decision_queue(self) -> dict:
        if not self.can_assign_tasks():
            return {}
        return self._service.get_decision_queue()

    def get_people_names(self) -> List[str]:
        if not self.can_assign_tasks():
            return ["Unassigned"]
        names = self._people_service.get_names() or []
        if "Unassigned" not in names:
            return ["Unassigned"] + list(names)
        return list(names)

    def log_time(self, task_id: Any, hours: float, note: str = "") -> None:
        self._service.log_time(task_id, hours, note)

    def prioritize_task(self, task_id: Any, priority: str) -> None:
        if not self.can_assign_tasks():
            raise PermissionError("Only Operations Managers can prioritise tasks.")
        self._service.prioritize_task(task_id, priority)

    def assign_task(self, task_id: Any, assignee: str) -> None:
        if not self.can_assign_tasks():
            raise PermissionError("Only Operations Managers can assign tasks.")
        self._service.assign_task(task_id, assignee)

    def start_work(self, task_id: Any, note: str = "") -> None:
        self._service.start_work(task_id, note)

    def pause_work(self, task_id: Any, note: str = "") -> None:
        self._service.pause_work(task_id, note)

    def resume_work(self, task_id: Any, note: str = "") -> None:
        self._service.resume_work(task_id, note)

    def submit_for_review(self, task_id: Any, note: str = "") -> None:
        self._service.submit_for_review(task_id, note)

    def complete_work(self, task_id: Any, note: str = "") -> None:
        if not self.can_review_tasks():
            raise PermissionError("Only an Operations Manager or Director can complete reviewed work.")
        self._service.complete_work(task_id, note)

    def approve_review(self, task_id: Any, note: str = "") -> None:
        if not self.can_review_tasks():
            raise PermissionError("Only Operations Managers or Directors can approve reviews.")
        self._service.approve_review(task_id, note)

    def return_to_work(self, task_id: Any, note: str = "") -> None:
        if not self.can_review_tasks():
            raise PermissionError("Only Operations Managers or Directors can return tasks.")
        self._service.return_to_work(task_id, note)

    def escalate_to_director(self, task_id: Any, note: str = "") -> None:
        if not self.can_assign_tasks():
            raise PermissionError("Only Operations Managers can escalate tasks.")
        self._service.escalate_to_director(task_id, note)

    def cancel_task(self, task_id: Any, note: str = "") -> None:
        if not self.can_assign_tasks():
            raise PermissionError("Only Operations Managers can cancel tasks.")
        self._service.cancel_task(task_id, note)

    def create_task(self, data: dict) -> dict:
        if not self.is_manager():
            raise PermissionError("Employees cannot create tasks. Tasks are assigned to you by a manager.")
        # The API owns task notifications so each assignment emits exactly once.
        return self._service.create_task(data)
