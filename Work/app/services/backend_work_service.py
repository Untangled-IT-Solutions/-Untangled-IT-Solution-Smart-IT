"""Backend API work/task service for the Mongo-backed operations spine."""

from __future__ import annotations

from typing import Any

from app.models.task import Task, WorkHistory
from app.services.backend_api_client import BackendAPIClient


class BackendWorkService:
    """Drop-in WorkService replacement backed by the Backend API."""

    WORK_CATEGORIES = (
        "RFQ",
        "Tender",
        "Supplier Registration",
        "Technical",
        "Software",
        "Marketing",
        "Administration",
        "Website",
        "Inventory",
        "Training",
        "HR",
        "Leave",
        "Procurement",
    )

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def create_work(self, task: Task | None = None, **kwargs: Any) -> Task:
        payload = self._payload_from_task(task, kwargs)
        data = self._backend.request("POST", "/api/work/tasks", payload)
        return self._task_from_dict(data.get("task") or {})

    def get_all_work(
        self,
        search: str = "",
        assigned_employee: str = "All",
        department: str = "All",
        priority: str = "All",
        status: str = "All",
        category: str = "All",
    ) -> list[Task]:
        params = {
            "scope": "all",
            "search": search,
            "assigned_employee": assigned_employee,
            "department": department,
            "priority": priority,
            "status": status,
            "category": category,
        }
        query = self._query(params)
        data = self._backend.request("GET", f"/api/work/tasks?{query}")
        tasks = data.get("tasks") or []

        if assigned_employee != "All":
            tasks = [
                task for task in tasks
                if str(task.get("assigned_employee") or "") == assigned_employee
            ]

        return [self._task_from_dict(task) for task in tasks]

    def get_operations_inbox(self) -> list[Task]:
        data = self._backend.request("GET", "/api/work/tasks?scope=inbox")
        return [self._task_from_dict(task) for task in data.get("tasks") or []]

    def get_personal_work(self) -> list[Task]:
        data = self._backend.request("GET", "/api/work/tasks?scope=mine")
        return [self._task_from_dict(task) for task in data.get("tasks") or []]

    def get_department_work(self) -> list[Task]:
        data = self._backend.request("GET", "/api/work/tasks?scope=department")
        return [self._task_from_dict(task) for task in data.get("tasks") or []]

    def get_work(self, task_id: Any) -> Task | None:
        data = self._backend.request("GET", f"/api/work/tasks/{task_id}")
        task = data.get("task")
        return self._task_from_dict(task) if task else None

    def update_work(self, task: Task | Any, **kwargs: Any) -> Task:
        if isinstance(task, Task):
            task_id = task.id
            payload = self._payload_from_task(task, kwargs)
        else:
            task_id = task
            payload = dict(kwargs)

        data = self._backend.request("PATCH", f"/api/work/tasks/{task_id}", payload)
        return self._task_from_dict(data.get("task") or {})

    def update_status(self, task_id: Any, status: str) -> None:
        self._backend.request("PATCH", f"/api/work/tasks/{task_id}", {"status": status})

    def start_work(self, task_id: Any, note: str = "") -> Task:
        return self._time_action(task_id, "start", note=note)

    def pause_work(self, task_id: Any, note: str = "") -> Task:
        return self._time_action(task_id, "pause", note=note)

    def log_time(self, task_id: Any, hours: float, note: str = "") -> Task:
        return self._time_action(task_id, "log", hours=hours, note=note)

    def submit_for_review(self, task_id: Any, note: str = "") -> Task:
        return self._time_action(task_id, "submit_review", note=note)

    def complete_work(self, task_id: Any, note: str = "") -> Task:
        return self._time_action(task_id, "complete", note=note)

    def _time_action(self, task_id: Any, action: str, **payload: Any) -> Task:
        body = {"action": action}
        body.update({key: value for key, value in payload.items() if value not in ("", None)})
        data = self._backend.request("POST", f"/api/work/tasks/{task_id}/time", body)
        return self._task_from_dict(data.get("task") or {})

    def assign_work(self, task_id: Any, assigned_employee: str) -> None:
        self._backend.request(
            "POST",
            f"/api/work/tasks/{task_id}/assign",
            {"assigned_employee": assigned_employee},
        )

    def get_decision_queue(self) -> dict[str, Any]:
        data = self._backend.request("GET", "/api/work/decision-queue")
        queues = data.get("queues") or {}
        return {
            "summary": data.get("summary") or {},
            "operations_inbox": [
                self._task_from_dict(task)
                for task in queues.get("operations_inbox") or []
            ],
            "waiting_review": [
                self._task_from_dict(task)
                for task in queues.get("waiting_review") or []
            ],
            "overdue": [
                self._task_from_dict(task)
                for task in queues.get("overdue") or []
            ],
            "my_approvals": queues.get("my_approvals") or [],
            "business_approvals": queues.get("business_approvals") or [],
            "director_approvals": queues.get("director_approvals") or [],
            "hr_reviews": queues.get("hr_reviews") or [],
        }

    def decide_work(self, task_id: Any, action: str, note: str = "") -> Task:
        payload = {"action": action}
        if note:
            payload["note"] = note
        data = self._backend.request("POST", f"/api/work/tasks/{task_id}/decision", payload)
        return self._task_from_dict(data.get("task") or {})

    def approve_review(self, task_id: Any, note: str = "") -> Task:
        return self.decide_work(task_id, "approve_review", note)

    def return_to_work(self, task_id: Any, note: str = "") -> Task:
        return self.decide_work(task_id, "return_to_work", note)

    def escalate_to_director(self, task_id: Any, note: str = "") -> Task:
        return self.decide_work(task_id, "escalate_director", note)

    def cancel_work(self, task_id: Any, note: str = "") -> Task:
        return self.decide_work(task_id, "cancel", note)

    def delete_work(self, task_id: Any) -> None:
        self._backend.request("DELETE", f"/api/work/tasks/{task_id}")

    def get_workload(self) -> list[dict[str, Any]]:
        data = self._backend.request("GET", "/api/work/workload")
        return data.get("workload") or []

    def get_active_assignments(self) -> list[Task]:
        data = self._backend.request("GET", "/api/work/workload")
        return [self._task_from_dict(task) for task in data.get("active_assignments") or []]

    def get_categories(self) -> list[str]:
        return list(self.WORK_CATEGORIES)

    def get_departments(self) -> list[str]:
        try:
            tasks = self.get_all_work()
        except Exception:
            return []
        return sorted({task.department for task in tasks if task.department})

    def get_assigned_employees(self) -> list[str]:
        try:
            tasks = self.get_all_work()
        except Exception:
            return []
        return sorted({task.assigned_employee for task in tasks if task.assigned_employee})

    def get_history(self, task_id: Any) -> list[WorkHistory]:
        task = self.get_work(task_id)
        if task is None:
            return []
        raw = getattr(task, "_history", [])
        return [
            WorkHistory(
                id=None,
                task_id=task.id,
                action=str(row.get("action") or ""),
                note=str(row.get("note") or ""),
                created_by=str(row.get("by") or ""),
                created_at=str(row.get("at") or ""),
                hours=float(row.get("hours") or 0),
            )
            for row in raw
            if isinstance(row, dict)
        ]

    @staticmethod
    def _query(values: dict[str, Any]) -> str:
        from urllib.parse import urlencode

        return urlencode({
            key: value
            for key, value in values.items()
            if value not in ("", None, "All")
        })

    @staticmethod
    def _payload_from_task(task: Task | None, extras: dict[str, Any]) -> dict[str, Any]:
        if task is None:
            return dict(extras)

        payload = {
            "title": task.title,
            "description": task.description,
            "assigned_employee": task.assigned_employee,
            "assigned_by": task.assigned_by,
            "priority": task.priority,
            "status": task.status,
            "department": task.department,
            "start_date": task.start_date or "",
            "due_date": task.due_date or "",
            "estimated_hours": task.estimated_hours,
            "actual_hours": task.actual_hours,
            "category": task.category,
            "comments": task.comments,
        }
        payload.update(extras)
        return payload

    @staticmethod
    def _task_from_dict(data: dict[str, Any]) -> Task:
        task = Task(
            id=data.get("id") or data.get("_id") or data.get("task_number"),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            assigned_employee=str(data.get("assigned_employee") or ""),
            assigned_by=str(data.get("assigned_by") or data.get("dumped_by") or ""),
            priority=str(data.get("priority") or "Medium"),
            status=str(data.get("status") or "Dumped"),
            department=str(data.get("department") or ""),
            created_date=str(data.get("created_at") or ""),
            start_date=str(data.get("start_date") or ""),
            due_date=str(data.get("due_date") or ""),
            estimated_hours=float(data.get("estimated_hours") or 0),
            category=str(data.get("category") or "Administration"),
            actual_hours=float(data.get("actual_hours") or 0),
            comments=str(data.get("comments") or ""),
            checklist=str(data.get("checklist") or "[]"),
            attachments=str(data.get("attachments") or "[]"),
            active_timer_started_at=str(data.get("active_timer_started_at") or "") or None,
            director_approval_id=data.get("director_approval_id") or None,
            director_approval_status=str(data.get("director_approval_status") or ""),
            returned_reason=str(data.get("returned_reason") or ""),
        )
        object.__setattr__(task, "_history", data.get("history") or [])
        return task
