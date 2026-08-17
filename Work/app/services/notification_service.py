"""Central notification and activity service."""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from app.database.database import Database
from app.models.notification import Activity, Notification


class NotificationService:
    """Creates role-aware notifications and feeds the dashboard activity stream."""

    DIRECTOR_ROLE = "Director"

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def notify_operational(
        self,
        recipient_roles: Iterable[str],
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: int | None = None,
    ) -> None:
        """Notify operational roles, explicitly excluding the Director."""
        recipients = {
            role.strip()
            for role in recipient_roles
            if role and role.strip() and role.strip() != self.DIRECTOR_ROLE
        }
        if not recipients:
            return

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO notifications (
                    recipient_role, title, message, category, reference_type,
                    reference_id, is_executive
                ) VALUES (?, ?, ?, ?, ?, ?, 0);
                """,
                [
                    (role, title, message, category, reference_type, reference_id)
                    for role in recipients
                ],
            )
            connection.commit()

    def notify_executive(
        self,
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id: int | None = None,
    ) -> None:
        """Send an executive brief to the Director only."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notifications (
                    recipient_role, title, message, category, reference_type,
                    reference_id, is_executive
                ) VALUES (?, ?, ?, ?, ?, ?, 1);
                """,
                (
                    self.DIRECTOR_ROLE,
                    title,
                    message,
                    category,
                    reference_type,
                    reference_id,
                ),
            )
            connection.commit()

    def notify_inventory_alert(self, title: str, message: str) -> None:
        """Expose Inventory as a supported source before its module is introduced."""
        self.notify_operational(
            ("Operations Manager",),
            title,
            message,
            "Inventory",
        )
        self.record_activity("Inventory", message, "Inventory", None)

    def notify_compliance_alert(self, title: str, message: str) -> None:
        """Expose Compliance as an executive-brief source."""
        self.notify_executive(title, message, "Compliance")
        self.record_activity("Compliance", message, "Compliance", None)

    def record_activity(
        self,
        category: str,
        description: str,
        reference_type: str = "",
        reference_id: int | None = None,
    ) -> None:
        """Record one source-neutral operational event for dashboards."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO activity_log (category, description, reference_type, reference_id)
                VALUES (?, ?, ?, ?);
                """,
                (category, description, reference_type, reference_id),
            )
            connection.commit()

    def get_notifications(
        self,
        recipient_role: str = "All",
        unread_only: bool = False,
    ) -> list[Notification]:
        """Return notifications appropriate to the selected role view."""
        query = "SELECT * FROM notifications WHERE 1 = 1"
        parameters: list[object] = []
        if recipient_role != "All":
            query += " AND recipient_role = ?"
            parameters.append(recipient_role)
            query += " AND is_executive = ?"
            parameters.append(1 if recipient_role == self.DIRECTOR_ROLE else 0)
        if unread_only:
            query += " AND is_read = 0"
        query += " ORDER BY datetime(created_at) DESC, id DESC;"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._row_to_notification(row) for row in rows]

    def get_latest_activity(self, limit: int = 6) -> tuple[Activity, ...]:
        """Return latest actions in reverse chronological order."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM activity_log
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ?;
                """,
                (limit,),
            ).fetchall()
        return tuple(self._row_to_activity(row) for row in rows)

    def mark_read(self, notification_id: int) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE notifications SET is_read = 1 WHERE id = ?;", (notification_id,))
            connection.commit()

    def count_unread(self, category: str | None = None) -> int:
        query = "SELECT COUNT(*) FROM notifications WHERE is_read = 0"
        parameters: tuple[object, ...] = ()
        if category:
            query += " AND category = ?"
            parameters = (category,)
        with self._connect() as connection:
            return int(connection.execute(query, parameters).fetchone()[0])

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]

    @staticmethod
    def _row_to_notification(row: sqlite3.Row) -> Notification:
        return Notification(
            id=row["id"],
            recipient_role=row["recipient_role"],
            title=row["title"],
            message=row["message"],
            category=row["category"],
            reference_type=row["reference_type"] or "",
            reference_id=row["reference_id"],
            is_executive=bool(row["is_executive"]),
            is_read=bool(row["is_read"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_activity(row: sqlite3.Row) -> Activity:
        return Activity(
            id=row["id"],
            category=row["category"],
            description=row["description"],
            reference_type=row["reference_type"] or "",
            reference_id=row["reference_id"],
            created_at=row["created_at"],
        )
