"""Task controller – Backend only, with assignment notifications and role rules."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from app.services.work_service import WorkService
from app.services.people_service import PeopleService
from app.models.task import Task

MANAGER_ROLES = {
    "Director",
    "Branch Manager",
    "Business Lead",
    "Operations Manager",
}

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
        if not self.is_manager():
            return {}
        return self._service.get_decision_queue()

    def get_people_names(self) -> List[str]:
        names = self._people_service.get_names() or []
        if "Unassigned" not in names:
            return ["Unassigned"] + list(names)
        return list(names)

    def log_time(self, task_id: Any, hours: float, note: str = "") -> None:
        self._service.log_time(task_id, hours, note)

    def assign_task(self, task_id: Any, assignee: str) -> None:
        if not self.is_manager():
            raise PermissionError("Only managers can assign tasks.")
        self._service.assign_task(task_id, assignee)
        self._notify_assignment(assignee=assignee, task_id=task_id, title=None)

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

    def create_task(self, data: dict) -> dict:
        if not self.is_manager():
            raise PermissionError("Employees cannot create tasks. Tasks are assigned to you by a manager.")
        result = self._service.create_task(data)
        assignee = (data.get("assigned_employee") or "").strip()
        if assignee and assignee.lower() != "unassigned":
            title = data.get("title") or ""
            task_id = None
            if isinstance(result, dict):
                task = result.get("task") or result
                if isinstance(task, dict):
                    task_id = task.get("id") or task.get("_id")
            self._notify_assignment(assignee=assignee, task_id=task_id, title=title)
        return result

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
            msg_title = "New task assigned"
            message = f'You were assigned "{title}"' if title else "You have a new task assignment."
            self._notifications.notify_user(
                user_name=assignee,
                title=msg_title,
                message=message,
                category="Task",
                reference_type="task",
                reference_id=str(task_id) if task_id else None,
            )
        except Exception as exc:
            print(f"⚠️ Task assignment notification failed: {exc}")
