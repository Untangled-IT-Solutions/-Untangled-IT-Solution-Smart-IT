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
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    attendees: str = ""
    agenda: str = ""
    minutes: str = ""
    summary: str = ""
    decisions: str = ""
    action_items: str = ""
    # -1 means no reminder; otherwise this is minutes before the event starts.
    reminder_minutes: int = -1
    created_at: str | None = None
