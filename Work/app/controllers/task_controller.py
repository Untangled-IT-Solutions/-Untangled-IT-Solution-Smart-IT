# app/controllers/task_controller.py
"""Task controller."""

from datetime import date

from app.services.work_service import WorkService
from app.services.people_service import PeopleService
from app.models.task import Task


class TaskController:
    """Controls task operations."""

    def __init__(
        self,
        work_service: WorkService,
        people_service: PeopleService,
    ) -> None:
        self._service = work_service
        self._people_service = people_service

    def get_tasks(self, scope: str = "All") -> list:
        """Get tasks based on scope."""
        if scope == "All":
            return self._service.get_all_work()
        elif scope == "Inbox" and hasattr(self._service, "get_operations_inbox"):
            return self._service.get_operations_inbox()
        elif scope == "Reviews":
            return self._service.get_all_work(status="Waiting Review")
        elif scope == "Overdue":
            today = date.today().isoformat()
            return [
                task for task in self._service.get_all_work()
                if task.due_date and task.status not in ("Completed", "Cancelled")
                and task.due_date < today
            ]
        elif scope == "Personal":
            return self._service.get_personal_work()
        elif scope == "Department":
            return self._service.get_department_work()
        return []

    def get_task(self, task_id: int):
        """Get a single task."""
        return self._service.get_work(task_id)

    def create_task(self, data: dict):
        """Create a new task."""
        return self._service.create_work(
            Task(
                id=None,
                title=data.get("title", ""),
                description=data.get("description", ""),
                assigned_employee=data.get("assigned_employee", ""),
                assigned_by=data.get("assigned_by", ""),
                priority=data.get("priority", "Medium"),
                status=data.get("status", "Dumped"),
                department=data.get("department", ""),
                created_date=None,
                start_date=data.get("start_date", ""),
                due_date=data.get("due_date", ""),
                estimated_hours=float(data.get("estimated_hours", 0) or 0),
                category=data.get("category", "Administration"),
                comments=data.get("comments", ""),
            )
        )

    def update_task(self, task_id: int, data: dict):
        """Update an existing task."""
        return self._service.update_work(task_id, **data)

    def start_work(self, task_id: int, note: str = ""):
        """Start tracking work on a task."""
        return self._service.start_work(task_id, note)

    def pause_work(self, task_id: int, note: str = ""):
        """Pause active work tracking."""
        return self._service.pause_work(task_id, note)

    def log_time(self, task_id: int, hours: float, note: str = ""):
        """Add manual time to a task."""
        return self._service.log_time(task_id, hours, note)

    def submit_for_review(self, task_id: int, note: str = ""):
        """Submit a task for manager review."""
        return self._service.submit_for_review(task_id, note)

    def complete_work(self, task_id: int, note: str = ""):
        """Complete a task after review."""
        return self._service.complete_work(task_id, note)

    def assign_task(self, task_id: int, assigned_employee: str) -> None:
        """Assign or reassign a task."""
        self._service.assign_work(task_id, assigned_employee)

    def approve_review(self, task_id: int, note: str = ""):
        """Approve reviewed work."""
        return self._service.approve_review(task_id, note)

    def return_to_work(self, task_id: int, note: str = ""):
        """Return reviewed work for changes."""
        return self._service.return_to_work(task_id, note)

    def escalate_to_director(self, task_id: int, note: str = ""):
        """Send a task to Director approval."""
        return self._service.escalate_to_director(task_id, note)

    def cancel_task(self, task_id: int, note: str = ""):
        """Cancel a task."""
        return self._service.cancel_work(task_id, note)

    def get_decision_queue(self) -> dict:
        """Get action-oriented queues for management users."""
        if hasattr(self._service, "get_decision_queue"):
            return self._service.get_decision_queue()
        return {}

    def get_workload(self) -> list:
        """Get team workload summary."""
        return self._service.get_workload() if hasattr(self._service, "get_workload") else []

    def get_people_names(self) -> list[str]:
        """Get assignable employee names."""
        if hasattr(self._people_service, "get_employee_names"):
            return self._people_service.get_employee_names()
        return [person.full_name for person in self._people_service.get_employees()]

    def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        self._service.delete_work(task_id)
