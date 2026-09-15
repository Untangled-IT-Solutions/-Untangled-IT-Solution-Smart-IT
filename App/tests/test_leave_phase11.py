from types import SimpleNamespace

from app.controllers.approval_controller import ApprovalController
from app.models.approval import ApprovalRequest
from app.services.approval_service import ApprovalService


class Backend:
    def __init__(self):
        self.uploads = []
        self.requests = []

    def upload_document(self, path, document_type):
        self.uploads.append((path, document_type))
        return {"document": {"id": f"doc-{len(self.uploads)}"}}

    def request(self, method, path, payload=None):
        self.requests.append((method, path, payload))
        return {"success": True}


def request(stage="Manager", requested_by="Staff Person", status="Pending"):
    return ApprovalRequest(
        id="leave-1", title="Sick leave", request_type="Leave", description="Medical",
        requested_by=requested_by, department="IT", amount=0, status=status,
        current_stage=stage, requires_director=True,
    )


def controller(role, full_name=None):
    account = SimpleNamespace(role=role, full_name=full_name or f"{role} Person")
    return ApprovalController(SimpleNamespace(), SimpleNamespace(), lambda: account)


def test_leave_submission_uploads_real_documents_before_linking_ids():
    backend = Backend()
    service = ApprovalService(backend)
    service.submit_leave(
        "Sick", "2026-10-01", "2026-10-02", "Medical", ["note.pdf", "scan.jpg"], True
    )
    assert backend.uploads == [("note.pdf", "Doctor note"), ("scan.jpg", "Doctor note")]
    method, path, payload = backend.requests[-1]
    assert (method, path) == ("POST", "/api/leave")
    assert payload["document_ids"] == ["doc-1", "doc-2"]
    assert "requested_by" not in payload


def test_review_controls_follow_authenticated_stage_and_prevent_self_review():
    assert controller("Operations Manager").can_review(request("Manager")) is True
    assert controller("Business Lead").can_review(request("Business")) is True
    assert controller("Director").can_review(request("Director")) is True
    assert controller("Director").can_review(request("Manager")) is False
    assert controller("Staff", "Staff Person").can_review(request(requested_by="Staff Person")) is False
    assert controller("Operations Manager").can_review(request(status="Approved")) is False
