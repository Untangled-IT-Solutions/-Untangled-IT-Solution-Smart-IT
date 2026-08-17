"""Calendar controller."""

from app.models.calendar_event import CalendarEvent
from app.services.calendar_service import CalendarService
from app.services.people_service import PeopleService


class CalendarController:
    """Coordinates calendar data and manual event commands."""

    def __init__(self, calendar_service: CalendarService, people_service: PeopleService) -> None:
        self._calendar_service = calendar_service
        self._people_service = people_service

    def get_month_events(self, year: int, month: int) -> list[CalendarEvent]:
        return self._calendar_service.get_month_events(year, month)

    def create_event(
        self,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ) -> CalendarEvent:
        return self._calendar_service.create_event(
            title, event_type, start_date, end_date, department, details, recurrence
        )

    def update_event(
        self,
        event_id: int,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ) -> CalendarEvent:
        return self._calendar_service.update_event(
            event_id, title, event_type, start_date, end_date, department, details, recurrence
        )

    def delete_event(self, event_id: int) -> None:
        self._calendar_service.delete_event(event_id)

    def get_event_types(self) -> list[str]:
        return list(self._calendar_service.EVENT_TYPES)

    def get_recurrence_options(self) -> list[str]:
        return list(self._calendar_service.RECURRENCE_OPTIONS)

    def get_departments(self) -> list[str]:
        return self._people_service.get_departments()
