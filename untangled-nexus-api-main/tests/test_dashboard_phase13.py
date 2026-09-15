from bson import ObjectId

from app.domain import now


async def get(client, headers, role, path="/api/dashboard/summary"):
    response = await client.get(path, headers=headers[role])
    assert response.status_code == 200, response.text
    return response.json()


async def test_authenticated_role_shapes_dashboard_and_protects_staff(api):
    client, db, people, headers = api
    staff = people["Staff"]["employee"]
    await db.work_assignments.insert_one({
        "_id": ObjectId(), "title": "Customer migration", "status": "In Progress",
        "priority": "High", "assignee_id": staff["_id"], "assigned_to": staff["_id"],
        "assigned_employee": staff["full_name"], "department": "IT", "actual_hours": 2,
        "created_at": now(),
    })
    await db.work_assignments.insert_one({
        "_id": ObjectId(), "title": "Unassigned intake", "status": "Pending",
        "priority": "Normal", "actual_hours": 0, "created_at": now(),
    })

    personal = await get(client, headers, "Staff")
    assert personal["dashboard_type"] == "personal"
    assert personal["employee"]["name"] == "Staff Person"
    assert "employee_workload" not in personal
    assert "attendance_rows" not in personal
    assert "office_requests" not in personal

    # Query-string role claims never change the authenticated shape.
    forged = await client.get("/api/dashboard/summary?role=Operations%20Manager", headers=headers["Staff"])
    assert forged.status_code == 200
    assert forged.json()["dashboard_type"] == "personal"

    director = await get(client, headers, "Director", "/api/dashboard/director")
    assert director["dashboard_type"] == "director"
    assert "business_health" in director and "important_work" in director
    assert "employee_workload" not in director and "attendance_rows" not in director

    business = await get(client, headers, "Business Lead", "/api/dashboard/business-lead")
    assert business["dashboard_type"] == "business_lead"
    assert business["department"] == "IT"
    assert "task_dump" in business and "team_work" in business and "attendance_rows" in business

    operations = await get(client, headers, "Operations Manager", "/api/dashboard/operations")
    assert operations["dashboard_type"] == "operations"
    required = {"incoming_task_dump", "assignment_queue", "employee_workload", "task_status",
                "attendance", "leave_queue", "approvals_queue", "hr", "office_requests",
                "calendar_upcoming", "notifications_unread", "qa_review_queue", "operational_issues"}
    assert required <= operations.keys()


async def test_role_specific_routes_reject_wrong_authenticated_role(api):
    client, _, _, headers = api
    for path in ("/api/dashboard/director", "/api/dashboard/business-lead", "/api/dashboard/operations"):
        response = await client.get(path, headers=headers["Staff"])
        assert response.status_code == 403
