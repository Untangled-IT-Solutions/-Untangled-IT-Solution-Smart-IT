"""Department model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    id: int | None
    name: str
    description: str | None = None
