"""Approval and Office Request integration tests."""

from app.database.database import Database
from app.models.approval import ApprovalRequest
from app.services.approval_service import ApprovalService
from app.services.office_request_service import OfficeRequestService
from app.services.people_service import PeopleService


def test_approval_chain_and_office_request_link(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    people = PeopleService(database).get_employees()
    approvals = ApprovalService(database)
    request = approvals.create_request(
        ApprovalRequest(
            id=None,
            title="Approve laptop",
            request_type="Equipment",
            description="",
            requested_by=people[2].full_name,
            department="Operations",
            amount=1000,
            status="Pending",
            current_stage="Operations Manager",
            requires_director=True,
        )
    )

    request = approvals.approve(request.id, people[2].full_name, "Operations Manager")
    request = approvals.approve(request.id, people[1].full_name, "Business Lead")
    request = approvals.approve(request.id, people[0].full_name, "Director")

    assert request.status == "Approved"

    office_service = OfficeRequestService(database, approvals)
    office_request = office_service.create_request(
        "Printer Paper", 2, people[2].full_name, "Operations", "", False
    )

    assert office_request.approval_status == "Pending"
    assert office_service.get_requests()[0].approval_id == office_request.approval_id
