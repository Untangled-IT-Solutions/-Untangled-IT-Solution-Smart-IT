"""Database-backed Projects module service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.project import Project


class ProjectService:
    """Provides project progress, members, milestones, and activity data."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def get_projects(self) -> list[Project]:
        with self._connect() as connection:
            self._seed_from_work(connection)
            rows = connection.execute(
                "SELECT * FROM projects ORDER BY status ASC, name ASC;"
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def _seed_from_work(self, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT category, department, COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS done,
                   GROUP_CONCAT(DISTINCT assigned_employee) AS members,
                   MIN(due_date) AS first_due, MAX(due_date) AS last_due
            FROM tasks
            WHERE category IN ('Software', 'Website', 'Technical', 'RFQ', 'Tender')
            GROUP BY category, department;
            """
        ).fetchall()
        for row in rows:
            if not row["category"]:
                continue
            progress = int((row["done"] or 0) / max(row["total"] or 1, 1) * 100)
            name = f"{row['department'] or 'General'} {row['category']} Program"
            status = "Completed" if progress == 100 else "Active"
            existing = connection.execute(
                "SELECT id FROM projects WHERE name = ?;", (name,)
            ).fetchone()
            values = (
                status,
                progress,
                row["members"] or "Unassigned",
                f"{row['total']} work items | {row['done'] or 0} complete",
                f"{row['first_due'] or 'No start'} to {row['last_due'] or 'No deadline'}",
                "Updated from current Work records",
            )
            if existing:
                connection.execute(
                    """
                    UPDATE projects
                    SET status = ?, progress = ?, members = ?, milestones = ?,
                        timeline = ?, activity_feed = ?
                    WHERE id = ?;
                    """,
                    (*values, existing["id"]),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO projects (
                        name, description, status, department, progress, members,
                        milestones, timeline, documents, activity_feed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        name,
                        f"Auto-tracked {row['category']} work stream.",
                        status,
                        row["department"] or "General",
                        progress,
                        row["members"] or "Unassigned",
                        f"{row['total']} work items | {row['done'] or 0} complete",
                        f"{row['first_due'] or 'No start'} to {row['last_due'] or 'No deadline'}",
                        "Linked Work attachments",
                        "Updated from current Work records",
                    ),
                )

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            status=row["status"],
            department=row["department"] or "",
            progress=int(row["progress"] or 0),
            members=row["members"] or "",
            milestones=row["milestones"] or "",
            timeline=row["timeline"] or "",
            budget_placeholder=row["budget_placeholder"] or "Budget pending",
            documents=row["documents"] or "",
            activity_feed=row["activity_feed"] or "",
        )
