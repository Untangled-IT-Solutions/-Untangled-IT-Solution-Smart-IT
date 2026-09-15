"""Approval workflow domain model."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalRequest:
    """Represents a request moving through the Untangled approval chain."""

    id: int | None
    title: str
    request_type: str
    description: str
    requested_by: str
    department: str
    amount: float
    status: str
    current_stage: str
    requires_director: bool
    submitted_at: str | None = None
    updated_at: str | None = None
    manager_approved_by: str = ""
    business_approved_by: str = ""
    director_approved_by: str = ""
    rejection_reason: str = ""
    leave_type: str = ""
    start_date: str = ""
    end_date: str = ""
    document_ids: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None
