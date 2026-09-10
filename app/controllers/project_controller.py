"""Project workspace controller and permission rules."""

from __future__ import annotations

from app.models.project import Project
from app.services.project_service import ProjectService


class ProjectController:
    """Control project records, files, updates, and management access."""

    CATEGORIES = ("Internal Project", "Client Project", "Upcoming Project")
    STATUSES = ("Planning", "Active", "On Hold", "Completed", "Archived")
    DOCUMENT_TYPES = (
        "General", "Requirements", "Design", "Technical", "Meeting Minutes",
        "Report", "Contract", "Quote", "Other",
    )
    MANAGEMENT_ROLES = {
        "super user", "superuser", "administrator", "admin", "super admin",
    }
    FULL_ACCESS_NAMES = {
        "ubuntu hadebe", "zandile johanna maredi", "zandile maredi",
        "zandil maredi", "benny moremi", "benny",
    }

    def __init__(self, project_service: ProjectService) -> None:
        self._service = project_service

    @classmethod
    def can_manage_projects(cls, role: str = "", full_name: str = "") -> bool:
        return (
            str(role or "").strip().casefold() in cls.MANAGEMENT_ROLES
            or str(full_name or "").strip().casefold() in cls.FULL_ACCESS_NAMES
        )

    def get_projects(self, search: str = "", category: str = "All", status: str = "All") -> list[Project]:
        return self._service.get_projects(search, category, status)

    def get_project(self, project_id: int) -> Project | None:
        return self._service.get_project(project_id)

    def create_project(self, values: dict, actor_name: str, actor_role: str) -> Project:
        self._require_manager(actor_role, actor_name)
        name = str(values.get("name", "")).strip()
        if not name:
            raise ValueError("Project name is required.")
        category = str(values.get("category", "Internal Project")).strip()
        status = str(values.get("status", "Planning")).strip()
        if category not in self.CATEGORIES:
            raise ValueError("Please select a valid project category.")
        if status not in self.STATUSES:
            raise ValueError("Please select a valid project status.")
        return self._service.create_project(Project(
            id=None, name=name,
            description=str(values.get("description", "")).strip(), status=status,
            department=str(values.get("department", "")).strip(),
            progress=self._progress(values.get("progress", 0)),
            members=str(values.get("members", "")).strip(),
            milestones=str(values.get("milestones", "")).strip(),
            timeline=str(values.get("timeline", "")).strip(),
            budget_placeholder=str(values.get("budget_placeholder", "Budget pending")).strip() or "Budget pending",
            category=category, client_name=str(values.get("client_name", "")).strip(),
            owner=str(values.get("owner", "")).strip(),
            start_date=str(values.get("start_date", "")).strip(),
            due_date=str(values.get("due_date", "")).strip(), created_by=actor_name,
        ))

    def update_project(self, project_id: int, values: dict, actor_name: str, actor_role: str) -> Project:
        self._require_manager(actor_role, actor_name)
        existing = self._service.get_project(project_id)
        if existing is None:
            raise ValueError("Project was not found.")
        name = str(values.get("name", existing.name)).strip()
        category = str(values.get("category", existing.category)).strip()
        status = str(values.get("status", existing.status)).strip()
        if not name:
            raise ValueError("Project name is required.")
        if category not in self.CATEGORIES or status not in self.STATUSES:
            raise ValueError("Please select a valid category and status.")
        return self._service.update_project(Project(
            id=existing.id, name=name,
            description=str(values.get("description", existing.description or "")).strip(),
            status=status, department=str(values.get("department", existing.department or "")).strip(),
            progress=self._progress(values.get("progress", existing.progress)),
            members=str(values.get("members", existing.members)).strip(),
            milestones=str(values.get("milestones", existing.milestones)).strip(),
            timeline=str(values.get("timeline", existing.timeline)).strip(),
            budget_placeholder=str(values.get("budget_placeholder", existing.budget_placeholder)).strip() or "Budget pending",
            documents=existing.documents, activity_feed=existing.activity_feed,
            category=category, client_name=str(values.get("client_name", existing.client_name)).strip(),
            owner=str(values.get("owner", existing.owner)).strip(),
            start_date=str(values.get("start_date", existing.start_date)).strip(),
            due_date=str(values.get("due_date", existing.due_date)).strip(),
            created_by=existing.created_by, created_at=existing.created_at,
        ))

    def delete_project(self, project_id: int, actor_name: str, actor_role: str) -> str:
        self._require_manager(actor_role, actor_name)
        return self._service.delete_project(project_id)

    def add_update(self, project_id: int, text: str, status: str, progress: object, actor_name: str, actor_role: str):
        self._require_manager(actor_role, actor_name)
        if status not in self.STATUSES:
            raise ValueError("Please select a valid status.")
        return self._service.add_update(project_id, text, status, self._progress(progress), actor_name)

    def get_updates(self, project_id: int) -> list:
        return self._service.get_updates(project_id)

    def add_document(self, project_id: int, file_path: str, document_type: str, actor_name: str, actor_role: str):
        self._require_manager(actor_role, actor_name)
        doc_type = document_type if document_type in self.DOCUMENT_TYPES else "General"
        return self._service.add_document(project_id, file_path, doc_type, actor_name)

    def get_documents(self, project_id: int) -> list:
        return self._service.get_documents(project_id)

    @classmethod
    def _require_manager(cls, role: str, full_name: str) -> None:
        if not cls.can_manage_projects(role, full_name):
            raise PermissionError("Only a super user can change project records.")

    @staticmethod
    def _progress(value: object) -> int:
        try:
            progress = int(float(str(value).strip()))
        except (TypeError, ValueError):
            raise ValueError("Progress must be a number from 0 to 100.") from None
        if not 0 <= progress <= 100:
            raise ValueError("Progress must be between 0 and 100.")
        return progress
