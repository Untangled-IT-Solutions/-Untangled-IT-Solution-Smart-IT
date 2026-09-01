"""BackendOfficeRequestService contract tests."""

from app.services.backend_office_request_service import BackendOfficeRequestService


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []
        self.office_request = {
            "id": "office-1",
            "item_name": "Printer Paper",
            "quantity": 2,
            "requested_by": "Ubuntu Hadebe",
            "department": "Operations",
            "notes": "RFQ folders are running low.",
            "approval_id": "approval-1",
            "approval_status": "Pending",
            "created_at": "2026-09-01T08:00:00.000Z",
        }

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path == "/api/office-requests/items":
            return {"success": True, "items": ["Printer Paper", "Laptop"]}
        if method == "GET" and path == "/api/employees":
            return {"success": True, "employees": [{"full_name": "Ubuntu Hadebe"}]}
        if method == "GET" and path == "/api/office-requests":
            return {"success": True, "requests": [self.office_request]}
        if method == "POST" and path == "/api/office-requests":
            return {"success": True, "request": {**self.office_request, **(payload or {})}}
        return {"success": True}


def test_backend_office_request_service_reads_reference_data() -> None:
    backend = FakeBackend()
    service = BackendOfficeRequestService(backend)

    assert service.get_items() == ["Printer Paper", "Laptop"]
    assert service.get_people_names() == ["Ubuntu Hadebe"]
    assert backend.calls[0] == ("GET", "/api/office-requests/items", None)
    assert backend.calls[1] == ("GET", "/api/employees", None)


def test_backend_office_request_service_creates_and_reads_requests() -> None:
    backend = FakeBackend()
    service = BackendOfficeRequestService(backend)

    created = service.create_request(
        "Printer Paper",
        "2",
        "Ubuntu Hadebe",
        "Operations",
        "RFQ folders are running low.",
        False,
    )
    requests = service.get_requests()

    assert created.item_name == "Printer Paper"
    assert created.approval_status == "Pending"
    assert requests[0].approval_id == "approval-1"
    assert backend.calls[0] == (
        "POST",
        "/api/office-requests",
        {
            "item_name": "Printer Paper",
            "quantity": 2,
            "requested_by": "Ubuntu Hadebe",
            "department": "Operations",
            "notes": "RFQ folders are running low.",
            "requires_director": False,
        },
    )
