"""Work item model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkItem:
    """Represents an operational work item."""

    id: int | None
    title: str
    description: str
    category: str
    priority: str
    status: str
    assigned_to: str
    department: str
    due_date: str
    created_at: str | None = None
    updated_at: str | None = None
