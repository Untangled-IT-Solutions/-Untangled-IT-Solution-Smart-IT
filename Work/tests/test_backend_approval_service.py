"""BackendApprovalService contract tests."""

from app.models.approval import ApprovalRequest
from app.services.backend_approval_service import BackendApprovalService


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []
        self.approval = {
            "id": "approval-1",
            "title": "Approve board pack",
            "request_type": "Budget",
            "description": "Director sign-off needed.",
            "requested_by": "Ubuntu Hadebe",
            "department": "Operations",
            "amount": 1000,
            "status": "Pending",
            "current_stage": "Operations Manager",
            "requires_director": True,
            "submitted_at": "2026-09-01T08:00:00.000Z",
            "updated_at": "2026-09-01T08:00:00.000Z",
        }

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "POST" and path == "/api/approvals":
            return {"success": True, "approval": {**self.approval, **(payload or {})}}
        if method == "GET" and path.startswith("/api/approvals?"):
            return {"success": True, "approvals": [self.approval]}
        if method == "GET" and path == "/api/approvals/approval-1":
            return {"success": True, "approval": self.approval}
        if method == "PATCH" and path == "/api/approvals/approval-1":
            status = "Rejected" if payload["decision"] == "reject" else "Pending"
            return {"success": True, "approval": {**self.approval, "status": status}}
        return {"success": True}


def test_backend_approval_service_creates_and_reads_approvals() -> None:
    backend = FakeBackend()
    service = BackendApprovalService(backend)

    created = service.create_request(
        ApprovalRequest(
            id=None,
            title="Approve board pack",
            request_type="Budget",
            description="Director sign-off needed.",
            requested_by="Ubuntu Hadebe",
            department="Operations",
            amount=1000,
            status="Pending",
            current_stage="Operations Manager",
            requires_director=True,
        )
    )
    approvals = service.get_approvals("Pending")
    approval = service.get_approval("approval-1")

    assert created.title == "Approve board pack"
    assert approvals[0].current_stage == "Operations Manager"
    assert approval is not None
    assert approval.id == "approval-1"
    assert backend.calls[0][0] == "POST"
    assert backend.calls[1] == ("GET", "/api/approvals?status=Pending", None)


def test_backend_approval_service_reviews_approvals() -> None:
    backend = FakeBackend()
    service = BackendApprovalService(backend)

    approved = service.approve("approval-1", "Ubuntu Hadebe", "Operations Manager")
    rejected = service.reject("approval-1", "Ubuntu Hadebe", "Operations Manager", "Budget not ready.")

    assert approved.status == "Pending"
    assert rejected.status == "Rejected"
    assert backend.calls[0] == (
        "PATCH",
        "/api/approvals/approval-1",
        {
            "decision": "approve",
            "reviewer": "Ubuntu Hadebe",
            "stage": "Operations Manager",
            "reason": "",
        },
    )
