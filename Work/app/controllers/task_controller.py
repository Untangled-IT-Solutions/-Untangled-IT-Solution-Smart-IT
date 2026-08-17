"""Tasks controller."""

from app.models.task import Task
from app.services.people_service import PeopleService
from app.services.work_service import WorkService


class TaskController:
    """Provides personal and department task views from unified Work records."""

    def __init__(self, work_service: WorkService, people_service: PeopleService) -> None:
        self._work_service = work_service
        self._people_service = people_service

    def get_tasks(self, scope: str = "All") -> list[Task]:
        if scope == "Personal":
            employees = self._people_service.get_employees()
            person = employees[0].full_name if employees else "All"
            return self._work_service.get_all_work(assigned_employee=person)
        if scope == "Department":
            departments = self._people_service.get_departments()
            department = departments[0] if departments else "All"
            return self._work_service.get_all_work(department=department)
        return self._work_service.get_all_work()
