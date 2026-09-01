# app/controllers/work_controller.py
"""Work controller."""

from app.services.work_service import WorkService
from app.services.people_service import PeopleService
from app.services.mongo_notification_service import MongoNotificationService


class WorkController:
    """Controls work/task operations."""

    PRIORITIES = ["Low", "Medium", "High", "Critical"]
    STATUSES = ["New", "Assigned", "In Progress", "Waiting Review", "Completed", "Cancelled"]
    DEFAULT_STATUS = "New"

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
        return self._service.get_all_work(search, assigned_employee, category,
                                          department, priority, status)

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
            title, description, assigned_employee, department, priority,
            due_date, estimated_hours, category, start_date, checklist,
            comments, attachments
        )

    def update_work(self, task_id: int, **kwargs) -> dict:
        """Update an existing work item."""
        return self._service.update_work(task_id, **kwargs)

    def delete_work(self, task_id: int) -> None:
        """Delete a work item."""
        self._service.delete_work(task_id)

    def get_history(self, task_id: int) -> list:
        """Get history for a work item."""
        return self._service.get_history(task_id)

    def checklist_text(self, task) -> str:
        """Get checklist as text."""
        return self._service.checklist_text(task)