"""Work service tests."""

from app.database.database import Database
from app.models.task import Task
from app.services.work_service import WorkService


def test_work_service_manages_tasks(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    service = WorkService(database)

    created = service.create_work(
        Task(
            id=None,
            title="Prepare supplier packet",
            description="Collect registration documents.",
            assigned_employee="Ubuntu Hadebe",
            assigned_by="Operations Manager",
            priority="High",
            status="Assigned",
            department="Operations",
            created_date=None,
            start_date=None,
            due_date="2026-08-10",
            estimated_hours=4,
        )
    )

    assert created.id is not None
    assert service.get_all_work()[0].title == "Prepare supplier packet"
    assert service.get_history(created.id)[0].action == "Created"

    service.update_status(created.id, "In Progress")
    service.assign_work(created.id, "Gift Wesi")
    updated = service.get_all_work()[0]

    assert updated.status == "In Progress"
    assert updated.assigned_employee == "Gift Wesi"

    service.delete_work(created.id)

    assert service.get_all_work() == []
