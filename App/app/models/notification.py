"""Notification and activity domain models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Notification:
    """A role-targeted operational notification or executive brief."""

    id: int | None
    recipient_role: str
    title: str
    message: str
    category: str
    reference_type: str
    reference_id: int | None
    is_executive: bool
    is_read: bool
    created_at: str | None = None


@dataclass(frozen=True)
class Activity:
    """A concise audit-friendly operational activity item."""

    id: int | None
    category: str
    description: str
    reference_type: str
    reference_id: int | None
    created_at: str | None = None
