"""Sprint Planning task submission and assignment tests."""

import pytest

from app.controllers.task_controller import TaskController
from app.database.database import Database
from app.services.people_service import PeopleService
from app.services.work_service import WorkService


class FakeNotifications:
    def __init__(self) -> None:
        self.operational = []
        self.users = []

    def record_activity(self, *values) -> None:
        pass

    def notify_operational(self, *values) -> None:
        self.operational.append(values)

    def notify_user(self, *values) -> None:
        self.users.append(values)


class FakeEmail:
    def __init__(self) -> None:
        self.assignments = []

    def send_task_assignment(self, task) -> bool:
        self.assignments.append(task)
        return True


def _controller(tmp_path):
    database = Database(tmp_path / "nexus.db")
    database.initialize()
    notifications = FakeNotifications()
    email = FakeEmail()
    service = WorkService(database, notifications, email)
    return TaskController(service, PeopleService(database)), notifications, email


def test_director_submits_unassigned_task_then_operations_assigns_it(tmp_path) -> None:
    controller, notifications, email = _controller(tmp_path)
    submitted = controller.create_planning_task(
        {
            "title": "Prepare website migration plan",
            "description": "Review dependencies before the next sprint.",
            "priority": "High",
            "department": "Software Development",
            "category": "Website Merge",
            "sprint_bucket": "Next Sprint",
            "story_points": 8,
        },
        creator_name="Zandile Johanna",
        creator_role="Director",
    )

    assert submitted.status == "Inbox"
    assert submitted.assigned_employee == ""
    assert submitted.assigned_by == "Zandile Johanna"
    assert submitted.sprint_bucket == "Next Sprint"
    assert submitted.story_points == 8
    assert controller.get_tasks(scope="Sprint Planning") == [submitted]
    assert notifications.operational
    assert email.assignments == []

    assigned = controller.update_task(
        submitted.id,
        {"assigned_employee": "Siyanda Nkosi"},
    )

    assert assigned.status == "To Do"
    assert assigned.assigned_employee == "Siyanda Nkosi"
    assert notifications.users[-1][0] == "Siyanda Nkosi"
    assert email.assignments == [assigned]


def test_employee_cannot_submit_management_planning_task(tmp_path) -> None:
    controller, _notifications, _email = _controller(tmp_path)

    with pytest.raises(PermissionError):
        controller.create_planning_task(
            {"title": "Unauthorised planning work"},
            creator_name="Employee",
            creator_role="Staff",
        )


def test_task_roles_match_planning_and_assignment_rights() -> None:
    assert TaskController.can_submit_planning_tasks("Director")
    assert TaskController.can_submit_planning_tasks("Super User")
    assert not TaskController.can_assign_tasks("Director")
    assert TaskController.can_assign_tasks("Operations Manager")
    assert TaskController.can_assign_tasks("Admin")
    assert TaskController.can_assign_tasks("Director", "Zandile Johanna Maredi")
    assert TaskController.can_assign_tasks("Business Lead", "Benny Moremi")


def test_sprint_employee_list_and_bucket_moves(tmp_path) -> None:
    controller, _notifications, _email = _controller(tmp_path)
    assert controller.get_employee_names() == list(TaskController.SPRINT_EMPLOYEES)

    task = controller.create_planning_task(
        {
            "title": "Prepare next sprint",
            "category": "General Operations",
            "sprint_bucket": "Backlog",
            "story_points": 5,
        },
        creator_name="Benny Moremi",
        creator_role="Director",
    )
    moved = controller.move_task_to_sprint(task.id, "Current Sprint")
    assert moved.sprint_bucket == "Current Sprint"
    assert moved.status == "To Do"


def test_my_tasks_includes_assigned_and_created_work_across_categories(tmp_path) -> None:
    controller, _notifications, _email = _controller(tmp_path)
    assigned = controller.create_task(
        {
            "title": "Cross-team website review",
            "assigned_employee": "Nonhlanhla Hlatshwayo",
            "assigned_by": "Ubuntu Hadebe",
            "category": "Website Merge",
        }
    )
    created = controller.create_task(
        {
            "title": "Original self-created work",
            "assigned_employee": "Siyanda Nkosi",
            "assigned_by": "Nonhlanhla Hlatshwayo",
            "category": "Technical Services",
        }
    )

    personal = controller.get_tasks(
        scope="My tasks",
        current_user="Nonhlanhla Hlatshwayo",
        department="General Administration",
    )

    assert {task.id for task in personal} == {assigned.id, created.id}
