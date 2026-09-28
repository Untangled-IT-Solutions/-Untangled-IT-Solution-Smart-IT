from __future__ import annotations

from datetime import timedelta

from bson import ObjectId

from app.domain import now
from app.security import hash_pbkdf2_sha256


STAGING_ACCOUNTS = (
    ("director@staging.local", "Director", "Staging Director", "Executive"),
    ("lead@staging.local", "Business Lead", "Staging Business Lead", "Sales"),
    ("operations@staging.local", "Operations Manager", "Staging Operations", "Operations"),
    ("staff@staging.local", "Staff", "Staging Staff", "Operations"),
    ("intern@staging.local", "Intern", "Staging Intern", "Operations"),
)


async def seed_local_staging(db, password: str) -> None:
    """Populate a disposable local database with representative workflow data."""
    password_hash = hash_pbkdf2_sha256(password)
    employees: dict[str, dict] = {}
    for index, (email, role, full_name, department) in enumerate(STAGING_ACCOUNTS, 1):
        employee = {
            "_id": ObjectId(),
            "employee_id": f"STG-{index:03d}",
            "full_name": full_name,
            "email": email,
            "role": role,
            "department": department,
            "position": role,
            "status": "active",
            "created_at": now(),
        }
        employees[role] = employee
        await db["employees"].insert_one(employee)
        await db["users"].insert_one({
            "_id": ObjectId(),
            "employee_id": employee["_id"],
            "nexus_employee_id": str(employee["_id"]),
            "username": email,
            "username_normalized": email,
            "email": email,
            "full_name": full_name,
            "role": role,
            "status": "active",
            "password_hash": password_hash,
            "require_password_change": False,
            "created_at": now(),
        })

    staff = employees["Staff"]
    lead = employees["Business Lead"]
    tasks = (
        ("Urgent client escalation", "In Progress", "Urgent", staff["_id"], 4),
        ("Prepare weekly operations report", "Pending", "High", lead["_id"], 2),
        ("Review completed installation", "Waiting Review", "Medium", staff["_id"], 6),
    )
    for index, (title, status, priority, employee_id, hours) in enumerate(tasks, 1):
        await db["tasks"].insert_one({
            "_id": ObjectId(),
            "title": title,
            "status": status,
            "priority": priority,
            "employee_id": employee_id,
            "assigned_to": employee_id,
            "estimated_hours": hours,
            "created_at": now() - timedelta(hours=index * 3),
            "due_date": (now() + timedelta(days=index - 2)).date().isoformat(),
            "revision": 0,
        })

    await db["approvals"].insert_one({
        "_id": ObjectId(),
        "title": "Local staging leave approval",
        "request_type": "Leave",
        "requested_by": staff["full_name"],
        "employee_id": staff["_id"],
        "status": "Pending",
        "current_stage": "Director",
        "submitted_at": now(),
        "created_at": now(),
        "revision": 0,
    })
    await db["office_requests"].insert_one({
        "_id": ObjectId(),
        "item": "Test laptop charger",
        "quantity": 1,
        "requested_by": staff["full_name"],
        "employee_id": staff["_id"],
        "status": "Pending",
        "current_stage": "Operations Manager",
        "created_at": now(),
        "revision": 0,
    })
    await db["calendar_events"].insert_one({
        "_id": ObjectId(),
        "title": "Staging operations review",
        "start_date": (now() + timedelta(days=1)).isoformat(),
        "end_date": (now() + timedelta(days=1, hours=1)).isoformat(),
        "created_at": now(),
    })
    await db["notifications"].insert_one({
        "_id": "staging:welcome",
        "employee_id": staff["_id"],
        "title": "Local staging notification",
        "message": "This notification exists only in the disposable staging database.",
        "category": "General",
        "read": False,
        "created_at": now(),
    })
