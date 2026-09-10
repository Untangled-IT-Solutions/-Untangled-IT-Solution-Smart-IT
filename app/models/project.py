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
    category: str = "Internal Project"
    client_name: str = ""
    owner: str = ""
    start_date: str = ""
    due_date: str = ""
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
    document_count: int = 0
    latest_update: str = ""


@dataclass(frozen=True)
class ProjectDocument:
    id: int | None
    project_id: int
    name: str
    file_path: str
    document_type: str = "General"
    added_by: str = ""
    added_at: str = ""


@dataclass(frozen=True)
class ProjectUpdate:
    id: int | None
    project_id: int
    update_text: str
    status: str = ""
    progress: int = 0
    added_by: str = ""
    created_at: str = ""
