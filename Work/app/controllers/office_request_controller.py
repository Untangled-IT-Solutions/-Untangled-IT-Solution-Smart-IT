"""Office request controller."""

from app.models.office_request import OfficeRequest
from app.services.office_request_service import OfficeRequestService
from app.services.people_service import PeopleService


class OfficeRequestController:
    """Adapts office request forms to the standard approval-backed service."""

    def __init__(self, office_service: OfficeRequestService, people_service: PeopleService) -> None:
        self._office_service = office_service
        self._people_service = people_service

    def create_request(
        self, item_name: str, quantity: str, requested_by: str, department: str,
        notes: str, requires_director: bool
    ) -> OfficeRequest:
        try:
            parsed_quantity = int(quantity)
        except ValueError as error:
            raise ValueError("Quantity must be a whole number.") from error
        return self._office_service.create_request(
            item_name, parsed_quantity, requested_by, department, notes, requires_director
        )

    def get_requests(self) -> list[OfficeRequest]:
        return self._office_service.get_requests()

    def get_items(self) -> list[str]:
        return list(self._office_service.ITEMS)

    def get_people_names(self) -> list[str]:
        return self._people_service.get_employee_names()

    def get_departments(self) -> list[str]:
        return self._people_service.get_departments()
