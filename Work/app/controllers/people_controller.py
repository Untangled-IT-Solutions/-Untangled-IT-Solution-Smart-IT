# app/controllers/people_controller.py
"""People controller."""

from app.services.people_service import PeopleService


class PeopleController:
    """Controls people/employee operations."""

    def __init__(self, people_service: PeopleService) -> None:
        self._people_service = people_service

    def get_employees(self, search: str = "", department: str = "All", role: str = "All", status: str = "All") -> list:
        """Get employees with optional filters."""
        return self._people_service.get_employees(search, department, role, status)

    def get_employee(self, employee_id: int):
        """Get a single employee by ID."""
        return self._people_service.get_employee(employee_id)

    def get_employee_by_name(self, full_name: str):
        """Get an employee by name."""
        return self._people_service.get_employee_by_name(full_name)

    def get_departments(self) -> list:
        """Get list of departments."""
        return self._people_service.get_departments()

    def get_roles(self) -> list:
        """Get list of roles."""
        return self._people_service.get_roles()

    def get_statuses(self) -> list:
        """Get list of statuses."""
        return self._people_service.get_statuses()

    def get_employee_names(self) -> list:
        """Get list of employee names."""
        return self._people_service.get_employee_names()

    def get_current_tasks(self, employee_name: str) -> list:
        """Get current tasks for an employee."""
        return self._people_service.get_current_tasks(employee_name)