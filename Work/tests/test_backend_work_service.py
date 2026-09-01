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
