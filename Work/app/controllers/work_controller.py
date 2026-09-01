# app/controllers/work_controller.py
"""Work controller."""

from app.services.work_service import WorkService
from app.services.people_service import PeopleService
from app.services.mongo_notification_service import MongoNotificationService
from app.models.task import Task


class WorkController:
    """Controls work/task operations."""

    PRIORITIES = ["Low", "Medium", "High", "Critical"]
    STATUSES = ["Dumped", "Needs Triage", "New", "Assigned", "In Progress", "Waiting Review", "Completed", "Cancelled"]
    DEFAULT_STATUS = "Dumped"

    def __init__(
        self,
        work_service: WorkService,
        people_service: PeopleService,
        notification_service: MongoNotificationService,
    ) -> None:
        self._service = work_service
        self._people_service = people_service
        self._notification_service = notification_service

    def get_employee_names(self) -> list:
        """Get list of employee names."""
        return self._people_service.get_employee_names()

    def get_categories(self) -> list:
        """Get list of categories."""
        return self._service.get_categories()

    def get_departments(self) -> list:
        """Get list of departments."""
        return self._service.get_departments()

    def get_priorities(self) -> list:
        """Get list of priorities."""
        return self.PRIORITIES

    def get_statuses(self) -> list:
        """Get list of statuses."""
        return self.STATUSES

    def get_all_work(self, search: str = "", assigned_employee: str = "All",
                     category: str = "All", department: str = "All",
                     priority: str = "All", status: str = "All") -> list:
        """Get all work items with filters."""
        return self._service.get_all_work(
            search=search,
            assigned_employee=assigned_employee,
            category=category,
            department=department,
            priority=priority,
            status=status,
        )

    def get_work(self, task_id: int):
        """Get a single work item."""
        return self._service.get_work(task_id)

    def create_work(self, title: str, description: str = "", assigned_employee: str = "",
                    department: str = "", priority: str = "Medium", due_date: str = "",
                    estimated_hours: float = 0, category: str = "General",
                    start_date: str = "", checklist: str = "", comments: str = "",
                    attachments: str = "") -> dict:
        """Create a new work item."""
        return self._service.create_work(
            Task(
                id=None,
                title=title,
                description=description,
                assigned_employee=assigned_employee,
                assigned_by="",
                priority=priority,
                status="Assigned" if assigned_employee else self.DEFAULT_STATUS,
                department=department,
                created_date=None,
                start_date=start_date,
                due_date=due_date,
                estimated_hours=estimated_hours,
                category=category,
                comments=comments,
                checklist=checklist or "[]",
                attachments=attachments or "[]",
            )
        )

    def update_work(self, task_id: int, **kwargs) -> dict:
        """Update an existing work item."""
        return self._service.update_work(task_id, **kwargs)

    def assign_work(self, task_id: int, assigned_employee: str) -> None:
        """Assign a task to an employee."""
        self._service.assign_work(task_id, assigned_employee)

    def update_status(self, task_id: int, status: str) -> None:
        """Move a task through the work pipeline."""
        self._service.update_status(task_id, status)

    def start_work(self, task_id: int, note: str = ""):
        """Start tracking work on a task."""
        if hasattr(self._service, "start_work"):
            return self._service.start_work(task_id, note)
        return self._service.update_status(task_id, "In Progress")

    def pause_work(self, task_id: int, note: str = ""):
        """Pause active work tracking."""
        if hasattr(self._service, "pause_work"):
            return self._service.pause_work(task_id, note)
        return None

    def log_time(self, task_id: int, hours: float, note: str = ""):
        """Add manual time to a task."""
        if hasattr(self._service, "log_time"):
            return self._service.log_time(task_id, hours, note)
        return self._service.update_work(task_id, actual_hours=hours)

    def submit_for_review(self, task_id: int, note: str = ""):
        """Submit a task for manager review."""
        if hasattr(self._service, "submit_for_review"):
            return self._service.submit_for_review(task_id, note)
        return self._service.update_status(task_id, "Waiting Review")

    def complete_work(self, task_id: int, note: str = ""):
        """Complete a task after review."""
        if hasattr(self._service, "complete_work"):
            return self._service.complete_work(task_id, note)
        return self._service.update_status(task_id, "Completed")

    def get_workload(self) -> list:
        """Get team workload summary."""
        return self._service.get_workload() if hasattr(self._service, "get_workload") else []

    def delete_work(self, task_id: int) -> None:
        """Delete a work item."""
        self._service.delete_work(task_id)

    def get_history(self, task_id: int) -> list:
        """Get history for a work item."""
        return self._service.get_history(task_id)

    def checklist_text(self, task) -> str:
        """Get checklist as text."""
        return self._service.checklist_text(task)
