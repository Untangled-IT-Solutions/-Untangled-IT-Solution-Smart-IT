"""People module data service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.employee import Employee


class PeopleService:
    """Provides employee data from SQLite."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def get_employees(
        self,
        search: str = "",
        department: str = "All",
        role: str = "All",
        status: str = "All",
    ) -> list[Employee]:
        """Return employees matching optional filters."""
        query = "SELECT * FROM employees WHERE 1 = 1"
        parameters: list[object] = []

        if search:
            query += " AND (full_name LIKE ? OR position LIKE ? OR email LIKE ?)"
            search_pattern = f"%{search}%"
            parameters.extend([search_pattern, search_pattern, search_pattern])

        if department != "All":
            query += " AND department = ?"
            parameters.append(department)

        if role != "All":
            query += " AND role = ?"
            parameters.append(role)

        if status != "All":
            query += " AND status = ?"
            parameters.append(status)

        query += " ORDER BY id ASC;"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [self._row_to_employee(row) for row in rows]

    def get_employee(self, employee_id: int) -> Employee | None:
        """Return one employee by id."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM employees WHERE id = ?;",
                (employee_id,),
            ).fetchone()

        return self._row_to_employee(row) if row is not None else None

    def get_employee_by_name(self, full_name: str) -> Employee | None:
        """Return an employee by display name for cross-module assignments."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM employees WHERE full_name = ?;",
                (full_name,),
            ).fetchone()
        return self._row_to_employee(row) if row is not None else None

    def get_departments(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name FROM departments ORDER BY name ASC;"
            ).fetchall()
        return [row["name"] for row in rows]

    def get_roles(self) -> list[str]:
        return self._distinct_values("role")

    def get_statuses(self) -> list[str]:
        return self._distinct_values("status")

    def get_employee_names(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT full_name FROM employees ORDER BY full_name ASC;"
            ).fetchall()
        return [row["full_name"] for row in rows]

    def _distinct_values(self, column_name: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT DISTINCT {column_name} FROM employees ORDER BY {column_name} ASC;"
            ).fetchall()
        return [row[column_name] for row in rows if row[column_name]]

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _row_to_employee(row: sqlite3.Row) -> Employee:
        return Employee(
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
            current_task=row["current_task"] or "No active task",
            profile_photo=row["profile_photo"] or "",
            skills=row["skills"] or "",
            permissions=row["permissions"] or "",
            performance_score=float(row["performance_score"] or 0),
            training_progress=float(row["training_progress"] or 0),
            notes=row["notes"] or "",
        )
