# app/controllers/task_controller.py
"""Task controller."""

from app.services.work_service import WorkService
from app.services.people_service import PeopleService


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
        return self._service.create_work(**data)

    def update_task(self, task_id: int, data: dict):
        """Update an existing task."""
        return self._service.update_work(task_id, **data)

    def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        self._service.delete_work(task_id)