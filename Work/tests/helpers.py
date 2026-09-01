"""Test helpers for the transitional desktop app architecture."""

from app.models.employee import Employee


def seeded_employees(database) -> list[Employee]:
    """Read the SQLite seed employees used by local/offline services."""
    with database.connection() as connection:
        rows = connection.execute("SELECT * FROM employees ORDER BY id ASC;").fetchall()

    return [
        Employee(
            id=row["id"],
            employee_number=row["employee_number"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            full_name=row["full_name"],
            position=row["position"],
            department=row["department"],
            role=row["role"],
            reports_to=row["reports_to"] or "",
            mentor=row["mentor"] or "",
            email=row["email"] or "",
            phone=row["phone"] or "",
            status=row["status"],
            employment_type=row["employment_type"],
            date_joined=row["date_joined"] or "",
            clocked_in=bool(row["clocked_in"]),
            current_task=row["current_task"] or "",
            profile_photo=row["profile_photo"] or "",
            skills=row["skills"] or "",
            permissions=row["permissions"] or "",
            performance_score=float(row["performance_score"] or 0),
            training_progress=float(row["training_progress"] or 0),
            notes=row["notes"] or "",
        )
        for row in rows
    ]
