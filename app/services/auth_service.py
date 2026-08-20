"""Authentication, account administration, and session service."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database.database import Database
from app.models.account import AuthSession, UserAccount
from app.models.role_permission import can_administer_accounts


class AuthService:
    """Owns secure login, session state, and employee-linked user accounts."""

    _TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    _HASH_ALGORITHM = "pbkdf2_sha256"
    _HASH_ITERATIONS = 260000
    _ACTIVE = "active"
    _INACTIVE = "inactive"

    def __init__(self, database: Database) -> None:
        self._database = database
        self._current_session: AuthSession | None = None

    @property
    def current_session(self) -> AuthSession | None:
        return self._current_session

    @property
    def current_account(self) -> UserAccount | None:
        return self._current_session.account if self._current_session else None

    @property
    def current_employee_id(self) -> int | None:
        return self._current_session.employee_id if self._current_session else None

    @property
    def current_role(self) -> str:
        return self._current_session.role if self._current_session else "Anonymous"

    def authenticate(self, username: str, password: str) -> AuthSession:
        """Validate credentials, block inactive accounts, and create a session."""
        username = username.strip().lower()
        if not username or not password:
            raise ValueError("Invalid username or password.")

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT users.*, employees.full_name AS employee_full_name
                FROM users
                JOIN employees ON employees.id = users.employee_id
                WHERE lower(users.username) = ?;
                """,
                (username,),
            ).fetchone()
            if row is None or not self.verify_password(password, row["password_hash"]):
                raise ValueError("Invalid username or password.")
            if str(row["status"]).lower() != self._ACTIVE:
                raise ValueError("This account is inactive. Contact a manager.")

            now = self._format_time(self._now())
            connection.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?;",
                (now, now, row["id"]),
            )
            cursor = connection.execute(
                """
                INSERT INTO auth_sessions (user_id, employee_id, login_at, last_activity_at)
                VALUES (?, ?, ?, ?);
                """,
                (row["id"], row["employee_id"], now, now),
            )
            connection.commit()
            account_row = connection.execute(
                """
                SELECT users.*, employees.full_name AS employee_full_name
                FROM users
                JOIN employees ON employees.id = users.employee_id
                WHERE users.id = ?;
                """,
                (row["id"],),
            ).fetchone()

        account = self._row_to_account(account_row)
        self._current_session = AuthSession(
            id=int(cursor.lastrowid),
            account=account,
            login_at=now,
            last_activity_at=now,
        )
        return self._current_session

    def logout(self) -> None:
        """Close the current session if one exists."""
        if self._current_session is None:
            return
        now = self._format_time(self._now())
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE auth_sessions
                SET logout_at = ?, last_activity_at = ?
                WHERE id = ?;
                """,
                (now, now, self._current_session.id),
            )
        self._current_session = None

    def touch(self) -> None:
        """Refresh session activity timestamp."""
        if self._current_session is None:
            return
        now = self._format_time(self._now())
        with self._connect() as connection:
            connection.execute(
                "UPDATE auth_sessions SET last_activity_at = ? WHERE id = ?;",
                (now, self._current_session.id),
            )
        self._current_session = AuthSession(
            id=self._current_session.id,
            account=self._current_session.account,
            login_at=self._current_session.login_at,
            last_activity_at=now,
            logout_at=self._current_session.logout_at,
        )

    def require_authenticated(self) -> AuthSession:
        """Return the current session or reject unauthenticated access."""
        if self._current_session is None:
            raise PermissionError("Login is required.")
        return self._current_session

    def require_account_admin(self) -> AuthSession:
        """Return the current session only for account administrators."""
        session = self.require_authenticated()
        if not can_administer_accounts(session.role):
            raise PermissionError("You are not allowed to administer accounts.")
        return session

    def bootstrap_employee_accounts(
        self,
        initial_password: str | None = None,
        activate: bool | None = None,
    ) -> list[UserAccount]:
        """Create missing accounts from employees without hard-coding a password.

        If ``initial_password`` is absent, ``UNTANGLED_BOOTSTRAP_PASSWORD`` is used.
        Accounts are activated only when a password is supplied or ``activate`` is
        explicitly true. This lets development setup be deliberate while keeping
        employee records as the identity source of truth.
        """
        password = initial_password or os.environ.get("UNTANGLED_BOOTSTRAP_PASSWORD", "")
        should_activate = bool(password) if activate is None else activate
        status = self._ACTIVE if should_activate else self._INACTIVE
        password_hash = self.hash_password(password) if password else self.hash_password(secrets.token_urlsafe(32))

        with self._connect() as connection:
            employees = connection.execute(
                "SELECT id, full_name, email, position, role FROM employees ORDER BY id ASC;"
            ).fetchall()
            for employee in employees:
                exists = connection.execute(
                    "SELECT id, last_login_at FROM users WHERE employee_id = ?;",
                    (employee["id"],),
                ).fetchone()
                if exists is not None:
                    if password and should_activate and not exists["last_login_at"]:
                        connection.execute(
                            """
                            UPDATE users
                            SET password_hash = ?, status = ?, updated_at = ?
                            WHERE id = ?;
                            """,
                            (password_hash, self._ACTIVE, self._format_time(self._now()), exists["id"]),
                        )
                    continue
                username = self._username_for(employee["full_name"])
                connection.execute(
                    """
                    INSERT INTO users (
                        employee_id, username, full_name, email, password_hash,
                        role, department, status, created_at, updated_at
                    )
                    SELECT ?, ?, ?, COALESCE(NULLIF(email, ''), ?), ?, ?, department, ?, ?, ?
                    FROM employees
                    WHERE id = ?;
                    """,
                    (
                        employee["id"],
                        username,
                        employee["full_name"],
                        f"{username}@untangled.local",
                        password_hash,
                        self._account_role(employee["full_name"], employee["role"], employee["position"]),
                        status,
                        self._format_time(self._now()),
                        self._format_time(self._now()),
                        employee["id"],
                    ),
                )
            connection.commit()
        return self.list_accounts()

    def ensure_demo_account(
        self,
        username: str = "siyandaN@untangled.co.za",
        password: str = "Password@untangled123",
    ) -> UserAccount:
        """Create or update the development demo account.

        The account is linked to a dedicated employee record so it works with
        the employee JOIN used by authenticate(). The password is stored using
        the same PBKDF2 scheme as all other accounts.
        """
        username = username.strip().lower()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")

        now = self._format_time(self._now())

        with self._connect() as connection:
            # Check if employee exists
            employee = connection.execute(
                "SELECT id, full_name, email, department FROM employees "
                "WHERE lower(email) = ? OR lower(full_name) = ? LIMIT 1;",
                (username, "demo admin"),
            ).fetchone()

            if employee is None:
                # Create demo employee with required employee_number
                cursor = connection.execute(
                    """
                    INSERT INTO employees (
                        employee_number, first_name, last_name, full_name, 
                        position, role, department, email, status,
                        employment_type, date_joined, clocked_in, current_task,
                        skills, permissions, performance_score, training_progress
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        "DEMO-001",  # employee_number - REQUIRED
                        "Demo",      # first_name
                        "Admin",     # last_name
                        "Demo Admin",
                        "Demo Administrator",
                        "Director",
                        "Administration",
                        username,    # email
                        "Active",
                        "Full Time",
                        "2026-08-12",
                        0,           # clocked_in
                        "No active task",
                        "Leadership, Development",
                        "Full Access",
                        100.0,       # performance_score
                        100.0        # training_progress
                    ),
                )
                employee_id = int(cursor.lastrowid)
                full_name = "Demo Admin"
                department = "Administration"
                print(f"✅ Created demo employee with ID: {employee_id}")
            else:
                employee_id = int(employee["id"])
                full_name = employee["full_name"]
                department = employee["department"]
                print(f"✅ Found existing demo employee with ID: {employee_id}")

            password_hash = self.hash_password(password)

            # Check if user exists
            existing = connection.execute(
                "SELECT id, status, role FROM users WHERE lower(username) = ?;",
                (username,),
            ).fetchone()

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO users (
                        employee_id, username, full_name, email,
                        password_hash, role, department, status,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        employee_id,
                        username,
                        full_name,
                        username,
                        password_hash,
                        "Director",
                        department,
                        self._ACTIVE,
                        now,
                        now,
                    ),
                )
                print(f"✅ Created demo user: {username}")
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET employee_id = ?,
                        full_name = ?,
                        email = ?,
                        password_hash = ?,
                        role = ?,
                        department = ?,
                        status = ?,
                        updated_at = ?
                    WHERE id = ?;
                    """,
                    (
                        employee_id,
                        full_name,
                        username,
                        password_hash,
                        "Director",
                        department,
                        self._ACTIVE,
                        now,
                        existing["id"],
                    ),
                )
                print(f"✅ Updated demo user: {username}")

            connection.commit()

            # Retrieve the complete account
            row = connection.execute(
                """
                SELECT users.*, employees.full_name AS employee_full_name
                FROM users
                JOIN employees ON employees.id = users.employee_id
                WHERE lower(users.username) = ?;
                """,
                (username,),
            ).fetchone()

        if row is None:
            raise RuntimeError(f"Failed to create or retrieve demo account: {username}")

        return self._row_to_account(row)

    def list_accounts(self) -> list[UserAccount]:
        """Return all account identities."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT users.*, employees.full_name AS employee_full_name
                FROM users
                JOIN employees ON employees.id = users.employee_id
                ORDER BY employees.id ASC;
                """
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    def create_account(
        self,
        employee_id: int,
        username: str,
        password: str,
        role: str,
        active: bool = True,
    ) -> UserAccount:
        self.require_account_admin()
        return self._create_or_update_account(employee_id, username, password, role, active)

    def reset_password(self, user_id: int, new_password: str) -> None:
        self.require_account_admin()
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        now = self._format_time(self._now())
        with self._connect() as connection:
            self._require_user(connection, user_id)
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?;",
                (self.hash_password(new_password), now, user_id),
            )

    def set_account_status(self, user_id: int, active: bool) -> None:
        self.require_account_admin()
        now = self._format_time(self._now())
        with self._connect() as connection:
            self._require_user(connection, user_id)
            connection.execute(
                "UPDATE users SET status = ?, updated_at = ? WHERE id = ?;",
                (self._ACTIVE if active else self._INACTIVE, now, user_id),
            )

    def change_role(self, user_id: int, role: str) -> None:
        self.require_account_admin()
        now = self._format_time(self._now())
        with self._connect() as connection:
            self._require_user(connection, user_id)
            connection.execute(
                "UPDATE users SET role = ?, updated_at = ? WHERE id = ?;",
                (role, now, user_id),
            )

    def link_employee(self, user_id: int, employee_id: int) -> None:
        self.require_account_admin()
        now = self._format_time(self._now())
        with self._connect() as connection:
            self._require_user(connection, user_id)
            employee = connection.execute(
                "SELECT full_name FROM employees WHERE id = ?;",
                (employee_id,),
            ).fetchone()
            if employee is None:
                raise ValueError("Employee was not found.")
            connection.execute(
                """
                UPDATE users
                SET employee_id = ?, full_name = ?, updated_at = ?
                WHERE id = ?;
                """,
                (employee_id, employee["full_name"], now, user_id),
            )

    def _create_or_update_account(
        self,
        employee_id: int,
        username: str,
        password: str,
        role: str,
        active: bool,
    ) -> UserAccount:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        username = username.strip().lower()
        if not username:
            raise ValueError("Username is required.")
        now = self._format_time(self._now())
        with self._connect() as connection:
            employee = connection.execute(
                "SELECT id, full_name, email, department FROM employees WHERE id = ?;",
                (employee_id,),
            ).fetchone()
            if employee is None:
                raise ValueError("Employee was not found.")
            try:
                connection.execute(
                    """
                    INSERT INTO users (
                        employee_id, username, full_name, email, password_hash,
                        role, department, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        employee_id,
                        username,
                        employee["full_name"],
                        employee["email"] or f"{username}@untangled.local",
                        self.hash_password(password),
                        role,
                        employee["department"],
                        self._ACTIVE if active else self._INACTIVE,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("An account already exists for that username or employee.") from error
            connection.commit()
            row = connection.execute(
                """
                SELECT users.*, employees.full_name AS employee_full_name
                FROM users
                JOIN employees ON employees.id = users.employee_id
                WHERE users.employee_id = ?;
                """,
                (employee_id,),
            ).fetchone()
        return self._row_to_account(row)

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Return a PBKDF2 hash string for storage."""
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            cls._HASH_ITERATIONS,
        ).hex()
        return f"{cls._HASH_ALGORITHM}${cls._HASH_ITERATIONS}${salt}${digest}"

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        """Verify a password without exposing timing differences."""
        try:
            algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != cls._HASH_ALGORITHM:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)

    @staticmethod
    def _account_role(full_name: str, employee_role: str, position: str) -> str:
        if full_name == "Zandile Johanna Maredi":
            return "Director"
        if full_name == "Benny Moremi":
            return "Branch Manager"
        if full_name == "Ubuntu Hadebe":
            return "Operations Manager"
        if "Intern" in position:
            return "Intern"
        return "Staff" if employee_role not in {"Director", "Branch Manager", "Operations Manager"} else employee_role

    @staticmethod
    def _username_for(full_name: str) -> str:
        parts = [part for part in full_name.lower().replace("&", "and").split() if part]
        return ".".join(parts[:2]) if len(parts) >= 2 else full_name.strip().lower()

    @staticmethod
    def _require_user(connection: sqlite3.Connection, user_id: int) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM users WHERE id = ?;", (user_id,)).fetchone()
        if row is None:
            raise ValueError("Account was not found.")
        return row

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> UserAccount:
        return UserAccount(
            id=row["id"],
            employee_id=row["employee_id"],
            username=row["username"],
            full_name=row["employee_full_name"] or row["full_name"],
            role=row["role"],
            status=row["status"],
            last_login_at=row["last_login_at"] or "",
        )

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()

    @classmethod
    def _format_time(cls, value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime(cls._TIME_FORMAT)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(microsecond=0)