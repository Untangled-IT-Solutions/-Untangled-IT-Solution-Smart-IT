from types import SimpleNamespace

import pytest

from app.controllers.task_controller import TaskController
from app.models.task import Task
from app.views.task_view import available_employee_actions


class Work:
    def __init__(self):
        self.calls = []

    def assign_task(self, *args):
        self.calls.append(("assign", args))

    def approve_review(self, *args):
        self.calls.append(("approve", args))

    def complete_work(self, *args):
        self.calls.append(("complete", args))

    def prioritize_task(self, *args):
        self.calls.append(("prioritize", args))

    def create_task(self, data):
        self.calls.append(("create", data))
        return {"task": {"id": "t1"}}

    def get_decision_queue(self):
        return {"tasks": []}


class People:
    def get_names(self):
        return ["Staff Person"]


def controller(role):
    work = Work()
    account = SimpleNamespace(role=role, full_name=role + " Person")
    return TaskController(work, People(), get_current_account=lambda: account), work


def test_business_lead_can_dump_but_cannot_assign_or_open_operations_queue():
    ctrl, work = controller("Business Lead")
    assert ctrl.can_create_tasks() is True
    assert ctrl.get_people_names() == ["Unassigned"]
    assert ctrl.get_decision_queue() == {}
    ctrl.create_task({"title": "Task dump", "assigned_employee": "Unassigned"})
    with pytest.raises(PermissionError, match="Operations Managers"):
        ctrl.assign_task("t1", "Staff Person")
    assert [call[0] for call in work.calls] == ["create"]


def test_operations_manager_can_assign_and_review():
    ctrl, work = controller("Operations Manager")
    assert ctrl.get_people_names() == ["Unassigned", "Staff Person"]
    ctrl.assign_task("t1", "Staff Person")
    ctrl.approve_review("t1", "Done")
    ctrl.prioritize_task("t1", "Urgent")
    assert [call[0] for call in work.calls] == ["assign", "approve", "prioritize"]


def test_staff_cannot_create_assign_or_review():
    ctrl, _ = controller("Staff")
    assert ctrl.can_create_tasks() is False
    with pytest.raises(PermissionError):
        ctrl.create_task({"title": "No"})
    with pytest.raises(PermissionError):
        ctrl.assign_task("t1", "Staff Person")
    with pytest.raises(PermissionError):
        ctrl.approve_review("t1")
    with pytest.raises(PermissionError):
        ctrl.complete_work("t1")


def test_employee_controls_follow_timer_state_and_never_offer_complete():
    cases = {
        ("Pending", False): (),
        ("Assigned", False): ("Start",),
        ("Returned", False): ("Start",),
        ("In Progress", True): ("Pause", "Submit review"),
        ("Paused", False): ("Resume", "Log time", "Submit review"),
        ("Waiting Review", False): (),
        ("Completed", False): (),
    }
    for (status, active), expected in cases.items():
        task = Task(
            id="t1",
            title="Test",
            status=status,
            active_timer_started_at="2026-09-14T10:00:00Z" if active else None,
        )
        actions = available_employee_actions(task)
        assert actions == expected
        assert "Complete" not in actions
