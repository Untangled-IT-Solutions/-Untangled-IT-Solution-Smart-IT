"""Project workspace coverage for defaults, access, files, and updates."""

from pathlib import Path

import pytest

from app.controllers.project_controller import ProjectController
from app.database.database import Database
from app.services.project_service import ProjectService


@pytest.fixture()
def projects(tmp_path: Path) -> ProjectController:
    database = Database(tmp_path / "nexus-projects.db")
    database.initialize()
    return ProjectController(ProjectService(database))


def test_seeds_requested_untangled_projects(projects: ProjectController) -> None:
    assert [project.name for project in projects.get_projects()] == [
        "Untangled Main Website",
        "Untangled Nexus",
    ]


def test_project_management_permissions(projects: ProjectController) -> None:
    assert projects.can_manage_projects("Operations Manager", "Ubuntu Hadebe")
    assert projects.can_manage_projects("Director", "Zandile Johanna Maredi")
    assert projects.can_manage_projects("Director", "Benny Moremi")
    assert not projects.can_manage_projects("Staff", "Siyanda Nkosi")
    with pytest.raises(PermissionError):
        projects.create_project({"name": "Not allowed"}, "Siyanda Nkosi", "Staff")


def test_project_document_update_filter_and_recoverable_delete(
    projects: ProjectController, tmp_path: Path
) -> None:
    project = projects.create_project(
        {
            "name": "Client Portal",
            "category": "Client Project",
            "status": "Planning",
            "progress": 10,
            "client_name": "Example Client",
        },
        "Ubuntu Hadebe",
        "Operations Manager",
    )
    projects.add_update(
        project.id, "Requirements approved.", "Active", 30,
        "Ubuntu Hadebe", "Operations Manager",
    )
    source = tmp_path / "requirements.txt"
    source.write_text("Approved requirements", encoding="utf-8")
    document = projects.add_document(
        project.id, str(source), "Requirements",
        "Ubuntu Hadebe", "Operations Manager",
    )
    assert Path(document.file_path).read_text(encoding="utf-8") == "Approved requirements"
    filtered = projects.get_projects("portal", "Client Project", "Active")
    assert [item.name for item in filtered] == ["Client Portal"]
    assert filtered[0].document_count == 1
    assert filtered[0].latest_update == "Requirements approved."
    recovery_path = projects.delete_project(project.id, "Benny Moremi", "Director")
    assert Path(recovery_path).is_dir()
