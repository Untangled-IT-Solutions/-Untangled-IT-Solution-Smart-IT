"""Unified Work controller."""

import json
from datetime import datetime

from app.models.task import Task
from app.models.task import WorkHistory
from app.services.people_service import PeopleService
from app.services.work_service import WorkService


class WorkController:
    """Coordinates Work view actions with the unified Work service."""

    DEFAULT_STATUS = "Assigned"
    STATUSES = ("New", "Assigned", "In Progress", "Waiting Review", "Completed", "Cancelled")
    PRIORITIES = ("Low", "Medium", "High", "Critical")

    def __init__(self, work_service: WorkService, people_service: PeopleService) -> None:
        self._work_service = work_service
        self._people_service = people_service

    def create_work(
        self,
        title: str,
        description: str,
        assigned_employee: str,
        department: str,
        priority: str,
        due_date: str,
        estimated_hours: str,
        category: str = "Administration",
        start_date: str = "",
        checklist: str = "",
        comments: str = "",
        attachments: str = "",
    ) -> Task:
        """Create a unified Work record from form input."""
        task = Task(
            id=None,
            title=title.strip(),
            description=description.strip(),
            assigned_employee=assigned_employee.strip(),
            assigned_by="Operations Manager",
            priority=priority.strip(),
            status=self.DEFAULT_STATUS,
            department=department.strip(),
            created_date=None,
            start_date=start_date.strip(),
            due_date=due_date.strip(),
            estimated_hours=self._parse_hours(estimated_hours, "Estimated Hours"),
            category=category.strip(),
            comments=comments.strip(),
            checklist=self._encode_checklist(checklist),
            attachments=attachments.strip() or "[]",
        )
        self._validate(task)
        return self._work_service.create_work(task)

    def update_work(
        self,
        task_id: int,
        title: str,
        description: str,
        category: str,
        assigned_employee: str,
        department: str,
        priority: str,
        status: str,
        start_date: str,
        due_date: str,
        estimated_hours: str,
        actual_hours: str,
        checklist: str,
        comments: str,
        attachments: str,
    ) -> Task:
        """Save edits to an existing Work record."""
        existing = self._work_service.get_work(task_id)
        if existing is None:
            raise ValueError("Work record was not found.")
        task = Task(
            id=task_id,
            title=title.strip(),
            description=description.strip(),
            assigned_employee=assigned_employee.strip(),
            assigned_by=existing.assigned_by or "Operations Manager",
            priority=priority.strip(),
            status=status.strip(),
            department=department.strip(),
            created_date=existing.created_date,
            start_date=start_date.strip(),
            due_date=due_date.strip(),
            estimated_hours=self._parse_hours(estimated_hours, "Estimated Hours"),
            category=category.strip(),
            actual_hours=self._parse_hours(actual_hours, "Actual Hours"),
            checklist=self._encode_checklist(checklist),
            comments=comments.strip(),
            attachments=attachments.strip() or "[]",
        )
        self._validate(task)
        return self._work_service.update_work(task)

    def get_all_work(
        self,
        search: str = "",
        assigned_employee: str = "All",
        department: str = "All",
        priority: str = "All",
        status: str = "All",
        category: str = "All",
    ) -> list[Task]:
        """Return Work records matching UI filters."""
        return self._work_service.get_all_work(
            search,
            assigned_employee,
            department,
            priority,
            status,
            category,
        )

    def get_work(self, task_id: int) -> Task | None:
        return self._work_service.get_work(task_id)

    def get_history(self, task_id: int) -> list[WorkHistory]:
        return self._work_service.get_history(task_id)

    def update_status(self, task_id: int, status: str) -> None:
        if status not in self.STATUSES:
            raise ValueError("Select a valid Work status.")
        self._work_service.update_status(task_id, status)

    def assign_work(self, task_id: int, assigned_employee: str) -> None:
        if not assigned_employee.strip():
            raise ValueError("Assign Employee is required.")
        self._work_service.assign_work(task_id, assigned_employee.strip())

    def delete_work(self, task_id: int) -> None:
        self._work_service.delete_work(task_id)

    def get_employee_names(self) -> list[str]:
        return self._people_service.get_employee_names()

    def get_departments(self) -> list[str]:
        return ["All", *self._people_service.get_departments()]

    def get_priorities(self) -> list[str]:
        return ["All", *self.PRIORITIES]

    def get_statuses(self) -> list[str]:
        return ["All", *self.STATUSES]

    def get_categories(self) -> list[str]:
        return ["All", *self._work_service.get_categories()]

    @staticmethod
    def checklist_text(task: Task) -> str:
        """Format stored checklist JSON for the editable multiline control."""
        try:
            values = json.loads(task.checklist)
        except json.JSONDecodeError:
            return task.checklist
        return "\n".join(str(value) for value in values)

    def _validate(self, task: Task) -> None:
        if not task.title:
            raise ValueError("Task Name is required.")
        if not task.assigned_employee:
            raise ValueError("Assign Employee is required.")
        if not task.department:
            raise ValueError("Department is required.")
        if task.priority not in self.PRIORITIES:
            raise ValueError("Select a valid priority.")
        if task.status not in self.STATUSES:
            raise ValueError("Select a valid Work status.")
        if task.category not in self._work_service.get_categories():
            raise ValueError("Select a valid Work category.")
        self._validate_date(task.start_date, "Start Date")
        self._validate_date(task.due_date, "Due Date")
        if task.start_date and task.due_date and task.due_date < task.start_date:
            raise ValueError("Due Date cannot be before Start Date.")

    @staticmethod
    def _encode_checklist(value: str) -> str:
        items = [line.strip() for line in value.splitlines() if line.strip()]
        return json.dumps(items)

    @staticmethod
    def _parse_hours(value: str, field_name: str) -> float:
        if not value.strip():
            return 0
        try:
            result = float(value)
        except ValueError as error:
            raise ValueError(f"{field_name} must be a number.") from error
        if result < 0:
            raise ValueError(f"{field_name} cannot be negative.")
        return result

    @staticmethod
    def _validate_date(value: str, label: str) -> None:
        if not value:
            return
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as error:
            raise ValueError(f"{label} must use YYYY-MM-DD.") from error
