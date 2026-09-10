# app/controllers/calendar_controller.py
"""Calendar controller."""

from pathlib import Path

from app.services.calendar_service import CalendarService
from app.services.people_service import PeopleService


class CalendarController:
    """Controls calendar operations."""

    def __init__(
        self,
        calendar_service: CalendarService,
        people_service: PeopleService,
    ) -> None:
        self._service = calendar_service
        self._people_service = people_service

    def get_month_events(self, year: int, month: int) -> list:
        """Get events for a specific month."""
        return self._service.get_month_events(year, month)

    def get_upcoming_events(self, days: int = 7) -> list:
        """Get upcoming events."""
        return self._service.get_upcoming_events(days)

    def create_event(self, title: str, event_type: str, start_date: str, end_date: str,
                     department: str, details: str, recurrence: str = "None", **meeting_details):
        """Create a new event."""
        return self._service.create_event(title, event_type, start_date, end_date,
                                          department, details, recurrence, **meeting_details)

    def update_event(self, event_id: int, title: str, event_type: str, start_date: str,
                     end_date: str, department: str, details: str, recurrence: str = "None",
                     **meeting_details):
        """Update an existing event."""
        return self._service.update_event(event_id, title, event_type, start_date,
                                          end_date, department, details, recurrence,
                                          **meeting_details)

    def send_meeting_invites(self, event_id: int) -> bool:
        return self._service.send_meeting_invites(event_id)

    def send_meeting_summary(self, event_id: int) -> bool:
        return self._service.send_meeting_summary(event_id)

    def send_meeting_report(
        self,
        recipients: str,
        meeting_title: str,
        summary: str,
        report_path: Path,
        event_id: int | None = None,
    ) -> bool:
        return self._service.send_meeting_report(
            recipients, meeting_title, summary, report_path, event_id
        )

    def delete_event(self, event_id: int) -> None:
        """Delete an event."""
        self._service.delete_event(event_id)

    def get_event_types(self) -> list:
        """Get list of event types."""
        return self._service.EVENT_TYPES

    def get_recurrence_options(self) -> list:
        """Get list of recurrence options."""
        return self._service.RECURRENCE_OPTIONS

    def get_departments(self) -> list:
        """Get list of departments."""
        return self._people_service.get_departments()
