"""Notification grouping and search behaviour."""

from types import SimpleNamespace

from app.views.notification_view import NotificationView


class FakeVar:
    def __init__(self, value: str) -> None:
        self.value = value

    def get(self) -> str:
        return self.value


def test_notification_sources_are_collapsed_into_simple_groups() -> None:
    assert NotificationView._notification_group(
        {"title": "Task assigned", "category": "Task Assignment"}
    ) == "Tasks"
    assert NotificationView._notification_group(
        {"title": "Quote assigned", "category": "Quote Assignment"}
    ) == "Sales"
    assert NotificationView._notification_group(
        {"title": "Meeting invite", "category": "Meeting"}
    ) == "Calendar"
    assert NotificationView._notification_group(
        {"title": "Leave approved", "category": "Approval"}
    ) == "Approvals"
    assert NotificationView._notification_group(
        {"title": "Low printer toner", "category": "Inventory"}
    ) == "Operations"


def test_search_uses_message_category_reference_and_recipient() -> None:
    view = SimpleNamespace(search_var=FakeVar("rfq-104"))
    notification = {
        "title": "Pricing required",
        "message": "Supplier response received",
        "category": "RFQ",
        "reference_id": "RFQ-104",
        "recipient_name": "Dipuo Tlowana",
    }
    assert NotificationView._matches_search(view, notification)

    view.search_var = FakeVar("bongiwe")
    assert not NotificationView._matches_search(view, notification)
