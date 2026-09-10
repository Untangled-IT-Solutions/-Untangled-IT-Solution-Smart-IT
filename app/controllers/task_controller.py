# app/controllers/task_controller.py
"""Task controller."""

from dataclasses import replace
from typing import TYPE_CHECKING

from app.models.task import Task
from app.services.work_service import WorkService

if TYPE_CHECKING:
    from app.services.people_service import PeopleService


class TaskController:
    """Controls task operations."""

    TASK_ASSIGNMENT_ROLES = {
        "Operations Manager", "Administrator", "Admin", "Super Admin",
    }
    FULL_SPRINT_USERS = {
        "ubuntu hadebe", "zandil maredi", "zandile maredi",
        "zandile johanna maredi", "benny", "benny moremi",
    }
    SPRINT_EMPLOYEES = (
        "Siyanda Nkosi", "Nonhlanhla Hlatshwayo", "Ubuntu Hadebe",
        "Gift Wesi", "Dipuo Tlowana", "Bongiwe Ngobese", "Botshelo Lehasa",
    )
    SPRINT_BUCKETS = ("Current Sprint", "Next Sprint", "Backlog")
    PLANNING_CREATOR_ROLES = {
        "Director", "Branch Manager", "Business Lead", "Super User", "Superuser",
        *TASK_ASSIGNMENT_ROLES,
    }

    WORKFLOW_STATUSES = (
        "Inbox", "To Do", "In Progress", "In Development", "In Review",
        "Completed", "Cancelled", "Archived",
    )

    def __init__(
        self,
        work_service: WorkService,
        people_service: "PeopleService",
    ) -> None:
        self._service = work_service
        self._people_service = people_service

    def get_tasks(
        self,
        scope: str = "All",
        search: str = "",
        category: str = "All",
        current_user: str = "",
        department: str = "",
        workstream: str = "All work",
    ) -> list[Task]:
        """Return tasks for the selected workspace scope and filters."""
        personal_scope = scope in {"Personal", "My tasks"}
        # Personal work includes tasks assigned to the employee and tasks they
        # originally created.  Query broadly first so an assignment made by a
        # super user remains visible even when its category sits outside the
        # employee's usual department.
        assigned_employee = "All"
        selected_department = department if scope == "Department" and department else "All"
        selected_status = "Inbox" if scope in {"Triage Inbox", "Sprint Planning"} else "All"
        selected_category = category
        if category == "All" and workstream in {"Website Merge", "Hardware Refurbishment"}:
            selected_category = workstream
        tasks = self._service.get_all_work(
            search=search,
            assigned_employee=assigned_employee,
            department=selected_department,
            category=selected_category,
            status=selected_status,
        )
        if personal_scope:
            employee_key = str(current_user or "").strip().casefold()
            tasks = [
                task for task in tasks
                if str(task.assigned_employee or "").strip().casefold() == employee_key
                or str(task.assigned_by or "").strip().casefold() == employee_key
            ]
        if workstream == "Service & Operations":
            return [
                task for task in tasks
                if task.category not in {"Website Merge", "Hardware Refurbishment"}
            ]
        return tasks

    def get_task(self, task_id: int):
        """Get a single task."""
        return self._service.get_work(task_id)

    def create_task(self, data: dict) -> Task:
        """Validate and create a task from the admin assignment form."""
        title = str(data.get("title") or "").strip()
        assigned_employee = str(data.get("assigned_employee") or "").strip()
        if not title:
            raise ValueError("Task name is required.")
        if not assigned_employee:
            raise ValueError("Please assign the task to an employee.")

        task = Task(
            id=None,
            title=title,
            description=str(data.get("description") or "").strip(),
            assigned_employee=assigned_employee,
            assigned_by=str(data.get("assigned_by") or "Administrator").strip(),
            priority=str(data.get("priority") or "Medium"),
            status=str(data.get("status") or "To Do"),
            department=str(data.get("department") or "Operations").strip(),
            created_date=None,
            start_date=str(data.get("start_date") or ""),
            due_date=str(data.get("due_date") or "").strip(),
            estimated_hours=float(data.get("estimated_hours") or 0),
            category=str(data.get("category") or "General Operations").strip(),
            hardware_serial=str(data.get("hardware_serial") or "").strip(),
            external_reference=str(data.get("external_reference") or "").strip(),
            sprint_bucket=str(data.get("sprint_bucket") or "Current Sprint"),
            story_points=self._story_points(data.get("story_points")),
        )
        return self._service.create_work(task)

    def create_self_task(self, data: dict, employee_name: str, department: str) -> Task:
        """Create a worker-owned task in Inbox after enforcing department rules."""
        employee_name = str(employee_name or "").strip()
        if not employee_name:
            raise ValueError("A signed-in employee is required.")
        category = str(data.get("category") or "").strip()
        allowed = self.get_self_task_categories(department)
        if category not in allowed:
            raise PermissionError("This task category is not available for your department.")
        payload = dict(data)
        payload.update(
            assigned_employee=employee_name,
            assigned_by=employee_name,
            status="Inbox",
            sprint_bucket="Backlog",
        )
        return self.create_task(payload)

    def create_planning_task(
        self, data: dict, creator_name: str, creator_role: str
    ) -> Task:
        """Submit an unassigned task for Operations Manager sprint planning."""
        if not self.can_submit_planning_tasks(creator_role, creator_name):
            raise PermissionError("Your role cannot submit Sprint Planning tasks.")
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("Task name is required.")
        task = Task(
            id=None,
            title=title,
            description=str(data.get("description") or "").strip(),
            assigned_employee="",
            assigned_by=str(creator_name or creator_role or "Management").strip(),
            priority=str(data.get("priority") or "Medium"),
            status="Inbox",
            department=str(data.get("department") or "Operations").strip(),
            created_date=None,
            start_date=str(data.get("start_date") or ""),
            due_date=str(data.get("due_date") or "").strip(),
            estimated_hours=float(data.get("estimated_hours") or 0),
            category=str(data.get("category") or "General Operations").strip(),
            hardware_serial=str(data.get("hardware_serial") or "").strip(),
            external_reference=str(data.get("external_reference") or "").strip(),
            sprint_bucket=str(data.get("sprint_bucket") or "Backlog"),
            story_points=self._story_points(data.get("story_points")),
        )
        return self._service.create_work(task)

    def update_task(self, task_id: int, data: dict) -> Task:
        """Update the fields exposed by the task quick-edit panel."""
        current = self._service.get_work(task_id)
        if current is None:
            raise ValueError("Task was not found.")
        allowed = {
            "title", "description", "assigned_employee", "priority", "status",
            "department", "due_date", "category", "hardware_serial", "external_reference",
            "sprint_bucket", "story_points",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        if (
            current.status == "Inbox"
            and str(updates.get("assigned_employee") or "").strip()
            and updates.get("status", "Inbox") == "Inbox"
        ):
            updates["status"] = "To Do"
        updated = replace(current, **updates)
        return self._service.update_work(updated)

    @classmethod
    def can_assign_tasks(cls, role: str, employee_name: str = "") -> bool:
        return (
            str(role or "").strip() in cls.TASK_ASSIGNMENT_ROLES
            or str(employee_name or "").strip().casefold() in cls.FULL_SPRINT_USERS
        )

    @classmethod
    def can_submit_planning_tasks(cls, role: str, employee_name: str = "") -> bool:
        return (
            str(role or "").strip() in cls.PLANNING_CREATOR_ROLES
            or str(employee_name or "").strip().casefold() in cls.FULL_SPRINT_USERS
        )

    def move_task_to_sprint(self, task_id: int, bucket: str) -> Task:
        """Move a task between Current Sprint, Next Sprint, and Backlog."""
        if bucket not in self.SPRINT_BUCKETS:
            raise ValueError("Unsupported sprint destination.")
        task = self._service.get_work(task_id)
        if task is None:
            raise ValueError("Task was not found.")
        updates: dict[str, object] = {"sprint_bucket": bucket}
        if bucket == "Current Sprint" and task.status == "Inbox":
            updates["status"] = "To Do"
        return self.update_task(task_id, updates)

    def close_sprint(self) -> int:
        """Archive completed work and promote the planned next sprint."""
        tasks = self._service.get_all_work()
        changed = 0
        for task in tasks:
            if task.sprint_bucket == "Current Sprint":
                if task.status in {"Completed", "Done"}:
                    self.update_task(task.id, {"status": "Archived"})
                else:
                    self.update_task(task.id, {"sprint_bucket": "Next Sprint"})
                changed += 1
            elif task.sprint_bucket == "Next Sprint":
                self.update_task(task.id, {"sprint_bucket": "Current Sprint"})
                changed += 1
        return changed

    def update_status(self, task_id: int, status: str) -> None:
        """Advance a task through the shared four-stage workflow."""
        if status not in self.WORKFLOW_STATUSES:
            raise ValueError("Unsupported task status.")
        self._service.update_status(task_id, status)

    def update_self_task(self, task_id: int, data: dict, employee_name: str) -> Task:
        """Let employees edit only their own non-destructive task fields."""
        task = self._service.get_work(task_id)
        if task is None:
            raise ValueError("Task was not found.")
        if task.assigned_employee.casefold() != str(employee_name or "").strip().casefold():
            raise PermissionError("You can only edit your own tasks.")
        allowed = {
            "title", "description", "priority", "due_date",
            "hardware_serial", "external_reference",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        return self._service.update_work(replace(task, **updates))

    def update_self_status(self, task_id: int, status: str, employee_name: str) -> None:
        """Prevent employees from approving Inbox work or changing other users' tasks."""
        task = self._service.get_work(task_id)
        if task is None:
            raise ValueError("Task was not found.")
        if task.assigned_employee.casefold() != str(employee_name or "").strip().casefold():
            raise PermissionError("You can only update your own tasks.")
        allowed = {"Cancelled", "Archived"} if task.status == "Inbox" else {
            "To Do", "In Progress", "In Development", "In Review", "Completed",
            "Cancelled", "Archived",
        }
        if status not in allowed:
            raise PermissionError("A manager must review this task before work begins.")
        self._service.update_status(task_id, status)

    def delete_task(self, task_id: int) -> None:
        """Delete a task."""
        self._service.delete_work(task_id)

    def get_employee_names(self) -> list[str]:
        """Return employees available for assignment."""
        try:
            available = self._people_service.get_employee_names()
        except Exception:
            available = self._service.get_assigned_employees()
        known = {str(name).strip().casefold(): str(name).strip() for name in available}
        return [known.get(name.casefold(), name) for name in self.SPRINT_EMPLOYEES]

    @staticmethod
    def _story_points(value: object) -> int:
        try:
            points = int(value or 3)
        except (TypeError, ValueError):
            return 3
        return points if points in {1, 2, 3, 5, 8, 13} else 3

    def get_departments(self) -> list[str]:
        """Return departments available for task routing."""
        try:
            departments = self._people_service.get_departments()
        except Exception:
            departments = self._service.get_departments()
        return sorted({str(value) for value in departments if str(value).strip()}, key=str.lower)

    def get_employee_department(self, employee_name: str) -> str:
        """Look up the current user's department for the Department scope."""
        if not employee_name:
            return ""
        try:
            employee = self._people_service.get_employee_by_name(employee_name)
        except Exception:
            return ""
        return str(getattr(employee, "department", "") or "")

    @staticmethod
    def get_self_task_categories(department: str) -> list[str]:
        """Restrict worker-created tasks to the employee's operational area."""
        value = str(department or "").strip().casefold()
        if any(word in value for word in ("software", "web", "developer")):
            return ["Website Merge", "Client Support / Website Requests", "General Operations"]
        if any(word in value for word in ("technical", "hardware", "refurb", "inventory")):
            return ["Hardware Refurbishment", "Technical Services", "General Operations"]
        if "marketing" in value:
            return ["Marketing & Social Media", "General Operations"]
        if "sales" in value:
            return ["Makro / Online Product Sales", "Client Support / Website Requests", "General Operations"]
        if any(word in value for word in ("admin", "human resource")):
            return ["General Administration / Employee Administration", "Office & Kitchen Supplies", "General Operations"]
        if "support" in value:
            return ["Client Support / Website Requests", "Technical Services", "General Operations"]
        if "operation" in value:
            return ["RFQ & Tender Administration", "General Operations"]
        return ["General Operations", "Client Support / Website Requests"]
