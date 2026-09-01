"""SQLite database initialization."""

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path


class Database:
    """Creates and manages the local SQLite database file."""

    def __init__(self, db_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.db_path = db_path or project_root / "data" / "untangled_nexus.db"

    def initialize(self) -> None:
        """Create the database and required tables when missing."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as connection:
            connection.execute("PRAGMA foreign_keys = ON;")
            self._create_tables(connection)
            self._migrate_existing_tables(connection)
            self._create_indexes(connection)
            self._normalise_work_categories(connection)
            self._seed_departments(connection)
            self._seed_employees(connection)
            self._apply_timestamp_migrations(connection)
            self._migrate_legacy_work_items(connection)

    def connection(self) -> sqlite3.Connection:
        """Return a database connection (non-context manager version for AuthService)."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a SQLite connection that is always closed on every platform."""
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA journal_mode = WAL;")
        connection.execute("PRAGMA synchronous = NORMAL;")
        connection.execute("PRAGMA busy_timeout = 10000;")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_tables(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                username TEXT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                department TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                last_login_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                login_at TEXT NOT NULL,
                logout_at TEXT,
                last_activity_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                assigned_to INTEGER,
                created_by INTEGER,
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                assigned_employee TEXT,
                assigned_by TEXT,
                department TEXT,
                created_date TEXT,
                start_date TEXT,
                estimated_hours REAL NOT NULL DEFAULT 0,
                actual_hours REAL NOT NULL DEFAULT 0,
                comments TEXT,
                category TEXT NOT NULL DEFAULT 'Administration',
                checklist TEXT NOT NULL DEFAULT '[]',
                attachments TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT,
                legacy_work_item_id INTEGER UNIQUE,
                FOREIGN KEY (assigned_to) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_number TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                full_name TEXT NOT NULL,
                position TEXT NOT NULL,
                department TEXT NOT NULL,
                role TEXT NOT NULL,
                reports_to TEXT,
                mentor TEXT,
                email TEXT,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                employment_type TEXT NOT NULL DEFAULT 'Full Time',
                date_joined TEXT,
                clocked_in INTEGER NOT NULL DEFAULT 0,
                current_task TEXT,
                profile_photo TEXT,
                skills TEXT,
                permissions TEXT,
                performance_score REAL NOT NULL DEFAULT 0,
                training_progress REAL NOT NULL DEFAULT 0,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                department TEXT,
                progress INTEGER NOT NULL DEFAULT 0,
                members TEXT NOT NULL DEFAULT '',
                milestones TEXT NOT NULL DEFAULT '',
                timeline TEXT NOT NULL DEFAULT '',
                budget_placeholder TEXT NOT NULL DEFAULT 'Budget pending',
                documents TEXT NOT NULL DEFAULT '',
                activity_feed TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS work_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                assigned_to TEXT,
                department TEXT,
                due_date TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                work_date TEXT NOT NULL,
                clock_in_at TEXT,
                clock_out_at TEXT,
                break_started_at TEXT,
                break_duration_minutes INTEGER NOT NULL DEFAULT 0,
                hours_worked REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(employee_id, work_date),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            );

            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                department TEXT,
                details TEXT,
                source_type TEXT NOT NULL DEFAULT 'Manual',
                source_id INTEGER,
                recurrence TEXT NOT NULL DEFAULT 'None',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                request_type TEXT NOT NULL,
                description TEXT,
                requested_by TEXT NOT NULL,
                department TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Pending',
                current_stage TEXT NOT NULL DEFAULT 'Operations Manager',
                requires_director INTEGER NOT NULL DEFAULT 0,
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                manager_approved_by TEXT,
                business_approved_by TEXT,
                director_approved_by TEXT,
                rejection_reason TEXT
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_role TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                category TEXT NOT NULL,
                reference_type TEXT,
                reference_id INTEGER,
                is_executive INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                reference_type TEXT,
                reference_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS work_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                note TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS office_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                requested_by TEXT NOT NULL,
                department TEXT NOT NULL,
                notes TEXT,
                approval_id INTEGER NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (approval_id) REFERENCES approvals(id)
            );

            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                status TEXT NOT NULL DEFAULT 'Active'
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_name TEXT,
                email TEXT,
                status TEXT NOT NULL DEFAULT 'Active'
            );

            -- Quotes table for managing customer quotes from website
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                company TEXT,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                notes TEXT,
                items TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'Pending',
                reply_message TEXT,
                replied_at TEXT,
                assigned_to TEXT,
                assigned_at TEXT,
                task_id INTEGER,
                internal_notes TEXT DEFAULT '[]',
                last_sync_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE INDEX IF NOT EXISTS idx_quotes_reference ON quotes(reference);
            CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);
            """
        )

    def _migrate_existing_tables(self, connection: sqlite3.Connection) -> None:
        """Add Sprint 2 columns when a database was created by an earlier sprint."""
        self._ensure_columns(
            connection,
            "tasks",
            {
                "assigned_employee": "TEXT",
                "assigned_by": "TEXT",
                "department": "TEXT",
                "created_date": "TEXT",
                "start_date": "TEXT",
                "estimated_hours": "REAL NOT NULL DEFAULT 0",
                "actual_hours": "REAL NOT NULL DEFAULT 0",
                "comments": "TEXT",
                "category": "TEXT NOT NULL DEFAULT 'Administration'",
                "checklist": "TEXT NOT NULL DEFAULT '[]'",
                "attachments": "TEXT NOT NULL DEFAULT '[]'",
                "updated_at": "TEXT",
                "legacy_work_item_id": "INTEGER",
            },
        )
        self._ensure_columns(connection, "employees", {"permissions": "TEXT"})
        self._ensure_columns(
            connection,
            "users",
            {
                "employee_id": "INTEGER",
                "username": "TEXT",
                "last_login_at": "TEXT",
                "updated_at": "TEXT",
            },
        )
        self._ensure_columns(
            connection,
            "calendar_events",
            {"recurrence": "TEXT NOT NULL DEFAULT 'None'"},
        )
        self._ensure_columns(
            connection,
            "projects",
            {
                "progress": "INTEGER NOT NULL DEFAULT 0",
                "members": "TEXT NOT NULL DEFAULT ''",
                "milestones": "TEXT NOT NULL DEFAULT ''",
                "timeline": "TEXT NOT NULL DEFAULT ''",
                "budget_placeholder": "TEXT NOT NULL DEFAULT 'Budget pending'",
                "documents": "TEXT NOT NULL DEFAULT ''",
                "activity_feed": "TEXT NOT NULL DEFAULT ''",
            },
        )

    @staticmethod
    def _create_indexes(connection: sqlite3.Connection) -> None:
        """Create indexes after additive column migrations have completed."""
        connection.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique
            ON users(username)
            WHERE username IS NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_employee_unique
            ON users(employee_id)
            WHERE employee_id IS NOT NULL;
            """
        )

    @staticmethod
    def _normalise_work_categories(connection: sqlite3.Connection) -> None:
        """Map pre-v0.3 category names into the shared Work category vocabulary."""
        connection.execute(
            "UPDATE tasks SET category = 'Technical' WHERE category = 'Technical Job';"
        )
        connection.execute(
            "UPDATE tasks SET category = 'Software' WHERE category = 'Software Development';"
        )

    def _ensure_columns(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        columns: dict[str, str],
    ) -> None:
        existing_columns = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table_name});")
        }

        for column_name, column_definition in columns.items():
            if column_name not in existing_columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition};"
                )

    def _seed_departments(self, connection: sqlite3.Connection) -> None:
        """Seed the organisational departments used by the first operational modules."""
        departments = (
            ("Executive", "Executive leadership and governance."),
            ("Management", "Business leadership and approvals."),
            ("Operations", "Daily operational coordination."),
            ("Technical", "Technical support and field services."),
            ("Administration", "Administration and supplier registration."),
            ("Marketing", "Marketing and RFQ support."),
            ("Software Development", "Software delivery and automation."),
            ("Inventory", "Stock, equipment, and procurement."),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?);",
            departments,
        )

    def _seed_employees(self, connection: sqlite3.Connection) -> None:
        """Seed the initial Untangled IT Solutions team once."""
        employees = (
            {
                "employee_number": "UTS-001",
                "first_name": "Zandile Johanna",
                "last_name": "Maredi",
                "full_name": "Zandile Johanna Maredi",
                "position": "Director",
                "department": "Executive",
                "role": "Director",
                "reports_to": "None",
                "mentor": "None",
                "skills": "Leadership, Strategy, Governance",
                "permissions": "Executive Briefs, Company Health, Compliance",
                "performance_score": 95,
                "training_progress": 100,
            },
            {
                "employee_number": "UTS-002",
                "first_name": "Benny",
                "last_name": "Moremi",
                "full_name": "Benny Moremi",
                "position": "Business Lead",
                "department": "Management",
                "role": "Business Lead",
                "reports_to": "Director",
                "mentor": "Director",
                "skills": "Business Development, Approvals, Reporting",
                "permissions": "Approvals, Reports, Operations",
                "performance_score": 88,
                "training_progress": 82,
            },
            {
                "employee_number": "UTS-003",
                "first_name": "Ubuntu",
                "last_name": "Hadebe",
                "full_name": "Ubuntu Hadebe",
                "position": "Operations Manager",
                "department": "Operations",
                "role": "Operations Manager",
                "reports_to": "Business Lead",
                "mentor": "Business Lead",
                "skills": "Operations, Staff Management, Task Assignment",
                "permissions": "Manage Staff, Assign Work, Edit Work, View Reports",
                "performance_score": 91,
                "training_progress": 86,
            },
            {
                "employee_number": "UTS-004",
                "first_name": "Gift",
                "last_name": "Wesi",
                "full_name": "Gift Wesi",
                "position": "Senior Technician",
                "department": "Technical",
                "role": "Senior Technician",
                "reports_to": "Operations Manager",
                "mentor": "Ubuntu Hadebe",
                "skills": "Technical Support, Field Work, Mentoring",
                "permissions": "View Own Work, Update Own Work Status",
                "performance_score": 84,
                "training_progress": 74,
            },
            {
                "employee_number": "UTS-005",
                "first_name": "Dipuo",
                "last_name": "Tlowana",
                "full_name": "Dipuo Tlowana",
                "position": "RFQ Administrator",
                "department": "Administration",
                "role": "RFQ Administrator",
                "reports_to": "Operations Manager",
                "mentor": "Ubuntu Hadebe",
                "skills": "RFQ Administration, Documentation, Coordination",
                "permissions": "View Own Work, Update Own Work Status",
                "performance_score": 82,
                "training_progress": 68,
            },
            {
                "employee_number": "UTS-006",
                "first_name": "Bongiwe",
                "last_name": "Ngobese",
                "full_name": "Bongiwe Ngobese",
                "position": "Marketing & RFQ Support",
                "department": "Marketing",
                "role": "Marketing & RFQ Support",
                "reports_to": "Operations Manager",
                "mentor": "Ubuntu Hadebe",
                "skills": "Marketing, RFQ Support, Client Communication",
                "permissions": "View Own Work, Update Own Work Status",
                "performance_score": 80,
                "training_progress": 70,
            },
            {
                "employee_number": "UTS-007",
                "first_name": "Siyanda",
                "last_name": "Nkosi",
                "full_name": "Siyanda Nkosi",
                "position": "Software Engineer",
                "department": "Software Development",
                "role": "Software Engineer",
                "reports_to": "Operations Manager",
                "mentor": "Gift Wesi",
                "skills": "Python, Desktop Apps, Automation",
                "permissions": "View Own Work, Update Own Work Status",
                "performance_score": 78,
                "training_progress": 65,
            },
            {
                "employee_number": "UTS-008",
                "first_name": "Nonhlanhla",
                "last_name": "Hlatshwayo",
                "full_name": "Nonhlanhla Hlatshwayo",
                "position": "Technical Support Intern",
                "department": "Technical",
                "role": "Technical Support Intern",
                "reports_to": "Operations Manager",
                "mentor": "Gift Wesi",
                "skills": "Technical Support, Troubleshooting, Learning",
                "permissions": "View Own Work, Update Own Work Status",
                "performance_score": 72,
                "training_progress": 45,
            },
        )

        for employee in employees:
            email_name = employee["full_name"].lower().replace(" ", ".")
            connection.execute(
                """
                INSERT OR IGNORE INTO employees (
                    employee_number,
                    first_name,
                    last_name,
                    full_name,
                    position,
                    department,
                    role,
                    reports_to,
                    mentor,
                    email,
                    phone,
                    status,
                    employment_type,
                    date_joined,
                    clocked_in,
                    current_task,
                    profile_photo,
                    skills,
                    permissions,
                    performance_score,
                    training_progress,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    employee["employee_number"],
                    employee["first_name"],
                    employee["last_name"],
                    employee["full_name"],
                    employee["position"],
                    employee["department"],
                    employee["role"],
                    employee["reports_to"],
                    employee["mentor"],
                    f"{email_name}@untangleditsolutions.co.za",
                    "",
                    "Active",
                    "Full Time",
                    "2026-08-03",
                    0,
                    "No active task",
                    "",
                    employee["skills"],
                    employee["permissions"],
                    employee["performance_score"],
                    employee["training_progress"],
                    "",
                ),
            )
            connection.execute(
                """
                UPDATE employees
                SET permissions = ?
                WHERE employee_number = ?
                AND (permissions IS NULL OR permissions = '');
                """,
                (employee["permissions"], employee["employee_number"]),
            )

    def _apply_timestamp_migrations(self, connection: sqlite3.Connection) -> None:
        """Normalize known app-managed timestamps to UTC and mark the migration complete."""
        current_version = connection.execute("PRAGMA user_version;").fetchone()[0]
        if current_version >= 1:
            return

        local_tz = datetime.now().astimezone().tzinfo
        time_format = "%Y-%m-%d %H:%M:%S"

        def convert(value: str) -> str:
            if not value:
                return ""
            try:
                local_dt = datetime.strptime(value, time_format).replace(tzinfo=local_tz)
            except ValueError:
                return value
            return local_dt.astimezone(timezone.utc).strftime(time_format)

        for row in connection.execute(
            "SELECT id, clock_in_at, clock_out_at, break_started_at, created_at, updated_at FROM attendance_records;"
        ).fetchall():
            connection.execute(
                """
                UPDATE attendance_records
                SET clock_in_at = ?, clock_out_at = ?, break_started_at = ?,
                    created_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (
                    convert(row["clock_in_at"]),
                    convert(row["clock_out_at"]),
                    convert(row["break_started_at"]),
                    convert(row["created_at"]),
                    convert(row["updated_at"]),
                    row["id"],
                ),
            )

        for row in connection.execute("SELECT id, created_at FROM calendar_events;").fetchall():
            connection.execute(
                """
                UPDATE calendar_events
                SET created_at = ?
                WHERE id = ?;
                """,
                (convert(row["created_at"]), row["id"]),
            )

        connection.execute("PRAGMA user_version = 1;")

    def _migrate_legacy_work_items(self, connection: sqlite3.Connection) -> None:
        """Import earlier Sprint work records once into the unified tasks table."""
        rows = connection.execute("SELECT * FROM work_items ORDER BY id ASC;").fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT OR IGNORE INTO tasks (
                    title, description, category, priority, status, assigned_employee,
                    department, due_date, created_date, updated_at, legacy_work_item_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[0],
                ),
            )