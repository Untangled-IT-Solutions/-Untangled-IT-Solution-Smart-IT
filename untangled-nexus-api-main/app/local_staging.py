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
    await db["quotes"].insert_one({
        "_id": ObjectId(),
        "reference": "STG-QUOTE-001",
        "customerName": "Nexus Test Client",
        "company": "Nexus Test Company",
        "email": "procurement@example.co.za",
        "phone": "010 000 0000",
        "address": "Midrand, Gauteng, South Africa",
        "delivery_address": "Midrand, Gauteng, South Africa",
        "preferred_delivery_date": (now() + timedelta(days=14)).date().isoformat(),
        "items": [
            {
                "id": "stg-item-001",
                "name": "Business computer equipment",
                "qty": 1,
            },
        ],
        "assigned_to": {
            "id": str(employees["Operations Manager"]["_id"]),
            "employee_id": employees["Operations Manager"]["employee_id"],
            "name": employees["Operations Manager"]["full_name"],
            "full_name": employees["Operations Manager"]["full_name"],
            "email": employees["Operations Manager"]["email"],
        },
        "assigned_employee_id": employees["Operations Manager"]["_id"],
        "status": "assigned",
        "notes": "Local-only quotation automation walkthrough.",
        "createdAt": now(),
        "updatedAt": now(),
        "revision": 0,
    })
    quotation_created = now()
    await db["quotes"].insert_one({
        "_id": ObjectId(),
        "reference": "STG-QUOTE-002",
        "customerName": "Thandi Customer",
        "company": "Nexus Demonstration Client (Pty) Ltd",
        "email": "accounts@example.co.za",
        "phone": "010 000 0001",
        "address": "1 Demo Avenue, Midrand, Gauteng, 1685",
        "delivery_address": "1 Demo Avenue, Midrand, Gauteng, 1685",
        "assigned_to": {
            "id": str(employees["Operations Manager"]["_id"]),
            "employee_id": employees["Operations Manager"]["employee_id"],
            "name": employees["Operations Manager"]["full_name"],
            "full_name": employees["Operations Manager"]["full_name"],
            "email": employees["Operations Manager"]["email"],
        },
        "assigned_employee_id": employees["Operations Manager"]["_id"],
        "status": "awaiting_client_approval",
        "quotation_snapshot": {
            "reference": "STG-QUOTE-002",
            "issue_date": quotation_created.date().isoformat(),
            "validity_days": 14,
            "valid_until": (quotation_created + timedelta(days=14)).date().isoformat(),
            "currency": "ZAR",
            "vat_percent": "15",
            "subtotal_excl_vat": "12500.00",
            "vat_amount": "1875.00",
            "total_incl_vat": "14375.00",
            "delivery_fee_excl_vat": "0.00",
            "lines": [{
                "sku": "STG-LAPTOP-01",
                "description": "Business laptop with three-year support",
                "quantity": "1",
                "unit_price_excl_vat": "12500.00",
                "line_total_excl_vat": "12500.00",
                "specifications": ["16 GB RAM", "512 GB SSD"],
            }],
            "internal_pricing": [{
                "sku": "STG-LAPTOP-01",
                "description": "Business laptop with three-year support",
                "quantity": "1",
                "unit_price_excl_vat": "12500.00",
                "line_total_excl_vat": "12500.00",
                "cost_unit_excl_vat": "10000.00",
                "markup_percent": "25",
            }],
            "created_by": "Staging Operations",
            "created_at": quotation_created,
        },
        "quotation": [{
            "sku": "STG-LAPTOP-01",
            "description": "Business laptop with three-year support",
            "quantity": "1",
            "unit_price_excl_vat": "12500.00",
            "amount": "12500.00",
        }],
        "quotation_subtotal": "12500.00",
        "quotation_vat": "1875.00",
        "quotation_total": "14375.00",
        "paymentAmount": 14375.0,
        "paymentRequired": True,
        "quote_valid_until": (quotation_created + timedelta(days=14)).date().isoformat(),
        "notes": "Ready-to-approve local invoice workflow demonstration.",
        "createdAt": quotation_created,
        "updatedAt": quotation_created,
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
