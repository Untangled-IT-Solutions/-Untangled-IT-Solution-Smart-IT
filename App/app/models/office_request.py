"""Office supply request domain model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficeRequest:
    """A consumable or equipment request linked to its approval workflow."""

    id: int | None
    item_name: str
    quantity: int
    requested_by: str
    department: str
    notes: str
    approval_id: int
    approval_status: str
    created_at: str | None = None
