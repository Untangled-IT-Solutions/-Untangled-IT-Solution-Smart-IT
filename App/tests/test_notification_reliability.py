import threading

import pytest

from app.services.backend_api_client import BackendAPIClient, BackendAPIError
from app.services.notification_service import NotificationService


class Backend:
    def __init__(self):
        self.calls = []
        self.fail = False

    def request(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if self.fail:
            raise BackendAPIError("offline")
        if path == "/api/notifications/unread-count":
            return {"success": True, "count": 7}
        if path.startswith("/api/notifications?"):
            return {"success": True, "notifications": [{"_id": "n1", "title": "Ready"}]}
        return {"success": True, "matched": 1, "modified": 1}


def test_unread_count_uses_count_endpoint_and_stale_fallback():
    backend = Backend()
    service = NotificationService(backend)
    assert service.count_unread() == 7
    assert backend.calls[-1][1] == "/api/notifications/unread-count"
    backend.fail = True
    assert service.count_unread() == 7
    assert service.is_stale is True


def test_notification_list_preserves_cached_data_during_outage():
    backend = Backend()
    service = NotificationService(backend)
    assert [item.id for item in service.get_notifications()] == ["n1"]
    backend.fail = True
    assert [item.id for item in service.get_notifications()] == ["n1"]
    assert service.last_error == "offline"


def test_first_notification_failure_is_not_reported_as_empty_inbox():
    backend = Backend()
    backend.fail = True
    with pytest.raises(BackendAPIError):
        NotificationService(backend).get_notifications()


def test_mark_read_uses_single_canonical_route():
    backend = Backend()
    service = NotificationService(backend)
    assert service.mark_read("n1") is True
    assert backend.calls == [("POST", "/api/notifications/n1/read", None)]


def test_sse_client_parses_named_events(monkeypatch):
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=False):
            assert decode_unicode is True
            yield "event: notification"
            yield 'data: {"id":"n1"}'
            yield ""

    monkeypatch.setattr(
        "app.services.backend_api_client.requests.get",
        lambda *_args, **_kwargs: Response(),
    )
    client = BackendAPIClient(base_url="https://example.test")
    result = []

    def consume():
        result.extend(client.iter_sse("/api/notifications/stream", threading.Event()))

    worker = threading.Thread(target=consume)
    worker.start()
    worker.join(timeout=2)
    assert result == [{"id": "n1", "_event": "notification"}]
