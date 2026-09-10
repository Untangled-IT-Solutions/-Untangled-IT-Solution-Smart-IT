"""Task email and calendar meeting workflow tests (no real email is sent)."""

from app.database.database import Database
from app.models.task import Task
from app.services.calendar_service import CalendarService
from app.services.email_notification_service import EmailNotificationService
from app.services.meeting_assistant_service import MeetingAssistantService
from app.services.work_service import WorkService


class FakeEmailService:
    def __init__(self) -> None:
        self.task_assignments = []
        self.invites = []
        self.summaries = []
        self.reports = []

    def send_task_assignment(self, task) -> bool:
        self.task_assignments.append(task)
        return True

    def send_meeting_invite(self, event) -> bool:
        self.invites.append(event)
        return True

    def send_meeting_summary(self, event) -> bool:
        self.summaries.append(event)
        return True

    def send_meeting_report(self, *values) -> bool:
        self.reports.append(values)
        return True


def test_task_assignment_uses_employee_email_and_does_not_send_by_default(tmp_path) -> None:
    database = Database(tmp_path / "nexus.db")
    database.initialize()
    service = EmailNotificationService(database)

    assert service.enabled is False
    assert service.resolve_email("Gift Wesi") == "g.wesi@untangledits.co.za"

    task = Task(
        id=None, title="Inspect laptop", description="Run diagnostics",
        assigned_employee="Gift Wesi", assigned_by="Ubuntu Hadebe",
        priority="High", status="To Do", department="Technical",
        created_date=None, start_date="2026-09-07", due_date="2026-09-08",
        estimated_hours=2, category="Technical",
    )
    assert service.send_task_assignment(task) is False
    connection = database.connection()
    try:
        row = connection.execute("SELECT recipient, status FROM email_delivery_log").fetchone()
    finally:
        connection.close()
    assert tuple(row) == ("g.wesi@untangledits.co.za", "Skipped")


def test_work_service_notifies_new_assignee(tmp_path) -> None:
    database = Database(tmp_path / "nexus.db")
    database.initialize()
    email = FakeEmailService()
    service = WorkService(database, email_service=email)
    created = service.create_work(
        Task(
            id=None, title="Repair laptop", description="Replace SSD",
            assigned_employee="Gift Wesi", assigned_by="Ubuntu Hadebe",
            priority="High", status="To Do", department="Technical",
            created_date=None, start_date="2026-09-07", due_date="2026-09-08",
            estimated_hours=2, category="Technical",
        )
    )
    assert email.task_assignments == [created]


def test_meeting_notes_persist_and_email_actions_are_requested(tmp_path) -> None:
    database = Database(tmp_path / "nexus.db")
    database.initialize()
    email = FakeEmailService()
    service = CalendarService(database, email_service=email)

    created = service.create_event(
        "Operations review", "Meeting", "2026-09-08", "", "Operations",
        "Weekly review", start_time="09:00", end_time="10:00",
        location="Teams", attendees="Gift Wesi, snkosi@untangledits.co.za",
        agenda="Review open work", minutes="Discussed workload",
        summary="Two tasks reassigned", decisions="Prioritise laptop batch",
        action_items="Gift: diagnostics by Friday", send_invites=True,
    )

    assert created.start_time == "09:00"
    assert created.summary == "Two tasks reassigned"
    assert email.invites == [created]
    assert service.send_meeting_summary(created.id) is True
    assert email.summaries == [created]


def test_natural_language_times_and_attendee_names_are_optional(tmp_path) -> None:
    database = Database(tmp_path / "nexus.db")
    database.initialize()
    service = CalendarService(database)

    event = service.create_event(
        "Flexible meeting", "Meeting", "2026-09-07", "", "Operations", "",
        start_time="9h00", end_time="2h00",
        attendees="nonhlanhla and siyanda",
    )

    assert event.start_time == "9h00"
    assert event.end_time == "2h00"
    directory = EmailNotificationService(database)
    assert directory.resolve_recipients(event.attendees) == [
        "nhlatshwayo@untangledits.co.za",
        "snkosi@untangledits.co.za",
    ]


def test_written_meeting_report_contains_summary_and_transcript(tmp_path) -> None:
    from docx import Document

    report_path = MeetingAssistantService._create_word_report(
        "Operations review",
        "2026-09-07",
        "09:00",
        "Boardroom",
        "The team reviewed the outstanding laptop repairs.",
        "Laptop repairs were reviewed and prioritised.",
        tmp_path,
    )
    document = Document(report_path)
    report_text = "\n".join(paragraph.text for paragraph in document.paragraphs)

    assert report_path.exists()
    assert "Meeting Summary" in report_text
    assert "Laptop repairs were reviewed and prioritised." in report_text
    assert "Full Transcript" in report_text
    assert "outstanding laptop repairs" in report_text
