"""Backend API calendar service for Mongo-backed operational planning."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.models.calendar_event import CalendarEvent
from app.services.backend_api_client import BackendAPIClient


class BackendCalendarService:
    """Drop-in CalendarService replacement backed by the authenticated API."""

    EVENT_TYPES = (
        "Meeting",
        "Leave",
        "Sick Leave",
        "Birthday",
        "Project",
        "Company Event",
        "Approval Deadline",
        "RFQ Deadline",
        "Supplier Deadline",
        "Technical Visit",
        "Software Milestone",
        "Training",
        "Work Due",
        "HR Deadline",
        "Other",
    )
    RECURRENCE_OPTIONS = ("None", "Daily", "Weekly", "Monthly", "Yearly")

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def get_month_events(self, year: int, month: int) -> list[CalendarEvent]:
        month = max(1, min(12, int(month)))
        year = int(year)
        data = self._backend.request(
            "GET",
            f"/api/calendar/events?year={year}&month={month}",
        )
        return self._events_from_response(data)

    def get_upcoming_events(self, days: int = 7) -> list[CalendarEvent]:
        start = date.today()
        end = start + timedelta(days=max(int(days) - 1, 0))
        data = self._backend.request(
            "GET",
            f"/api/calendar/events?start={start.isoformat()}&end={end.isoformat()}",
        )
        return self._events_from_response(data)

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
        self._validate_event(title, start_date, end_date)
        payload = self._payload(
            title,
            event_type,
            start_date,
            end_date,
            department,
            details,
            recurrence,
        )
        data = self._backend.request("POST", "/api/calendar/events", payload)
        return self._event_from_dict(data.get("event") or {})

    def update_event(
        self,
        event_id: Any,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ) -> CalendarEvent:
        self._validate_event(title, start_date, end_date)
        payload = self._payload(
            title,
            event_type,
            start_date,
            end_date,
            department,
            details,
            recurrence,
        )
        data = self._backend.request("PATCH", f"/api/calendar/events/{event_id}", payload)
        return self._event_from_dict(data.get("event") or {})

    def delete_event(self, event_id: Any) -> None:
        self._backend.request("DELETE", f"/api/calendar/events/{event_id}")

    @classmethod
    def _payload(
        cls,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str,
    ) -> dict[str, Any]:
        event_type = event_type if event_type in cls.EVENT_TYPES else "Other"
        recurrence = recurrence if recurrence in cls.RECURRENCE_OPTIONS else "None"
        return {
            "title": title.strip(),
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date or "",
            "department": department or "",
            "details": details.strip(),
            "recurrence": recurrence,
        }

    @staticmethod
    def _validate_event(title: str, start_date: str, end_date: str) -> None:
        if not title.strip():
            raise ValueError("Event title is required.")
        if not start_date:
            raise ValueError("Start date is required.")
        if end_date and end_date < start_date:
            raise ValueError("End date cannot be before the start date.")

    @classmethod
    def _events_from_response(cls, data: dict[str, Any]) -> list[CalendarEvent]:
        events = data.get("events") if isinstance(data, dict) else []
        return [cls._event_from_dict(event) for event in events or []]

    @staticmethod
    def _event_from_dict(data: dict[str, Any]) -> CalendarEvent:
        return CalendarEvent(
            id=data.get("id") or data.get("_id"),
            title=str(data.get("title") or ""),
            event_type=str(data.get("event_type") or "Other"),
            start_date=str(data.get("start_date") or ""),
            end_date=str(data.get("end_date") or ""),
            department=str(data.get("department") or ""),
            details=str(data.get("details") or ""),
            source_type=str(data.get("source_type") or "Manual"),
            source_id=data.get("source_id"),
            recurrence=str(data.get("recurrence") or "None"),
            created_at=str(data.get("created_at") or "") or None,
        )
