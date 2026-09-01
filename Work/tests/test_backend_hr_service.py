"""BackendHRService contract tests."""

from app.services.backend_hr_service import BackendHRService


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []
        self.row = {
            "id": "hr-1",
            "title": "Sick Leave: Ubuntu Hadebe",
            "request_type": "Sick Leave",
            "employee_name": "Ubuntu Hadebe",
            "department": "Operations",
            "start_date": "2026-08-28",
            "end_date": "2026-08-29",
            "reason": "Booked off by doctor.",
            "status": "Pending",
            "current_stage": "Operations Manager",
            "sick_note": {
                "file_name": "note.pdf",
                "status": "Pending Evaluation",
            },
        }

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET":
            return {"success": True, "requests": [self.row]}
        if method == "POST":
            return {"success": True, "request": {**self.row, **(payload or {})}}
        if method == "PATCH":
            return {"success": True, "request": {**self.row, "status": payload["status"]}}
        return {"success": True}


def test_backend_hr_service_reads_requests_as_approvals() -> None:
    backend = FakeBackend()
    service = BackendHRService(backend)

    requests = service.get_requests()

    assert requests[0].id == "hr:hr-1"
    assert requests[0].request_type == "Sick Leave"
    assert "note.pdf" in requests[0].description
    assert backend.calls[0][1] == "/api/hr/leave-requests"


def test_backend_hr_service_creates_and_reviews_request() -> None:
    backend = FakeBackend()
    service = BackendHRService(backend)

    created = service.create_request(
        "Sick Leave",
        "2026-08-28",
        "2026-08-29",
        "Booked off by doctor.",
        "Operations",
        {"file_name": "note.pdf", "file_type": "application/pdf", "file_size": 1234},
    )
    approved = service.approve("hr:hr-1", "Operations Manager")

    assert created.request_type == "Sick Leave"
    assert approved.status == "Approved"
    assert backend.calls[0][0] == "POST"
    assert backend.calls[1] == (
        "PATCH",
        "/api/hr/leave-requests/hr-1",
        {"status": "Approved", "evaluation_notes": ""},
    )
