"""Task / unified Work model – production."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Task:
    """Represents a unified operational Work / Task record."""

    id: Any
    title: str
    description: str = ""
    assigned_employee: str = ""
    assigned_by: str = ""
    priority: str = "Normal"
    status: str = "Pending"
    department: str = ""
    created_date: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    elapsed_hours: float = 0.0
    category: str = "Administration"
    comments: str = ""
    checklist: str = "[]"
    attachments: str = "[]"
    active_timer_started_at: Optional[str] = None
    director_approval_status: Optional[str] = None
    returned_reason: Optional[str] = None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class WorkHistory:
    """Auditable event against a Work record."""

    id: Any
    task_id: Any
    action: str
    note: str
    created_by: str
    created_at: Optional[str] = None
