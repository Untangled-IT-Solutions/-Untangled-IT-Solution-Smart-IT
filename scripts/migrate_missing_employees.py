"""
Safely migrate missing employee profiles from MongoDB users.

SOURCE:
    untangled_nexus.users

TARGET:
    untangled_nexus.employees

IMPORTANT:
    This script does NOT copy passwords or authentication fields.

DEFAULT:
    DRY RUN - nothing is inserted.

To actually create missing employees:

    python scripts/migrate_missing_employees.py --execute
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------
# Make project root importable
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.services.mongodb_service import MongoDBService


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATABASE_NAME = "untangled_nexus"

USERS_COLLECTION = "users"
EMPLOYEES_COLLECTION = "employees"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean_string(value: Any) -> str:
    """Safely convert a value to a stripped string."""

    if value is None:
        return ""

    return str(value).strip()


def first_non_empty(*values: Any) -> str:
    """Return the first non-empty value."""

    for value in values:
        result = clean_string(value)

        if result:
            return result

    return ""


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last name."""

    full_name = clean_string(full_name)

    if not full_name:
        return "", ""

    parts = full_name.split()

    if len(parts) == 1:
        return parts[0], ""

    return parts[0], " ".join(parts[1:])


def make_employee_number(
    employees,
    user: dict[str, Any],
) -> str:
    """
    Generate a safe employee number.

    Preference:
        1. Existing employee_number from user
        2. Existing employee_id if suitable
        3. Next UTS-### number
    """

    existing_number = first_non_empty(
        user.get("employee_number")
    )

    if existing_number:
        return existing_number

    # -------------------------------------------------------------
    # If employee_id is numeric, don't blindly use it as UTS-XXX
    # unless it makes sense.
    # -------------------------------------------------------------

    raw_employee_id = user.get("employee_id")

    if isinstance(raw_employee_id, int):
        candidate = f"UTS-{raw_employee_id:03d}"

        if employees.find_one(
            {"employee_number": candidate}
        ) is None:
            return candidate

    # -------------------------------------------------------------
    # Find the next available UTS number.
    # -------------------------------------------------------------

    existing_numbers = employees.find(
        {
            "employee_number": {
                "$regex": r"^UTS-\d+$"
            }
        },
        {
            "employee_number": 1
        },
    )

    highest = 0

    for employee in existing_numbers:

        number = clean_string(
            employee.get("employee_number")
        )

        try:
            numeric_part = int(
                number.split("-", 1)[1]
            )

            highest = max(
                highest,
                numeric_part,
            )

        except (IndexError, ValueError):
            continue

    next_number = highest + 1

    while employees.find_one(
        {
            "employee_number": f"UTS-{next_number:03d}"
        }
    ):
        next_number += 1

    return f"UTS-{next_number:03d}"


def find_existing_employee(
    employees,
    user: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """
    Find an employee matching a user.

    Matching order:
        1. users.employee_id -> employees._id
        2. users.employee_id -> employees.id
        3. email
        4. username/email-derived possibilities are NOT used
           automatically to avoid false matches.
    """

    employee_id = user.get("employee_id")

    # -------------------------------------------------------------
    # Match MongoDB ObjectId
    # -------------------------------------------------------------

    if employee_id is not None:

        try:
            from bson import ObjectId

            if isinstance(employee_id, ObjectId):

                employee = employees.find_one(
                    {
                        "_id": employee_id
                    }
                )

                if employee:
                    return employee, "MongoDB _id"

        except Exception:
            pass

    # -------------------------------------------------------------
    # Match string ObjectId
    # -------------------------------------------------------------

    if isinstance(employee_id, str):

        try:
            from bson import ObjectId

            if ObjectId.is_valid(employee_id):

                employee = employees.find_one(
                    {
                        "_id": ObjectId(employee_id)
                    }
                )

                if employee:
                    return employee, "MongoDB _id"

        except Exception:
            pass

    # -------------------------------------------------------------
    # Match numeric employee id
    # -------------------------------------------------------------

    if isinstance(employee_id, int):

        employee = employees.find_one(
            {
                "id": employee_id
            }
        )

        if employee:
            return employee, "employee.id"

    # -------------------------------------------------------------
    # Match string numeric employee id
    # -------------------------------------------------------------

    if isinstance(employee_id, str):

        try:
            numeric_id = int(employee_id)

            employee = employees.find_one(
                {
                    "id": numeric_id
                }
            )

            if employee:
                return employee, "employee.id"

        except ValueError:
            pass

    # -------------------------------------------------------------
    # Match email
    # -------------------------------------------------------------

    email = clean_string(
        user.get("email")
    ).lower()

    if email:

        employee = employees.find_one(
            {
                "email": email
            }
        )

        if employee:
            return employee, "email"

    return None, ""


def build_employee_document(
    user: dict[str, Any],
    employee_number: str,
) -> dict[str, Any]:
    """
    Build an employee document from a user document.

    SECURITY:
        Authentication fields such as password_hash are
        intentionally NOT copied.
    """

    full_name = first_non_empty(
        user.get("full_name"),
        user.get("name"),
    )

    first_name = first_non_empty(
        user.get("first_name")
    )

    last_name = first_non_empty(
        user.get("last_name")
    )

    # -------------------------------------------------------------
    # If first/last names aren't available, derive them.
    # -------------------------------------------------------------

    if not first_name and not last_name:

        first_name, last_name = split_full_name(
            full_name
        )

    if not full_name:

        full_name = " ".join(
            part
            for part in [
                first_name,
                last_name,
            ]
            if part
        )

    # -------------------------------------------------------------
    # Build ONLY employee/profile data.
    #
    # DO NOT copy:
    # password_hash
    # username
    # require_password_change
    # last_login_at
    # authentication tokens
    # -------------------------------------------------------------

    employee = {
        "employee_number": employee_number,

        "first_name": first_name,

        "last_name": last_name,

        "full_name": full_name,

        "position": first_non_empty(
            user.get("position"),
            user.get("job_title"),
            "Staff",
        ),

        "department": first_non_empty(
            user.get("department"),
            "General",
        ),

        "role": first_non_empty(
            user.get("role"),
            "Staff",
        ),

        "reports_to": first_non_empty(
            user.get("reports_to")
        ),

        "mentor": first_non_empty(
            user.get("mentor")
        ),

        "email": first_non_empty(
            user.get("email")
        ),

        "phone": first_non_empty(
            user.get("phone"),
            user.get("phone_number"),
        ),

        "status": first_non_empty(
            user.get("employee_status"),
            "Active",
        ),

        "employment_type": first_non_empty(
            user.get("employment_type"),
            "Full-time",
        ),

        "date_joined": first_non_empty(
            user.get("date_joined"),
            user.get("created_at"),
        ),

        "clocked_in": False,

        "current_task": "No active task",

        "profile_photo": "",

        "skills": "",

        "permissions": "",

        "performance_score": 0.0,

        "training_progress": 0.0,

        "notes": "",

        # Useful audit information.
        "created_from_user_migration": True,

        "source_user_id": user.get("_id"),

        "migrated_at": datetime.now(
            timezone.utc
        ),
    }

    return employee


# ---------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------

def migrate(
    execute: bool = False,
) -> None:

    print("\n")
    print("=" * 70)
    print("🔄 UNTANGLED NEXUS - MISSING EMPLOYEE MIGRATION")
    print("=" * 70)

    if execute:
        print("\n⚠️ MODE: EXECUTE")
        print("Missing employee records WILL be created.")
    else:
        print("\n🔎 MODE: DRY RUN")
        print("NO DATABASE RECORDS WILL BE CREATED.")

    print("=" * 70)

    # -------------------------------------------------------------
    # Connect
    # -------------------------------------------------------------

    print("\n🔌 Connecting to MongoDB...")

    mongodb = MongoDBService()

    print("✅ MongoDB connected")

    print(
        "📊 Database:",
        mongodb.db_name,
    )

    if mongodb.db_name != DATABASE_NAME:

        print(
            "\n❌ SAFETY STOP"
        )

        print(
            f"Expected database: {DATABASE_NAME}"
        )

        print(
            f"Connected database: {mongodb.db_name}"
        )

        print(
            "\nNo changes were made."
        )

        return

    # -------------------------------------------------------------
    # Collections
    # -------------------------------------------------------------

    users = mongodb.get_collection(
        USERS_COLLECTION
    )

    employees = mongodb.get_collection(
        EMPLOYEES_COLLECTION
    )

    user_count = users.count_documents({})

    employee_count = employees.count_documents({})

    print("\n📊 Current database state:")

    print(
        f"   Users:     {user_count}"
    )

    print(
        f"   Employees: {employee_count}"
    )

    # -------------------------------------------------------------
    # Counters
    # -------------------------------------------------------------

    matched = 0
    missing = 0
    created = 0
    skipped = 0
    errors = 0

    # -------------------------------------------------------------
    # Process users
    # -------------------------------------------------------------

    print("\n🔍 Checking users against employees...\n")

    for user in users.find({}):

        username = clean_string(
            user.get("username")
        )

        email = clean_string(
            user.get("email")
        )

        full_name = clean_string(
            user.get("full_name")
        )

        print("-" * 70)

        print(
            "User:",
            username or "(no username)"
        )

        print(
            "Name:",
            full_name or "(no name)"
        )

        print(
            "Email:",
            email or "(no email)"
        )

        print(
            "employee_id:",
            user.get("employee_id")
        )

        # ---------------------------------------------------------
        # Find matching employee
        # ---------------------------------------------------------

        existing, match_type = find_existing_employee(
            employees,
            user,
        )

        if existing:

            matched += 1

            print(
                f"✅ MATCHED via {match_type}"
            )

            print(
                "   Employee:",
                existing.get(
                    "full_name",
                    existing.get(
                        "employee_number",
                        str(existing.get("_id"))
                    )
                )
            )

            continue

        # ---------------------------------------------------------
        # Missing employee
        # ---------------------------------------------------------

        missing += 1

        print(
            "⚠️ NO MATCHING EMPLOYEE FOUND"
        )

        # ---------------------------------------------------------
        # Safety checks
        # ---------------------------------------------------------

        if not email and not full_name:

            skipped += 1

            print(
                "⏭️ SKIPPED: insufficient employee information"
            )

            continue

        # ---------------------------------------------------------
        # Generate employee number
        # ---------------------------------------------------------

        employee_number = make_employee_number(
            employees,
            user,
        )

        employee_document = build_employee_document(
            user,
            employee_number,
        )

        print(
            "   Proposed employee number:",
            employee_number,
        )

        print(
            "   Proposed name:",
            employee_document["full_name"],
        )

        print(
            "   Proposed department:",
            employee_document["department"],
        )

        print(
            "   Proposed role:",
            employee_document["role"],
        )

        # ---------------------------------------------------------
        # DRY RUN
        # ---------------------------------------------------------

        if not execute:

            print(
                "   🔎 DRY RUN: nothing inserted"
            )

            continue

        # ---------------------------------------------------------
        # Final duplicate checks immediately before insert
        # ---------------------------------------------------------

        if email:

            duplicate = employees.find_one(
                {
                    "email": email
                }
            )

            if duplicate:

                skipped += 1

                print(
                    "⏭️ SKIPPED: employee with this email "
                    "now exists"
                )

                continue

        duplicate_number = employees.find_one(
            {
                "employee_number": employee_number
            }
        )

        if duplicate_number:

            skipped += 1

            print(
                "⏭️ SKIPPED: employee number already exists"
            )

            continue

        # ---------------------------------------------------------
        # Insert
        # ---------------------------------------------------------

        try:

            result = employees.insert_one(
                employee_document
            )

            created += 1

            print(
                "✅ CREATED employee:",
                result.inserted_id,
            )

        except Exception as exc:

            errors += 1

            print(
                "❌ ERROR creating employee:",
                exc,
            )

    # -------------------------------------------------------------
    # Final report
    # -------------------------------------------------------------

    final_employee_count = (
        employees.count_documents({})
    )

    print("\n")
    print("=" * 70)
    print("📋 MIGRATION REPORT")
    print("=" * 70)

    print(
        f"Users checked:              {user_count}"
    )

    print(
        f"Employees before migration: {employee_count}"
    )

    print(
        f"Users already matched:      {matched}"
    )

    print(
        f"Missing employee profiles:  {missing}"
    )

    print(
        f"Employees created:          {created}"
    )

    print(
        f"Skipped:                     {skipped}"
    )

    print(
        f"Errors:                      {errors}"
    )

    print(
        f"Employees after migration:  {final_employee_count}"
    )

    print("=" * 70)

    if not execute:

        print(
            "\n🔎 DRY RUN COMPLETE"
        )

        print(
            "No records were changed."
        )

        print(
            "\nIf the proposed records look correct,"
        )

        print(
            "run:"
        )

        print(
            "python scripts/migrate_missing_employees.py --execute"
        )

    else:

        print(
            "\n✅ MIGRATION COMPLETE"
        )

        print(
            "MongoDB employees collection has been updated."
        )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

if __name__ == "__main__":

    execute = "--execute" in sys.argv

    try:

        migrate(
            execute=execute
        )

    except KeyboardInterrupt:

        print(
            "\n\n⚠️ Migration cancelled by user."
        )

    except Exception as exc:

        print(
            "\n❌ Migration failed:"
        )

        print(exc)

        import traceback

        traceback.print_exc()