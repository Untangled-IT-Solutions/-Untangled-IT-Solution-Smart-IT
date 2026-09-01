"""People service tests for Mongo-sourced users."""

from app.services.people_service import PeopleService


class FakeCursor:
    def __init__(self, documents):
        self._documents = documents

    def sort(self, _fields):
        return self._documents


class FakeCollection:
    def __init__(self, documents):
        self._documents = documents

    def find(self, _query):
        return FakeCursor(self._documents)

    def distinct(self, field):
        return [document.get(field) for document in self._documents]


class FakeMongo:
    db_name = "test"

    def __init__(self, documents):
        self._collection = FakeCollection(documents)

    def get_collection(self, name):
        assert name == "users"
        return self._collection


def test_people_service_returns_mongo_users_as_employees() -> None:
    service = PeopleService(
        FakeMongo(
            [
                {
                    "employee_id": 1,
                    "employee_number": "UTS-001",
                    "first_name": "Zandile Johanna",
                    "last_name": "Maredi",
                    "full_name": "Zandile Johanna Maredi",
                    "position": "Director",
                    "department": "Executive",
                    "role": "Director",
                    "email": "zandile.johanna@untangleditsolutions.co.za",
                    "status": "active",
                },
                {
                    "employee_id": 2,
                    "employee_number": "UTS-002",
                    "first_name": "Gift",
                    "last_name": "Wesi",
                    "full_name": "Gift Wesi",
                    "position": "Senior Technician",
                    "department": "Technical",
                    "role": "Senior Technician",
                    "email": "gift.wesi@untangleditsolutions.co.za",
                    "status": "active",
                },
            ]
        )
    )

    employees = service.get_employees()

    assert len(employees) == 2
    assert employees[0].full_name == "Zandile Johanna Maredi"
    assert "Technical" in service.get_departments()
