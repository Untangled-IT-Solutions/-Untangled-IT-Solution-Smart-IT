"""People controller."""

from app.models.employee import Employee
from app.services.people_service import PeopleService
from app.services.work_service import WorkService


class PeopleController:
    """Coordinates employee views with data services."""

    def __init__(self, people_service: PeopleService, work_service: WorkService) -> None:
        self._people_service = people_service
        self._work_service = work_service

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> list[Employee]:
        return self._people_service.get_employees(search, department, role, status)

    def get_employee(self, employee_id: int) -> Employee | None:
        return self._people_service.get_employee(employee_id)

    def get_employee_by_name(self, full_name: str) -> Employee | None:
        return self._people_service.get_employee_by_name(full_name)

    def get_departments(self) -> list[str]:
        return ["All", *self._people_service.get_departments()]

    def get_roles(self) -> list[str]:
        return ["All", *self._people_service.get_roles()]

    def get_statuses(self) -> list[str]:
        return ["All", *self._people_service.get_statuses()]

    def get_employee_names(self) -> list[str]:
        return self._people_service.get_employee_names()

    def get_current_tasks(self, employee_name: str) -> list[str]:
        return [
            task.title
            for task in self._work_service.get_all_work(assigned_employee=employee_name)
            if task.status not in {"Completed", "Cancelled"}
        ]
