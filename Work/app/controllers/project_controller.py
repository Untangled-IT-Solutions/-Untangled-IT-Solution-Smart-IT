"""Projects controller."""

from app.models.project import Project
from app.services.project_service import ProjectService


class ProjectController:
    """Provides project module data to the view."""

    def __init__(self, project_service: ProjectService) -> None:
        self._project_service = project_service

    def get_projects(self) -> list[Project]:
        return self._project_service.get_projects()
