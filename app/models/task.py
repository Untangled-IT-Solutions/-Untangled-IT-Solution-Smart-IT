"""Task model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    """Represents the unified operational Work record."""

    id: int | None
    title: str
    description: str
    assigned_employee: str
    assigned_by: str
    priority: str
    status: str
    department: str
    created_date: str | None
    start_date: str | None
    due_date: str
    estimated_hours: float
    category: str = "Administration"
    actual_hours: float = 0
    comments: str = ""
    checklist: str = "[]"
    attachments: str = "[]"
    hardware_serial: str = ""
    external_reference: str = ""
    sprint_bucket: str = "Backlog"
    story_points: int = 3


@dataclass(frozen=True)
class WorkHistory:
    """An auditable event recorded against a unified Work record."""

    id: int | None
    task_id: int
    action: str
    note: str
    created_by: str
    created_at: str | None = None
