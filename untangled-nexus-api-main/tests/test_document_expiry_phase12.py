from datetime import date, timedelta
from zoneinfo import ZoneInfo
from datetime import datetime

from app.routers.documents import expiry_details


async def call(client, headers, method, path, role="Staff", expected=200, **kwargs):
    response = await client.request(method, path, headers=headers[role], **kwargs)
    assert response.status_code == expected, response.text
    return response.json() if response.content else None


def test_expiry_windows_include_seven_and_thirty_day_boundaries():
    today = date(2026, 9, 14)
    assert expiry_details(None, today)["status"] == "no_expiry"
    assert expiry_details("invalid", today)["status"] == "invalid"
    assert expiry_details(today - timedelta(days=1), today)["expiry_window"] == "expired"
    assert expiry_details(today, today)["expiry_window"] == "within_7_days"
    assert expiry_details(today + timedelta(days=7), today)["expiry_window"] == "within_7_days"
    assert expiry_details(today + timedelta(days=8), today)["expiry_window"] == "within_30_days"
    assert expiry_details(today + timedelta(days=30), today)["expiry_window"] == "within_30_days"
    assert expiry_details(today + timedelta(days=31), today)["status"] == "valid"


async def test_expiry_scan_persists_status_and_is_idempotent(api):
    client, db, people, headers = api
    today = datetime.now(ZoneInfo("Africa/Johannesburg")).date()
    documents = []
    for name, offset in (("expired.pdf", -1), ("seven.pdf", 5), ("thirty.pdf", 20), ("valid.pdf", 40)):
        response = await call(
            client,
            headers,
            "POST",
            "/api/documents",
            files={"file": (name, b"%PDF-1.4\nexpiry-test", "application/pdf")},
            data={"document_type": "Compliance", "expiry_date": (today + timedelta(days=offset)).isoformat()},
        )
        documents.append(response["document"])

    await call(client, headers, "POST", "/api/documents/expiry-scan", expected=403)
    await call(client, headers, "POST", "/api/documents/expiry-scan", "Business Lead", expected=403)
    assert await db.notifications.count_documents({}) == 12
    first = await call(client, headers, "POST", "/api/documents/expiry-scan", "Operations Manager")
    assert first["scanned"] == 4
    assert first["expired"] == 1
    assert first["within_7_days"] == 1
    assert first["within_30_days"] == 1
    assert first["valid"] == 1
    assert first["notifications_created"] == 0

    stored = await db.documents.find_one({"name": "seven.pdf"})
    assert stored["expiry_status"] == "expiring"
    assert stored["expiry_window"] == "within_7_days"
    assert stored["days_until_expiry"] == 5
    assert stored["expiry_checked_at"] is not None

    second = await call(client, headers, "POST", "/api/documents/expiry-scan", "Operations Manager")
    assert second["notifications_created"] == 0
    notification_count = await db.notifications.count_documents({})
    assert notification_count == 12

    # Dashboard reads cannot create or duplicate expiry alerts.
    await call(client, headers, "GET", "/api/dashboard/summary", "Operations Manager")
    await call(client, headers, "GET", "/api/dashboard/summary", "Operations Manager")
    assert await db.notifications.count_documents({}) == notification_count

    summary = await call(client, headers, "GET", "/api/documents/expiry-summary", "Operations Manager")
    assert summary["total"] == 4
    assert await db.notifications.count_documents({}) == notification_count

    staff_alerts = await call(client, headers, "GET", "/api/notifications", "Staff")
    assert len(staff_alerts["notifications"]) == 3
    assert all(item["reference_type"] == "Document" for item in staff_alerts["notifications"])

    # A changed expiry date creates one new alert cycle and supersedes old alerts.
    thirty = next(item for item in documents if item["name"] == "thirty.pdf")
    await call(
        client,
        headers,
        "PATCH",
        "/api/documents/" + thirty["id"],
        "Operations Manager",
        json={"expiry_date": (today + timedelta(days=3)).isoformat()},
    )
    changed = await call(client, headers, "POST", "/api/documents/expiry-scan", "Operations Manager")
    assert changed["notifications_created"] == 0
    changed_alerts = await db.notifications.find({"reference_id": thirty["id"]}).to_list(None)
    assert len(changed_alerts) == 8
    assert sum(item.get("read") is not True for item in changed_alerts) == 4
    repeated = await call(client, headers, "POST", "/api/documents/expiry-scan", "Operations Manager")
    assert repeated["notifications_created"] == 0
