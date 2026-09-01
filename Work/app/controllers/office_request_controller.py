# app/controllers/office_request_controller.py
"""Office Request controller."""

from app.services.office_request_service import OfficeRequestService
from app.services.people_service import PeopleService


class OfficeRequestController:
    """Controls office request operations."""

    def __init__(
        self,
        office_request_service: OfficeRequestService,
        people_service: PeopleService,
    ) -> None:
        self._service = office_request_service
        self._people_service = people_service

    def get_requests(self) -> list:
        """Get all office requests."""
        return self._service.get_requests()

    def get_items(self) -> list:
        """Get list of available items."""
        return self._service.get_items()

    def get_people_names(self) -> list:
        """Get list of people names."""
        return self._service.get_people_names()

    def get_departments(self) -> list:
        """Get list of departments."""
        return self._people_service.get_departments()

    def create_request(self, item: str, quantity: str, requested_by: str,
                       department: str, notes: str, requires_director: bool) -> dict:
        """Create a new office request."""
        return self._service.create_request(
            item, quantity, requested_by, department, notes, requires_director
        )