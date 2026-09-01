"""BackendCalendarService contract tests."""

from app.models.calendar_event import CalendarEvent
from app.services.backend_calendar_service import BackendCalendarService


class FakeBackend:
    def __init__(self) -> None:
        self.calls = []
        self.event = {
            "id": "event-1",
            "title": "Director approval deadline",
            "event_type": "Approval Deadline",
            "start_date": "2026-08-28",
            "end_date": "",
            "department": "Executive",
            "details": "Budget approval waiting for action.",
            "source_type": "Approval",
            "source_id": "approval-1",
            "recurrence": "None",
            "created_at": "2026-08-27T08:00:00.000Z",
        }

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.startswith("/api/calendar/events?"):
            return {"success": True, "events": [self.event]}
        if method == "POST" and path == "/api/calendar/events":
            return {"success": True, "event": {**self.event, **(payload or {})}}
        if method == "PATCH":
            return {"success": True, "event": {**self.event, **(payload or {})}}
        return {"success": True}


def test_backend_calendar_service_reads_month_events() -> None:
    backend = FakeBackend()
    service = BackendCalendarService(backend)

    events = service.get_month_events(2026, 8)

    assert events[0].title == "Director approval deadline"
    assert events[0].source_type == "Approval"
    assert backend.calls[0][1] == "/api/calendar/events?year=2026&month=8"


def test_backend_calendar_service_creates_updates_and_deletes_manual_events() -> None:
    backend = FakeBackend()
    service = BackendCalendarService(backend)

    created = service.create_event(
        "Ops triage",
        "Meeting",
        "2026-08-29",
        "",
        "Operations",
        "Assign dumped tasks.",
    )
    updated = service.update_event(
        "event-1",
        "Ops triage updated",
        "Meeting",
        "2026-08-30",
        "",
        "Operations",
        "Review assignments.",
    )
    service.delete_event("event-1")

    assert isinstance(created, CalendarEvent)
    assert created.title == "Ops triage"
    assert updated.start_date == "2026-08-30"
    assert backend.calls[0][0] == "POST"
    assert backend.calls[1][0] == "PATCH"
    assert backend.calls[2] == ("DELETE", "/api/calendar/events/event-1", None)
