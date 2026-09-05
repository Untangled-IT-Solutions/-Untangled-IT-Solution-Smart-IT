"""Calendar – Backend API only."""

from __future__ import annotations

from typing import List

from app.models.calendar_event import CalendarEvent
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class CalendarService:
    EVENT_TYPES = [
        "Meeting",
        "Deadline",
        "Holiday",
        "Training",
        "Leave",
        "Other",
    ]
    RECURRENCE_OPTIONS = ["None", "Daily", "Weekly", "Monthly", "Yearly"]

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def _to_model(self, raw: dict) -> CalendarEvent:
        return CalendarEvent(
            id=raw.get("id") or raw.get("_id"),
            title=str(raw.get("title") or ""),
            event_type=str(raw.get("event_type") or raw.get("type") or "Other"),
            start_date=str(raw.get("start_date") or raw.get("start") or ""),
            end_date=str(raw.get("end_date") or raw.get("end") or ""),
            department=str(raw.get("department") or ""),
            details=str(raw.get("details") or raw.get("description") or ""),
            source_type=str(raw.get("source_type") or "manual"),
            source_id=raw.get("source_id"),
            recurrence=str(raw.get("recurrence") or "None"),
            created_at=raw.get("created_at"),
        )

    def get_month_events(self, year: int, month: int) -> List[CalendarEvent]:
        try:
            data = self._backend.request(
                "GET", f"/api/calendar/events?year={year}&month={month}"
            )
            items = data.get("events") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return [self._to_model(i) for i in items if isinstance(i, dict)]
        except BackendAPIError as exc:
            print(f"⚠️ calendar month fetch failed: {exc}")
            return []

    def get_upcoming_events(self, days: int = 7) -> List[CalendarEvent]:
        try:
            data = self._backend.request(
                "GET", f"/api/calendar/events/upcoming?days={days}"
            )
            items = data.get("events") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return [self._to_model(i) for i in items if isinstance(i, dict)]
        except BackendAPIError as exc:
            print(f"⚠️ calendar upcoming fetch failed: {exc}")
            return []

    def create_event(
        self,
        title: str,
        event_type: str,
        start_date: str,
        end_date: str,
        department: str,
        details: str,
        recurrence: str = "None",
    ):
        payload = {
            "title": title,
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "department": department,
            "details": details,
            "recurrence": recurrence,
        }
        return self._backend.request("POST", "/api/calendar/events", payload)

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
    ):
        payload = {
            "title": title,
            "event_type": event_type,
            "start_date": start_date,
            "end_date": end_date,
            "department": department,
            "details": details,
            "recurrence": recurrence,
        }
        return self._backend.request("PATCH", f"/api/calendar/events/{event_id}", payload)

    def delete_event(self, event_id: int) -> None:
        self._backend.request("DELETE", f"/api/calendar/events/{event_id}")
