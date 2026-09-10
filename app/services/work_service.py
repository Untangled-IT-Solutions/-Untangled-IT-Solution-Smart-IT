"""Unified Work model persistence service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.task import Task
from app.services.notification_service import NotificationService
from app.services.email_notification_service import EmailNotificationService


class WorkService:
    """Owns all SQLite access for the unified operational work model."""

    WORK_CATEGORIES = (
        "RFQ",
        "Tender",
        "Supplier Registration",
        "Technical",
        "Software",
        "Marketing",
        "Administration",
        "Website",
        "Inventory",
        "Training",
    )

    def __init__(
        self,
        database: Database,
        notification_service: NotificationService | None = None,
        email_service: EmailNotificationService | None = None,
    ) -> None:
        self._database = database
        self._notifications = notification_service
        self._email = email_service

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def create_work(self, task: Task) -> Task:
        """Persist a Work record and update the assigned employee's current task."""
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (
                    title, description, category, assigned_employee, assigned_by,
                    priority, status, department, created_date, start_date, due_date,
                    estimated_hours, actual_hours, checklist, comments, attachments,
                    hardware_serial, external_reference, sprint_bucket,
                    story_points, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    task.title,
                    task.description,
                    task.category,
                    task.assigned_employee,
                    task.assigned_by,
                    task.priority,
                    task.status,
                    task.department,
                    task.start_date,
                    task.due_date,
                    task.estimated_hours,
                    task.actual_hours,
                    task.checklist,
                    task.comments,
                    task.attachments,
                    task.hardware_serial,
                    task.external_reference,
                    task.sprint_bucket,
                    task.story_points,
                ),
            )
            task_id = int(cursor.lastrowid)
            self._sync_employee_current_task(connection, task.assigned_employee)
            self._add_history(connection, task_id, "Created", "Work item created.")
            connection.commit()
            saved = self._get_by_id(task_id, connection)

        self._record_work_activity(saved, "Work created")
        self._notify_assignee(saved)
        return saved

    def get_all_work(
        self,
        search: str = "",
        assigned_employee: str = "All",
        department: str = "All",
        priority: str = "All",
        status: str = "All",
        category: str = "All",
    ) -> list[Task]:
        """Return Work records matching optional operational filters."""
        query = "SELECT * FROM tasks WHERE 1 = 1"
        parameters: list[object] = []

        if search:
            query += (
                " AND (title LIKE ? OR description LIKE ? OR comments LIKE ? "
                "OR hardware_serial LIKE ? OR external_reference LIKE ? "
                "OR category LIKE ? OR assigned_employee LIKE ? OR department LIKE ? OR status LIKE ?)"
            )
            search_pattern = f"%{search}%"
            parameters.extend([search_pattern] * 9)

        filters = (
            ("assigned_employee", assigned_employee),
            ("department", department),
            ("priority", priority),
            ("status", status),
            ("category", category),
        )
        for column, value in filters:
            if value != "All":
                query += f" AND {column} = ?"
                parameters.append(value)

        query += """
            ORDER BY
                CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END,
                due_date ASC,
                created_date DESC,
                id DESC;
        """

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [self._row_to_task(row) for row in rows]

    def get_work(self, task_id: int) -> Task | None:
        """Return one Work record by its identifier."""
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,)).fetchone()
        return self._row_to_task(row) if row is not None else None

    def update_work(self, task: Task) -> Task:
        """Update editable Work details without leaking persistence into views."""
        if task.id is None:
            raise ValueError("A saved Work record is required for an update.")

        with self._connect() as connection:
            previous = self._get_by_id(task.id, connection)
            connection.execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, category = ?, assigned_employee = ?,
                    assigned_by = ?, priority = ?, status = ?, department = ?,
                    start_date = ?, due_date = ?, estimated_hours = ?, actual_hours = ?,
                    checklist = ?, comments = ?, attachments = ?, hardware_serial = ?,
                    external_reference = ?, sprint_bucket = ?, story_points = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    task.title,
                    task.description,
                    task.category,
                    task.assigned_employee,
                    task.assigned_by,
                    task.priority,
                    task.status,
                    task.department,
                    task.start_date,
                    task.due_date,
                    task.estimated_hours,
                    task.actual_hours,
                    task.checklist,
                    task.comments,
                    task.attachments,
                    task.hardware_serial,
                    task.external_reference,
                    task.sprint_bucket,
                    task.story_points,
                    task.id,
                ),
            )
            self._sync_employee_current_task(connection, previous.assigned_employee)
            self._sync_employee_current_task(connection, task.assigned_employee)
            self._add_history(connection, task.id, "Updated", "Work item details updated.")
            connection.commit()
            saved = self._get_by_id(task.id, connection)

        self._record_work_activity(saved, "Work updated")
        if saved.assigned_employee and saved.assigned_employee != previous.assigned_employee:
            self._notify_assignee(saved)
        return saved

    def update_status(self, task_id: int, status: str) -> None:
        """Update one Work record's status."""
        with self._connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (status, task_id),
            )
            task = self._get_by_id(task_id, connection)
            self._sync_employee_current_task(connection, task.assigned_employee)
            self._add_history(connection, task_id, "Status changed", f"Status set to {status}.")
            connection.commit()

        self._record_work_activity(task, f"Work moved to {status}")

    def assign_work(self, task_id: int, assigned_employee: str) -> None:
        """Assign an existing Work record to an employee."""
        with self._connect() as connection:
            previous = self._get_by_id(task_id, connection)
            connection.execute(
                """
                UPDATE tasks
                SET assigned_employee = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (assigned_employee, task_id),
            )
            task = self._get_by_id(task_id, connection)
            self._sync_employee_current_task(connection, previous.assigned_employee)
            self._sync_employee_current_task(connection, assigned_employee)
            self._add_history(connection, task_id, "Assigned", f"Assigned to {assigned_employee}.")
            connection.commit()

        self._record_work_activity(task, f"Work assigned to {assigned_employee}")
        self._notify_assignee(task)

    def delete_work(self, task_id: int) -> None:
        """Remove a Work record and refresh the former assignee's current task."""
        with self._connect() as connection:
            task = self._get_by_id(task_id, connection)
            self._add_history(connection, task_id, "Deleted", "Work item deleted.")
            connection.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
            self._sync_employee_current_task(connection, task.assigned_employee)
            connection.commit()

        if self._notifications is not None:
            self._notifications.record_activity(
                "Work",
                f"Work deleted: {task.title}",
                "Task",
                task_id,
            )

    def get_departments(self) -> list[str]:
        return self._distinct_values("department")

    def get_assigned_employees(self) -> list[str]:
        return self._distinct_values("assigned_employee")

    def get_categories(self) -> list[str]:
        return list(self.WORK_CATEGORIES)

    def get_history(self, task_id: int) -> list["WorkHistory"]:
        """Return the chronological history for a Work record."""
        from app.models.task import WorkHistory

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM work_history
                WHERE task_id = ?
                ORDER BY datetime(created_at) DESC, id DESC;
                """,
                (task_id,),
            ).fetchall()
        return [
            WorkHistory(
                id=row["id"], task_id=row["task_id"], action=row["action"],
                note=row["note"] or "", created_by=row["created_by"] or "",
                created_at=row["created_at"]
            )
            for row in rows
        ]

    def _record_work_activity(self, task: Task, action: str) -> None:
        if self._notifications is None:
            return
        self._notifications.record_activity("Work", f"{action}: {task.title}", "Task", task.id)
        if task.status == "Inbox" and not task.assigned_employee:
            notification_title = "New Sprint Planning task"
            notification_message = (
                f"{task.assigned_by or 'Management'} submitted '{task.title}' "
                "for prioritisation and assignment."
            )
        else:
            notification_title = "Work update"
            notification_message = f"{action}: {task.title}"
        self._notifications.notify_operational(
            ("Operations Manager",),
            notification_title,
            notification_message,
            "Work",
            "Task",
            task.id,
        )

    def _notify_assignee(self, task: Task) -> None:
        if not task.assigned_employee:
            return
        if self._notifications is not None:
            self._notifications.notify_user(
                task.assigned_employee,
                f"You were assigned: {task.title}",
                "Work",
                "New task assignment",
                "Task",
                task.id,
            )
        if self._email is not None:
            self._email.send_task_assignment(task)

    @staticmethod
    def _add_history(
        connection: sqlite3.Connection,
        task_id: int,
        action: str,
        note: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO work_history (task_id, action, note, created_by)
            VALUES (?, ?, ?, 'Operations Manager');
            """,
            (task_id, action, note),
        )

    def _sync_employee_current_task(
        self,
        connection: sqlite3.Connection,
        employee_name: str,
    ) -> None:
        if not employee_name:
            return
        row = connection.execute(
            """
            SELECT title FROM tasks
            WHERE assigned_employee = ?
            AND status NOT IN ('Inbox', 'Completed', 'Cancelled', 'Archived')
            ORDER BY CASE WHEN due_date IS NULL OR due_date = '' THEN 1 ELSE 0 END,
                     due_date ASC, id DESC
            LIMIT 1;
            """,
            (employee_name,),
        ).fetchone()
        current_task = row["title"] if row is not None else "No active task"
        connection.execute(
            "UPDATE employees SET current_task = ? WHERE full_name = ?;",
            (current_task, employee_name),
        )

    def _distinct_values(self, column_name: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT DISTINCT {column_name} FROM tasks WHERE {column_name} IS NOT NULL "
                f"AND {column_name} != '' ORDER BY {column_name} ASC;"
            ).fetchall()
        return [row[column_name] for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    def _get_by_id(self, task_id: int, connection: sqlite3.Connection) -> Task:
        row = connection.execute("SELECT * FROM tasks WHERE id = ?;", (task_id,)).fetchone()
        if row is None:
            raise ValueError(f"Work record {task_id} was not found.")
        return self._row_to_task(row)

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            assigned_employee=row["assigned_employee"] or "",
            assigned_by=row["assigned_by"] or "",
            priority=row["priority"],
            status=row["status"],
            department=row["department"] or "",
            created_date=row["created_date"] or row["created_at"],
            start_date=row["start_date"] or "",
            due_date=row["due_date"] or "",
            estimated_hours=float(row["estimated_hours"] or 0),
            category=row["category"] or "Administration",
            actual_hours=float(row["actual_hours"] or 0),
            comments=row["comments"] or "",
            checklist=row["checklist"] or "[]",
            attachments=row["attachments"] or "[]",
            hardware_serial=row["hardware_serial"] or "",
            external_reference=row["external_reference"] or "",
            sprint_bucket=(
                row["sprint_bucket"] or "Backlog"
                if "sprint_bucket" in row.keys()
                else "Backlog"
            ),
            story_points=(
                int(row["story_points"] or 3)
                if "story_points" in row.keys()
                else 3
            ),
        )
