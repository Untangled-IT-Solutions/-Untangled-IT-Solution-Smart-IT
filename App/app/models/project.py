"""Project model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    id: int | None
    name: str
    description: str | None
    status: str
    department: str | None
    progress: int = 0
    members: str = ""
    milestones: str = ""
    timeline: str = ""
    budget_placeholder: str = "Budget pending"
    documents: str = ""
    activity_feed: str = ""
