"""Role matrix tests for authenticated, server-side authorization."""

from bson import ObjectId

from app.domain import now


async def call(client, headers, method, path, role="Staff", expected=200, **kwargs):
    response = await client.request(method, path, headers=headers[role], **kwargs)
    assert response.status_code == expected, response.text
    return response.json() if response.content else None


async def test_task_dump_visibility_and_operations_assignment(api):
    c, db, people, h = api
    finance_employee = {
        "_id": ObjectId(), "employee_id": "finance-1", "full_name": "Finance Person",
        "email": "finance@test.invalid", "role": "Staff", "status": "active", "department": "Finance",
    }
    await db.employees.insert_one(finance_employee)
    finance_task = {
        "_id": ObjectId(), "title": "Private finance work", "status": "Pending",
        "department": "Finance", "employee_id": finance_employee["_id"],
        "assignee_id": finance_employee["_id"], "assigned_to": finance_employee["_id"],
        "revision": 0, "created_at": now(), "updated_at": now(),
    }
    await db.work_assignments.insert_one(finance_task)

    await call(c, h, "POST", "/api/tasks", expected=403, json={"title": "Forged staff dump"})
    dumped = await call(
        c, h, "POST", "/api/tasks", "Business Lead",
        json={"title": "Business task dump", "department": "Finance"},
    )
    task_id = dumped["task"]["id"]
    assert dumped["task"]["department"] == "IT"

    await call(
        c, h, "POST", f"/api/tasks/{task_id}/assign", "Business Lead", expected=403,
        json={"employee_id": str(people["Staff"]["employee"]["_id"])},
    )
    await call(
        c, h, "POST", f"/api/tasks/{task_id}/assign", "Director", expected=403,
        json={"employee_id": str(people["Staff"]["employee"]["_id"])},
    )
    assigned = await call(
        c, h, "POST", f"/api/tasks/{task_id}/assign", "Operations Manager",
        json={"employee_id": str(people["Staff"]["employee"]["_id"])},
    )
    assert assigned["task"]["assigned_employee"] == "Staff Person"

    business_tasks = (await call(c, h, "GET", "/api/tasks", "Business Lead"))["tasks"]
    operations_tasks = (await call(c, h, "GET", "/api/tasks", "Operations Manager"))["tasks"]
    assert task_id in {item["id"] for item in business_tasks}
    assert str(finance_task["_id"]) not in {item["id"] for item in business_tasks}
    assert str(finance_task["_id"]) in {item["id"] for item in operations_tasks}

    workload = (await call(c, h, "GET", "/api/tasks/workload", "Business Lead"))["workload"]
    assert all(item["employee"] != "Finance Person" for item in workload)
    await call(c, h, "GET", "/api/tasks/decision-queue", "Business Lead", expected=403)
    await call(c, h, "GET", "/api/tasks/decision-queue", "Operations Manager")


async def test_people_and_attendance_are_personal_or_authorized_team_scope(api):
    c, db, people, h = api
    finance = {
        "_id": ObjectId(), "employee_id": "finance-2", "full_name": "Other Department",
        "email": "other.department@test.invalid", "role": "Staff", "status": "active", "department": "Finance",
    }
    await db.employees.insert_one(finance)

    staff_rows = (await call(c, h, "GET", "/api/employees"))["employees"]
    business_rows = (await call(c, h, "GET", "/api/employees", "Business Lead"))["employees"]
    operations_rows = (await call(c, h, "GET", "/api/employees", "Operations Manager"))["employees"]
    assert [row["full_name"] for row in staff_rows] == ["Staff Person"]
    assert "Other Department" not in {row["full_name"] for row in business_rows}
    assert "Other Department" in {row["full_name"] for row in operations_rows}

    path = "/api/employees/" + str(finance["_id"])
    await call(c, h, "GET", path, "Business Lead", expected=403)
    await call(c, h, "GET", path, "Operations Manager")
    await call(c, h, "GET", "/api/attendance/team", "Business Lead", expected=403)
    await call(c, h, "GET", "/api/attendance/team", "Operations Manager")
    await call(
        c, h, "GET", "/api/attendance/today?employee_id=" + str(finance["_id"]),
        "Staff", expected=403,
    )


async def test_client_claims_cannot_grant_approval_authority(api):
    c, db, people, h = api
    approval = await call(
        c, h, "POST", "/api/approvals",
        json={"title": "Controlled request", "requested_by": "Director Person", "requires_director": True},
    )
    record = approval["approval"]
    assert record["requested_by"] == "Staff Person"
    path = "/api/approvals/" + record["_id"] + "/approve"

    forged = {"reviewer_name": "Director Person", "reviewer_role": "Director"}
    await call(c, h, "POST", path, expected=403, json=forged)
    await call(c, h, "POST", path, "Business Lead", expected=403, json=forged)
    await call(c, h, "POST", path, "Operations Manager", json=forged)
    await call(c, h, "POST", path, "Operations Manager", expected=403, json={"reviewer_role": "Business Lead"})
    await call(c, h, "POST", path, "Business Lead", json={"reviewer_name": "Imposter"})
    await call(c, h, "POST", path, "Business Lead", expected=403, json={"reviewer_role": "Director"})
    final = await call(c, h, "POST", path, "Director", json={"reviewer_name": "Imposter"})
    assert final["approval"]["status"] == "Approved"
    stored = await db.approvals.find_one({"_id": ObjectId(record["_id"])})
    assert stored["manager_approved_by"] == "Operations Manager Person"
    assert stored["business_approved_by"] == "Business Lead Person"
    assert stored["director_approved_by"] == "Director Person"


async def test_privilege_escalation_and_management_actions_are_rejected(api):
    c, db, people, h = api
    staff_user_id = str(people["Staff"]["user"]["_id"])
    staff_employee_id = str(people["Staff"]["employee"]["_id"])

    await call(c, h, "PATCH", f"/api/admin/users/{staff_user_id}", expected=403, json={"role": "Director"})
    await call(c, h, "PATCH", f"/api/admin/users/{staff_user_id}", "Operations Manager", expected=403, json={"role": "Director"})
    await call(c, h, "PATCH", f"/api/admin/users/{staff_user_id}", "Director", expected=422, json={"role": "Super Admin"})
    await call(c, h, "GET", "/api/admin/users", "Business Lead", expected=403)
    await call(
        c, h, "POST", "/api/notifications", "Business Lead", expected=403,
        json={"employee_id": staff_employee_id, "title": "Forged", "message": "No"},
    )

    quote = {"_id": ObjectId(), "reference": "Q-AUTH-1", "status": "received", "revision": 0}
    await db.quotes.insert_one(quote)
    await call(
        c, h, "PUT", "/api/admin/quotes/Q-AUTH-1/assignment", "Business Lead", expected=403,
        json={"employee_id": staff_employee_id},
    )
    await call(
        c, h, "PUT", "/api/admin/quotes/Q-AUTH-1/assignment", "Operations Manager",
        json={"employee_id": staff_employee_id},
    )
    await call(c, h, "GET", "/api/reports/types", expected=403)

    business_types = (await call(c, h, "GET", "/api/reports/types", "Business Lead"))["types"]
    assert "Task Workload" in business_types
    assert "Attendance Summary" not in business_types
    await call(
        c, h, "GET", "/api/reports/preview?type=Attendance%20Summary",
        "Business Lead", expected=403,
    )
