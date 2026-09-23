from datetime import timedelta

from app.domain import now
from app.domain import notify
from app.notification_events import subscribe
from app.routers import health


async def test_notification_pagination_delivery_and_read_state(api):
    client, db, people, headers = api
    employee_id = people["Staff"]["employee"]["_id"]
    created = now()
    for index in range(3):
        await db.notifications.insert_one({
            "_id": f"notification:{index}",
            "employee_id": employee_id,
            "title": f"Message {index}",
            "message": "Test",
            "read": False,
            "created_at": created - timedelta(minutes=index),
        })

    response = await client.get(
        "/api/notifications?limit=2", headers=headers["Staff"]
    )
    assert response.status_code == 200
    page = response.json()
    assert len(page["notifications"]) == 2
    assert page["has_more"] is True
    assert page["next_before"]
    assert all(row["delivery_status"] == "delivered" for row in page["notifications"])

    second = await client.get(
        "/api/notifications",
        params={"limit": 2, "before": page["next_before"]},
        headers=headers["Staff"],
    )
    assert len(second.json()["notifications"]) == 1

    unread = await client.get("/api/notifications/unread-count", headers=headers["Staff"])
    assert unread.json()["count"] == 3

    notification_id = page["notifications"][0]["_id"]
    marked = await client.post(
        f"/api/notifications/{notification_id}/read", headers=headers["Staff"]
    )
    assert marked.status_code == 200
    stored = await db.notifications.find_one({"_id": notification_id})
    assert stored["read"] is True
    assert stored["delivery_status"] == "read"


async def test_request_id_and_metrics_are_exposed(api):
    client, _db, _people, _headers = api
    response = await client.get("/api/health", headers={"X-Request-ID": "test-request-id"})
    assert response.headers["x-request-id"] == "test-request-id"
    metrics = (await client.get("/api/metrics")).json()
    assert metrics["requests"] >= 1
    assert "/api/health" in metrics["routes"]


async def test_metrics_token_is_enforced_when_configured(api, monkeypatch):
    client, _db, _people, _headers = api
    settings = health.get_settings()
    monkeypatch.setattr(settings, "metrics_token", "monitor-secret")
    denied = await client.get("/api/metrics")
    allowed = await client.get(
        "/api/metrics", headers={"X-Metrics-Token": "monitor-secret"}
    )
    assert denied.status_code == 401
    assert allowed.status_code == 200


async def test_notification_event_is_published_once(api):
    _client, db, people, _headers = api
    employee_id = people["Staff"]["employee"]["_id"]
    async with subscribe({str(employee_id)}) as queue:
        created = await notify(db, "event:test", employee_id, "Action required", "Review task", "Task", "123")
        assert created is True
        event = await queue.get()
        assert event["id"] == "event:test"
        assert event["reference_id"] == "123"
        duplicate = await notify(db, "event:test", employee_id, "Action required", "Review task", "Task", "123")
        assert duplicate is False
        assert queue.empty()


async def test_mutations_create_request_audit_events(api):
    client, db, _people, headers = api
    response = await client.post(
        "/api/notifications/mark-all-read", headers=headers["Staff"]
    )
    assert response.status_code == 200
    event = await db.audit_events.find_one({"request_id": response.headers["x-request-id"]})
    assert event["route"] == "/api/notifications/mark-all-read"
    assert event["employee_id"]
