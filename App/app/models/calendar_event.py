"""Calendar event domain model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CalendarEvent:
    """Represents a scheduled operational event."""

    id: int | None
    title: str
    event_type: str
    start_date: str
    end_date: str
    department: str
    details: str
    source_type: str
    source_id: int | None
    recurrence: str = "None"
    created_at: str | None = None
