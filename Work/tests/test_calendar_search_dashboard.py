"""Calendar, global search, and dashboard data tests."""

from datetime import date, timedelta

from app.database.database import Database
from app.models.task import Task
from app.services.calendar_service import CalendarService
from app.services.search_service import SearchService
from app.services.work_service import WorkService
from tests.helpers import seeded_employees


def test_work_dates_feed_calendar_search_and_dashboard(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    employee = seeded_employees(database)[0]
    task = WorkService(database).create_work(
        Task(
            id=None,
            title="Submit RFQ response",
            description="Priority response.",
            assigned_employee=employee.full_name,
            assigned_by="Operations Manager",
            priority="High",
            status="Assigned",
            department="Executive",
            created_date=None,
            start_date=date.today().isoformat(),
            due_date=date.today().isoformat(),
            estimated_hours=2,
            category="RFQ",
        )
    )

    events = CalendarService(database).get_month_events(date.today().year, date.today().month)
    results = SearchService(database).search("RFQ")
    assert any(event.source_id == task.id and event.event_type == "RFQ Deadline" for event in events)
    assert any(result.title == "Submit RFQ response" for result in results)


def test_calendar_recurring_event_expands_and_upcoming_events_return_future_occurrences(tmp_path) -> None:
    database = Database(tmp_path / "untangled_nexus.db")
    database.initialize()
    service = CalendarService(database)

    start_date = date.today() - timedelta(days=date.today().weekday())
    event = service.create_event(
        "Weekly sync",
        "Meeting",
        start_date.isoformat(),
        "",
        "Operations",
        "Weekly review",
        "Weekly",
    )

    month_events = service.get_month_events(date.today().year, date.today().month)
    assert any(item.title == event.title for item in month_events)
    upcoming = service.get_upcoming_events(14)
    assert any(item.title == event.title for item in upcoming)
