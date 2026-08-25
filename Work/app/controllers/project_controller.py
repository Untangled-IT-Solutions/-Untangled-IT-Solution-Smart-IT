# app/controllers/project_controller.py
"""Project controller."""

from app.services.project_service import ProjectService


class ProjectController:
    """Controls project operations."""

    def __init__(self, project_service: ProjectService) -> None:
        self._service = project_service

    def get_projects(self) -> list:
        """Get all projects."""
        return self._service.get_projects()

    def get_project(self, project_id: int):
        """Get a single project."""
        return self._service.get_project(project_id)