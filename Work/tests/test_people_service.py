"""People service tests."""

from app.database.database import Database
from app.services.people_service import PeopleService


def test_people_service_returns_seeded_employees(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    service = PeopleService(database)

    employees = service.get_employees()

    assert len(employees) == 8
    assert employees[0].full_name == "Zandile Johanna Maredi"
    assert "Technical" in service.get_departments()
