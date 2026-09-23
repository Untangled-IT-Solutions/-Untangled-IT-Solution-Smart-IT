"""Unified Work / Tasks – Backend API only."""

from __future__ import annotations

from typing import Any, List, Optional

from app.models.task import Task
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class WorkService:
    """All task/work operations go through the backend."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    @staticmethod
    def _normalize_attachments(value) -> str:
        """Always store attachments as a JSON string for the Task model."""
        import json as _json
        if value is None or value == "":
            return "[]"
        if isinstance(value, list):
            return _json.dumps(value)
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return "[]"
            try:
                parsed = _json.loads(s)
                if isinstance(parsed, list):
                    return _json.dumps(parsed)
            except Exception:
                pass
            return s
        return "[]"

    def _to_task(self, raw: dict) -> Task:
        return Task(
            id=str(raw.get("id") or raw.get("_id") or "") or None,
            title=raw.get("title") or raw.get("name") or "Untitled",
            description=raw.get("description") or "",
            assigned_employee=raw.get("assigned_employee")
            or raw.get("assignee")
            or raw.get("assigned_to")
            or "",
            assigned_by=raw.get("assigned_by") or "",
            priority=raw.get("priority") or "Normal",
            status=raw.get("status") or "Pending",
            department=raw.get("department") or "",
            created_date=raw.get("created_date") or raw.get("created_at"),
            start_date=raw.get("start_date"),
            due_date=raw.get("due_date") or "",
            estimated_hours=float(raw.get("estimated_hours") or 0),
            actual_hours=float(raw.get("actual_hours") or 0),
            elapsed_hours=float(raw.get("elapsed_hours") or raw.get("actual_hours") or 0),
            category=raw.get("category") or "Administration",
            comments=raw.get("comments") or "",
            checklist=raw.get("checklist") or "[]",
            attachments=self._normalize_attachments(raw.get("attachments")),
            active_timer_started_at=raw.get("active_timer_started_at"),
            director_approval_status=raw.get("director_approval_status"),
            returned_reason=raw.get("returned_reason"),
            raw=raw,
        )


    def create_task(self, data: dict) -> dict:
        """Create a task on the backend and optionally assign it."""
        assignee = (data.get("assigned_employee") or data.get("assignee") or "").strip()
        if assignee.lower() == "unassigned":
            assignee = ""
        status = data.get("status") or ("Assigned" if assignee else "Pending")
        payload = {
            "title": (data.get("title") or "").strip(),
            "description": data.get("description") or "",
            "assigned_employee": assignee,
            # Common backend aliases so assignment sticks regardless of schema
            "assignee": assignee,
            "assigned_to": assignee,
            "priority": data.get("priority") or "Normal",
            "status": status,
            "due_date": data.get("due_date") or None,
            "estimated_hours": float(data.get("estimated_hours") or 0),
            "category": data.get("category") or "Administration",
            "attachments": data.get("attachments") or [],
        }
        # Persist both array and string forms for schema flexibility
        atts = payload["attachments"]
        if isinstance(atts, list):
            import json as _json
            payload["attachments"] = atts
            payload["attachments_json"] = _json.dumps(atts)
        if not payload["title"]:
            raise ValueError("Title is required.")
        try:
            result = self._backend.create_task(payload)
        except BackendAPIError as exc:
            # Retry with minimal payload if backend is strict about unknown fields
            minimal = {
                "title": payload["title"],
                "description": payload["description"],
                "assigned_employee": assignee,
                "priority": payload["priority"],
                "status": status,
                "due_date": payload["due_date"],
                "estimated_hours": payload["estimated_hours"],
                "attachments": payload.get("attachments") or [],
            }
            try:
                result = self._backend.create_task(minimal)
            except BackendAPIError:
                raise RuntimeError(
                    f"Could not create task on the server: {exc}"
                ) from exc
        if not isinstance(result, dict):
            result = {"success": True, "task": result}
        task = result.get("task") or result
        task_id = None
        if isinstance(task, dict):
            task_id = task.get("id") or task.get("_id")

        # Ensure attachments survived create (retry via PATCH if stripped)
        atts = data.get("attachments") or []
        if task_id and atts:
            try:
                import json as _json
                self._backend.update_task(
                    task_id,
                    {
                        "title": payload["title"],
                        "attachments": atts,
                        "attachments_json": _json.dumps(atts) if isinstance(atts, list) else str(atts),
                    },
                )
            except Exception as exc:
                print(f"⚠️ Task created but attachment save failed: {exc}")

        if assignee and task_id:
            try:
                self.assign_task(task_id, assignee)
            except Exception as exc:
                print(f"⚠️ Task created but assign patch failed: {exc}")
        return result

    def get_tasks(self, scope: str = "All") -> List[Task]:
        scope_map = {
            "Inbox": "inbox",
            "Reviews": "reviews",
            "Overdue": "overdue",
            "All": "all",
            "Personal": "personal",
            "Department": "department",
        }
        api_scope = scope_map.get(scope, "all")
        try:
            data = self._backend.get_tasks(api_scope)
            items = data.get("tasks") or data.get("items") or data.get("data") or []
            return [self._to_task(item) for item in items]
        except BackendAPIError:
            return []

    def get_task(self, task_id: Any) -> Optional[Task]:
        try:
            data = self._backend.get_task(task_id)
            raw = data.get("task") or data
            return self._to_task(raw)
        except BackendAPIError:
            return None

    def get_workload(self) -> List[dict]:
        try:
            data = self._backend.get_workload()
            return data.get("workload") or data.get("items") or []
        except BackendAPIError:
            return []

    def get_decision_queue(self) -> dict:
        try:
            return self._backend.get_decision_queue()
        except BackendAPIError:
            return {"summary": {}}

    def log_time(self, task_id: Any, hours: float, note: str = "") -> None:
        try:
            self._backend.update_task(task_id, {"hours_logged": hours, "note": note})
        except BackendAPIError:
            self._backend.task_action(task_id, "log-time", note, {"hours": hours})

    def prioritize_task(self, task_id: Any, priority: str) -> None:
        self._backend.update_task(task_id, {"priority": priority})

    def assign_task(self, task_id: Any, assignee: str) -> None:
        assignee = (assignee or "").strip()
        if assignee.lower() == "unassigned":
            assignee = ""
        payload = {
            "assigned_employee": assignee,
            "assignee": assignee,
            "assigned_to": assignee,
            "status": "Assigned" if assignee else "Pending",
        }
        try:
            self._backend.update_task(task_id, payload)
        except BackendAPIError:
            # Some APIs use a dedicated assign action
            try:
                self._backend.task_action(task_id, "assign", assignee)
            except BackendAPIError as exc:
                raise RuntimeError(f"Could not assign task: {exc}") from exc

    def _set_status(self, task_id: Any, status: str, note: str = "", action: str = "") -> None:
        """Prefer PATCH status update; fall back to action endpoint if present.

        Some backends validate title on every write – always include existing title.
        """
        existing = self.get_task(task_id)
        title = (existing.title if existing else "") or ""
        payload: dict = {
            "status": status,
            "title": title,
        }
        if existing:
            if existing.description:
                payload["description"] = existing.description
            if existing.assigned_employee:
                payload["assigned_employee"] = existing.assigned_employee
                payload["assignee"] = existing.assigned_employee
                payload["assigned_to"] = existing.assigned_employee
            if existing.priority:
                payload["priority"] = existing.priority
            if existing.category:
                payload["category"] = existing.category
            if existing.due_date:
                payload["due_date"] = existing.due_date
        if note:
            payload["note"] = note
            payload["comments"] = note
        # Prefer dedicated action route first when provided (no title validation)
        if action:
            try:
                self._backend.task_action(task_id, action, note)
                return
            except BackendAPIError:
                pass
        try:
            self._backend.update_task(task_id, payload)
            return
        except BackendAPIError as exc:
            # Last attempt: minimal status-only with title
            try:
                self._backend.update_task(task_id, {"status": status, "title": title or "Task"})
                return
            except BackendAPIError:
                raise RuntimeError(f"Could not update task status: {exc}") from exc

    def start_work(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "In Progress", note, action="start")

    def pause_work(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Paused", note, action="pause")

    def resume_work(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "In Progress", note, action="resume")

    def submit_for_review(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Waiting Review", note, action="submit-review")

    def complete_work(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Completed", note, action="complete")

    def approve_review(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Completed", note, action="approve-review")

    def return_to_work(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "In Progress", note, action="return")

    def escalate_to_director(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Escalated", note, action="escalate")

    def cancel_task(self, task_id: Any, note: str = "") -> None:
        self._set_status(task_id, "Cancelled", note, action="cancel")

    # Compatibility
    def get_all_work(self) -> List[Task]:
        return self.get_tasks("All")

    def get_personal_work(self) -> List[Task]:
        return self.get_tasks("Personal")

    def get_department_work(self) -> List[Task]:
        return self.get_tasks("Department")

    def get_work(self, task_id: Any) -> Optional[Task]:
        return self.get_task(task_id)
