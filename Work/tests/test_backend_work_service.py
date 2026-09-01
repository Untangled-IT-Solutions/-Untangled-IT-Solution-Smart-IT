"""BackendWorkService contract tests."""

from app.models.task import Task
from app.services.backend_work_service import BackendWorkService


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []
        self.task = {
            "id": "task-1",
            "task_number": "TASK-00001",
            "title": "Review supplier registration",
            "description": "Check documents and assign next step.",
            "assigned_employee": "",
            "assigned_by": "",
            "priority": "High",
            "status": "Dumped",
            "department": "Operations",
            "due_date": "2026-08-28",
            "estimated_hours": 2,
            "category": "Supplier Registration",
            "history": [{"action": "dumped", "by": "Business Lead"}],
        }

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.startswith("/api/work/tasks?"):
            return {"success": True, "tasks": [self.task]}
        if method == "POST" and path == "/api/work/tasks":
            return {"success": True, "task": {**self.task, **(payload or {})}}
        if method == "POST" and path.endswith("/assign"):
            assigned = payload["assigned_employee"]
            return {"success": True, "task": {**self.task, "assigned_employee": assigned, "status": "Assigned"}}
        if method == "GET" and path == "/api/work/decision-queue":
            return {
                "success": True,
                "summary": {
                    "operations_inbox": 1,
                    "waiting_review": 1,
                    "overdue": 0,
                    "my_approvals": 0,
                },
                "queues": {
                    "operations_inbox": [self.task],
                    "waiting_review": [{**self.task, "status": "Waiting Review"}],
                    "overdue": [],
                    "my_approvals": [],
                    "business_approvals": [],
                    "director_approvals": [],
                    "hr_reviews": [],
                },
            }
        if method == "POST" and path.endswith("/decision"):
            status = {
                "approve_review": "Completed",
                "return_to_work": "In Progress",
                "escalate_director": "Waiting Review",
                "cancel": "Cancelled",
            }.get(payload["action"], self.task["status"])
            return {"success": True, "task": {**self.task, "status": status}}
        if method == "POST" and path.endswith("/time"):
            status = {
                "start": "In Progress",
                "pause": "In Progress",
                "log": self.task["status"],
                "submit_review": "Waiting Review",
                "complete": "Completed",
            }.get(payload["action"], self.task["status"])
            return {
                "success": True,
                "task": {
                    **self.task,
                    "status": status,
                    "actual_hours": payload.get("hours", 1.5),
                    "active_timer_started_at": "2026-08-28T08:00:00.000Z" if payload["action"] == "start" else None,
                },
            }
        if method == "PATCH":
            return {"success": True, "task": {**self.task, **(payload or {})}}
        if method == "GET" and path.startswith("/api/work/tasks/task-1"):
            return {"success": True, "task": self.task}
        return {"success": True}


def test_backend_work_service_reads_operations_inbox() -> None:
    backend = FakeBackend()
    service = BackendWorkService(backend)

    tasks = service.get_operations_inbox()

    assert tasks[0].title == "Review supplier registration"
    assert tasks[0].status == "Dumped"
    assert backend.calls[0][1] == "/api/work/tasks?scope=inbox"


def test_backend_work_service_creates_and_assigns_tasks() -> None:
    backend = FakeBackend()
    service = BackendWorkService(backend)

    created = service.create_work(
        Task(
            id=None,
            title="Prepare board pack",
            description="Summarise operational risks.",
            assigned_employee="",
            assigned_by="Business Lead",
            priority="Critical",
            status="Dumped",
            department="Executive",
            created_date=None,
            start_date="",
            due_date="2026-08-29",
            estimated_hours=3,
            category="Administration",
        )
    )
    service.assign_work("task-1", "Ubuntu Hadebe")

    assert created.title == "Prepare board pack"
    assert backend.calls[0][0] == "POST"
    assert backend.calls[1] == (
        "POST",
        "/api/work/tasks/task-1/assign",
        {"assigned_employee": "Ubuntu Hadebe"},
    )


def test_backend_work_service_tracks_task_time() -> None:
    backend = FakeBackend()
    service = BackendWorkService(backend)

    started = service.start_work("task-1")
    logged = service.log_time("task-1", 2.25, "Worked on supplier documents.")
    submitted = service.submit_for_review("task-1")

    assert started.status == "In Progress"
    assert started.active_timer_started_at is not None
    assert logged.actual_hours == 2.25
    assert submitted.status == "Waiting Review"
    assert backend.calls[0] == (
        "POST",
        "/api/work/tasks/task-1/time",
        {"action": "start"},
    )
    assert backend.calls[1] == (
        "POST",
        "/api/work/tasks/task-1/time",
        {"action": "log", "hours": 2.25, "note": "Worked on supplier documents."},
    )


def test_backend_work_service_reads_and_updates_decision_queue() -> None:
    backend = FakeBackend()
    service = BackendWorkService(backend)

    queue = service.get_decision_queue()
    approved = service.approve_review("task-1", "Reviewed with client.")
    returned = service.return_to_work("task-1", "Please attach the supplier docs.")
    escalated = service.escalate_to_director("task-1", "Needs executive sign-off.")

    assert queue["summary"]["operations_inbox"] == 1
    assert queue["waiting_review"][0].status == "Waiting Review"
    assert approved.status == "Completed"
    assert returned.status == "In Progress"
    assert escalated.status == "Waiting Review"
    assert backend.calls[0] == ("GET", "/api/work/decision-queue", None)
    assert backend.calls[1] == (
        "POST",
        "/api/work/tasks/task-1/decision",
        {"action": "approve_review", "note": "Reviewed with client."},
    )
