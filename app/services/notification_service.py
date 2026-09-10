# app/services/notification_service.py
"""Central notification and activity service with sound support.

Fixed so quote-assignment notifications actually reach employees:
- Accepts reference_type / reference_id (no more TypeError)
- Looks up employee by full_name, email, OR username
- Falls back to Staff role when employee is not in local SQLite
  (people data now comes from the backend API)
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path
import platform
import subprocess
import os

from app.database.database import Database
from app.models.notification import Activity, Notification


class NotificationService:
    """Creates role-aware notifications and feeds the dashboard activity stream."""

    DIRECTOR_ROLE = "Director"

    def __init__(self, database: Database) -> None:
        self._database = database
        self._sound_enabled = True
        self._sound_path = self._get_default_sound_path()

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def _get_default_sound_path(self) -> Path:
        """Get the default notification sound path."""
        possible_paths = [
            Path(__file__).parent.parent / "assets" / "notification.wav",
            Path(__file__).parent.parent.parent / "assets" / "notification.wav",
            Path(__file__).parent.parent / "assets" / "sounds" / "notification.wav",
            Path("app/assets/notification.wav"),
            Path("assets/notification.wav"),
            Path("assets/sounds/notification.wav"),
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return possible_paths[0]

    def set_sound_enabled(self, enabled: bool) -> None:
        """Enable or disable notification sounds."""
        self._sound_enabled = enabled

    def set_sound_path(self, path: Path) -> None:
        """Set a custom notification sound path."""
        if path.exists():
            self._sound_path = path

    def _play_sound(self) -> None:
        """Play a notification sound (client-side only)."""
        if not self._sound_enabled:
            return

        try:
            # Prefer the shared SoundManager if available
            try:
                from app.utils.sound import SoundManager
                SoundManager.play_notification_sound(blocking=False)
                return
            except Exception:
                pass

            system = platform.system()

            if system == "Windows":
                try:
                    import winsound
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                except Exception:
                    if self._sound_path.exists():
                        try:
                            import winsound
                            winsound.PlaySound(str(self._sound_path), winsound.SND_FILENAME)
                        except Exception:
                            pass
            elif system == "Darwin":
                if self._sound_path.exists():
                    subprocess.run(["afplay", str(self._sound_path)], capture_output=True)
                else:
                    print("\a", end="", flush=True)
            else:
                if self._sound_path.exists():
                    try:
                        subprocess.run(["aplay", str(self._sound_path)], capture_output=True)
                    except FileNotFoundError:
                        try:
                            subprocess.run(["paplay", str(self._sound_path)], capture_output=True)
                        except FileNotFoundError:
                            print("\a", end="", flush=True)
                else:
                    print("\a", end="", flush=True)
        except Exception as e:
            print(f"⚠️ Could not play notification sound: {e}")

    def notify_operational(
        self,
        recipient_roles: Iterable[str],
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id=None,
        **kwargs,
    ) -> None:
        """Notify operational roles, explicitly excluding the Director."""
        recipients = {
            role.strip()
            for role in recipient_roles
            if role and role.strip() and role.strip() != self.DIRECTOR_ROLE
        }
        if not recipients:
            return

        # reference_id column is INTEGER – only store numeric ids
        ref_id = None
        if reference_id is not None:
            try:
                ref_id = int(reference_id)
            except (TypeError, ValueError):
                ref_id = None

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO notifications (
                    recipient_role, title, message, category, reference_type,
                    reference_id, is_executive, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                """,
                [
                    (role, title, message, category, reference_type or None, ref_id)
                    for role in recipients
                ],
            )
            connection.commit()

        self._play_sound()

    def _find_local_employee(self, identity: str):
        """Look up employee in local SQLite by name, email, or username."""
        if not identity or not str(identity).strip():
            return None
        key = str(identity).strip()
        with self._connect() as connection:
            # Discover available columns (schema may vary)
            cols = {
                row[1]
                for row in connection.execute("PRAGMA table_info(employees)").fetchall()
            }
            clauses = []
            params = []
            if "full_name" in cols:
                clauses.append("full_name = ?")
                params.append(key)
            if "email" in cols:
                clauses.append("LOWER(email) = LOWER(?)")
                params.append(key)
            if "email_address" in cols:
                clauses.append("LOWER(email_address) = LOWER(?)")
                params.append(key)
            if "username" in cols:
                clauses.append("LOWER(username) = LOWER(?)")
                params.append(key)
            if "employee_id" in cols:
                clauses.append("CAST(employee_id AS TEXT) = ?")
                params.append(key)
            if not clauses:
                return None
            sql = f"SELECT * FROM employees WHERE {' OR '.join(clauses)} LIMIT 1"
            return connection.execute(sql, params).fetchone()

    def notify_user(
        self,
        user_name: str,
        message: str,
        category: str = "General",
        title: str = "",
        reference_type: str = "",
        reference_id=None,
        **kwargs,
    ) -> None:
        """Send a notification to a specific user (by name, email, or username).

        Accepts reference_type / reference_id so callers from Quote Management
        no longer raise TypeError. If the employee is not found in the local
        SQLite employees table, a Staff-role notification is still created so
        the employee can see it under the Staff filter.
        """
        try:
            # Put quote reference into the message if we cannot store it as int
            ref_str = str(reference_id).strip() if reference_id else ""
            full_message = message
            if ref_str and ref_str not in message:
                full_message = f"{message} [{ref_str}]"

            ref_id = None
            if reference_id is not None:
                try:
                    ref_id = int(reference_id)
                except (TypeError, ValueError):
                    ref_id = None  # quote refs like UQ-Q7GEW7 are strings

            employee = self._find_local_employee(user_name)
            role = "Staff"
            if employee:
                # sqlite3.Row supports dict-style access
                try:
                    role = employee["role"] or "Staff"
                except (KeyError, IndexError, TypeError):
                    try:
                        role = employee["Role"] or "Staff"
                    except Exception:
                        role = "Staff"
                print(f"✅ Found local employee for notification: {user_name} → role={role}")
            else:
                print(
                    f"ℹ️ User '{user_name}' not in local SQLite employees – "
                    f"creating Staff notification as fallback"
                )

            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO notifications (
                        recipient_role, title, message, category,
                        reference_type, reference_id, is_executive, is_read
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, 0)
                    """,
                    (
                        role,
                        title or category,
                        full_message,
                        category,
                        reference_type or None,
                        ref_id,
                    ),
                )
                connection.commit()

            print(f"✅ Notification created for {user_name} (role={role}, category={category})")
            self._play_sound()

        except Exception as e:
            print(f"⚠️ Failed to send notification: {e}")
            import traceback
            traceback.print_exc()

    def notify_executive(
        self,
        title: str,
        message: str,
        category: str,
        reference_type: str = "",
        reference_id=None,
        **kwargs,
    ) -> None:
        """Send an executive brief to the Director only."""
        ref_id = None
        if reference_id is not None:
            try:
                ref_id = int(reference_id)
            except (TypeError, ValueError):
                ref_id = None
                if reference_id and str(reference_id) not in message:
                    message = f"{message} [{reference_id}]"

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO notifications (
                    recipient_role, title, message, category, reference_type,
                    reference_id, is_executive, is_read
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 0);
                """,
                (
                    self.DIRECTOR_ROLE,
                    title,
                    message,
                    category,
                    reference_type or None,
                    ref_id,
                ),
            )
            connection.commit()

        self._play_sound()

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
        reference_id=None,
    ) -> None:
        """Record one source-neutral operational event for dashboards."""
        ref_id = None
        if reference_id is not None:
            try:
                ref_id = int(reference_id)
            except (TypeError, ValueError):
                ref_id = None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO activity_log (category, description, reference_type, reference_id)
                VALUES (?, ?, ?, ?);
                """,
                (category, description, reference_type or None, ref_id),
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

    def mark_read(self, notification_id) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?;",
                (notification_id,),
            )
            connection.commit()

    def mark_all_read(self, recipient_role: str = "All") -> int:
        """Mark all (optionally role-filtered) notifications as read. Returns count updated."""
        with self._connect() as connection:
            if recipient_role and recipient_role != "All":
                cur = connection.execute(
                    "UPDATE notifications SET is_read = 1 WHERE is_read = 0 AND recipient_role = ?;",
                    (recipient_role,),
                )
            else:
                cur = connection.execute(
                    "UPDATE notifications SET is_read = 1 WHERE is_read = 0;"
                )
            connection.commit()
            return int(cur.rowcount or 0)

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