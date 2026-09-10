"""Database-backed Projects workspace service."""

from __future__ import annotations

import re
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.database.database import Database
from app.models.project import Project, ProjectDocument, ProjectUpdate


class ProjectService:
    """Store project profiles, documents, and chronological updates."""

    DEFAULT_PROJECTS = (
        {
            "name": "Untangled Main Website",
            "description": (
                "Enterprise ICT Partner — the official Untangled IT Solutions company "
                "website and e-commerce presence. Untangled IT Solutions was founded in "
                "2016 to help public- and private-sector organisations simplify complex "
                "technology environments through practical, reliable ICT products and "
                "services. The website presents the company story, mission, vision, "
                "leadership, solutions, testimonials, contact information and online store.\n\n"
                "Leadership and delivery: Director Zandile Maredi and Head of Business "
                "Development Benny Moremi bring ICT and customer-relations experience to "
                "each engagement. The company delivers enterprise hardware and support "
                "across Dell, Lenovo and HP solutions, including laptops, workstations, "
                "desktops, monitors, accessories, lifecycle care and hardware/software "
                "troubleshooting. Responsible device lifecycle practices are being "
                "strengthened through the EWASA registration journey.\n\n"
                "Mission: enable private- and public-sector clients with appropriate "
                "technology knowledge and tools that strengthen competitiveness. Vision: "
                "be a preferred ICT solutions provider in South Africa through continuous "
                "improvement and customer satisfaction. The delivery approach is reliable, "
                "responsive and scalable, aligning technology decisions to each client's "
                "operational priorities. Website: www.untangledits.co.za. Contact: "
                "sales@untangledits.co.za, accounts@untangledits.co.za, 011 664 6500. "
                "Office: Renaissance Centre, 16–20 New Street South, Gandhi Square, Office 502."
            ),
            "status": "Active",
            "department": "Software Development",
            "category": "Internal Project",
            "owner": "Untangled IT Solutions Leadership",
            "members": "Zandile Maredi, Benny Moremi, Ubuntu Hadebe, Website Delivery Team",
            "milestones": (
                "Maintain Home, About, Solutions, Testimonials and Contact pages; maintain "
                "the online Store; integrate e-commerce and customer requests; validate "
                "company information; test accessibility and navigation; maintain Terms and "
                "Conditions and Refund/Cancellation policy pages; publish approved updates"
            ),
            "timeline": "Established in 2016; current website programme maintained through 2026 and beyond",
        },
        {
            "name": "Untangled Nexus",
            "description": (
                "Internal operations platform covering employees, attendance, tasks, "
                "sprints, calendar, notifications, approvals, and reporting."
            ),
            "status": "Active",
            "department": "Operations",
            "category": "Internal Project",
            "owner": "Ubuntu Hadebe",
            "members": (
                "Ubuntu Hadebe, Siyanda Nkosi, Nonhlanhla Hlatshwayo, Gift Wesi, "
                "Dipuo Tlowana, Bongiwe Ngobese, Botshelo Lehasa"
            ),
            "milestones": (
                "Sprint workspace; notification centre; calendar improvements; "
                "project document workspace"
            ),
            "timeline": "Continuous internal improvement",
        },
    )

    def __init__(self, database: Database) -> None:
        self._database = database
        self.files_root = self.db_path.parent / "project_files"
        self.trash_root = self.db_path.parent / "project_trash"

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def get_projects(
        self,
        search: str = "",
        category: str = "All",
        status: str = "All",
    ) -> list[Project]:
        with self._connect() as connection:
            self._seed_defaults(connection)
            clauses = ["1 = 1"]
            parameters: list[object] = []
            if search.strip():
                query = f"%{search.strip().lower()}%"
                clauses.append(
                    "(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ? "
                    "OR LOWER(p.owner) LIKE ? OR LOWER(p.members) LIKE ? "
                    "OR LOWER(p.client_name) LIKE ?)"
                )
                parameters.extend([query] * 5)
            if category != "All":
                clauses.append("p.category = ?")
                parameters.append(category)
            if status != "All":
                clauses.append("p.status = ?")
                parameters.append(status)
            rows = connection.execute(
                f"""
                SELECT p.*,
                       (SELECT COUNT(*) FROM project_documents d
                        WHERE d.project_id = p.id) AS document_count,
                       COALESCE((SELECT u.update_text FROM project_updates u
                                 WHERE u.project_id = p.id
                                 ORDER BY datetime(u.created_at) DESC, u.id DESC
                                 LIMIT 1), p.activity_feed, '') AS latest_update
                FROM projects p
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE p.status
                        WHEN 'Active' THEN 1 WHEN 'Planning' THEN 2
                        WHEN 'On Hold' THEN 3 WHEN 'Completed' THEN 4 ELSE 5
                    END,
                    p.name COLLATE NOCASE;
                """,
                parameters,
            ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def get_project(self, project_id: int) -> Project | None:
        with self._connect() as connection:
            self._seed_defaults(connection)
            row = connection.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM project_documents d
                        WHERE d.project_id = p.id) AS document_count,
                       COALESCE((SELECT u.update_text FROM project_updates u
                                 WHERE u.project_id = p.id
                                 ORDER BY datetime(u.created_at) DESC, u.id DESC
                                 LIMIT 1), p.activity_feed, '') AS latest_update
                FROM projects p WHERE p.id = ?;
                """,
                (project_id,),
            ).fetchone()
        return self._row_to_project(row) if row else None

    def create_project(self, project: Project) -> Project:
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE LOWER(name) = LOWER(?);",
                (project.name,),
            ).fetchone()
            if existing:
                raise ValueError("A project with this name already exists.")
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name, description, status, department, progress, members,
                    milestones, timeline, budget_placeholder, documents,
                    activity_feed, category, client_name, owner, start_date,
                    due_date, created_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    project.name, project.description or "", project.status,
                    project.department or "", project.progress, project.members,
                    project.milestones, project.timeline, project.budget_placeholder,
                    project.documents, project.activity_feed, project.category,
                    project.client_name, project.owner, project.start_date,
                    project.due_date, project.created_by,
                ),
            )
            project_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO project_updates (
                    project_id, update_text, status, progress, added_by
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (
                    project_id, "Project created in Nexus.", project.status,
                    project.progress, project.created_by,
                ),
            )
            connection.commit()
        result = self.get_project(project_id)
        if result is None:
            raise ValueError("Project could not be loaded after creation.")
        return result

    def update_project(self, project: Project) -> Project:
        if project.id is None:
            raise ValueError("Project was not found.")
        with self._connect() as connection:
            duplicate = connection.execute(
                "SELECT id FROM projects WHERE LOWER(name) = LOWER(?) AND id <> ?;",
                (project.name, project.id),
            ).fetchone()
            if duplicate:
                raise ValueError("A project with this name already exists.")
            cursor = connection.execute(
                """
                UPDATE projects
                SET name = ?, description = ?, status = ?, department = ?,
                    progress = ?, members = ?, milestones = ?, timeline = ?,
                    budget_placeholder = ?, category = ?, client_name = ?,
                    owner = ?, start_date = ?, due_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    project.name, project.description or "", project.status,
                    project.department or "", project.progress, project.members,
                    project.milestones, project.timeline, project.budget_placeholder,
                    project.category, project.client_name, project.owner,
                    project.start_date, project.due_date, project.id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("Project was not found.")
            connection.commit()
        result = self.get_project(project.id)
        if result is None:
            raise ValueError("Project could not be loaded after update.")
        return result

    def delete_project(self, project_id: int) -> str:
        project = self.get_project(project_id)
        if project is None:
            raise ValueError("Project was not found.")
        with self._connect() as connection:
            connection.execute("DELETE FROM projects WHERE id = ?;", (project_id,))
            connection.commit()

        folder = self._project_folder(project_id)
        recovery_path = ""
        if folder.exists():
            self.trash_root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            safe_name = self._safe_filename(project.name) or f"project-{project_id}"
            destination = self.trash_root / f"{project_id}-{safe_name}-{stamp}"
            shutil.move(str(folder), str(destination))
            recovery_path = str(destination)
        return recovery_path

    def add_update(
        self,
        project_id: int,
        update_text: str,
        status: str,
        progress: int,
        added_by: str,
    ) -> ProjectUpdate:
        text = str(update_text or "").strip()
        if not text:
            raise ValueError("Please enter a project update.")
        if self.get_project(project_id) is None:
            raise ValueError("Project was not found.")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO project_updates (
                    project_id, update_text, status, progress, added_by
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (project_id, text, status, progress, added_by),
            )
            connection.execute(
                """
                UPDATE projects
                SET status = ?, progress = ?, activity_feed = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (status, progress, text, project_id),
            )
            connection.commit()
            update_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM project_updates WHERE id = ?;", (update_id,)
            ).fetchone()
        return self._row_to_update(row)

    def get_updates(self, project_id: int) -> list[ProjectUpdate]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM project_updates
                WHERE project_id = ?
                ORDER BY datetime(created_at) DESC, id DESC;
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_update(row) for row in rows]

    def add_document(
        self,
        project_id: int,
        source_path: str,
        document_type: str,
        added_by: str,
    ) -> ProjectDocument:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Please select an existing document.")
        if self.get_project(project_id) is None:
            raise ValueError("Project was not found.")
        folder = self._project_folder(project_id)
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(source.name)
        destination = folder / safe_name
        if destination.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            destination = folder / f"{destination.stem}-{stamp}{destination.suffix}"
        shutil.copy2(source, destination)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO project_documents (
                    project_id, name, file_path, document_type, added_by
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (
                    project_id, source.name, str(destination),
                    document_type or "General", added_by,
                ),
            )
            connection.execute(
                """
                UPDATE projects
                SET documents = 'Stored in Nexus project files',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (project_id,),
            )
            connection.commit()
            document_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM project_documents WHERE id = ?;", (document_id,)
            ).fetchone()
        return self._row_to_document(row)

    def get_documents(self, project_id: int) -> list[ProjectDocument]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM project_documents
                WHERE project_id = ?
                ORDER BY datetime(added_at) DESC, id DESC;
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def _seed_defaults(self, connection: sqlite3.Connection) -> None:
        for data in self.DEFAULT_PROJECTS:
            row = connection.execute(
                "SELECT id FROM projects WHERE LOWER(name) = LOWER(?);",
                (data["name"],),
            ).fetchone()
            if row:
                if data["name"] == "Untangled Main Website":
                    self._refresh_website_profile(connection, int(row["id"]), data)
                continue
            cursor = connection.execute(
                """
                INSERT INTO projects (
                    name, description, status, department, progress, members,
                    milestones, timeline, budget_placeholder, documents,
                    activity_feed, category, client_name, owner, start_date,
                    due_date, created_by, updated_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, 'Budget pending', '', ?, ?, '', ?, '', '', 'Nexus', CURRENT_TIMESTAMP);
                """,
                (
                    data["name"], data["description"], data["status"],
                    data["department"], data["members"], data["milestones"],
                    data["timeline"], "Project workspace created in Nexus.",
                    data["category"], data["owner"],
                ),
            )
            connection.execute(
                """
                INSERT INTO project_updates (
                    project_id, update_text, status, progress, added_by
                ) VALUES (?, 'Project workspace created in Nexus.', ?, 0, 'Nexus');
                """,
                (int(cursor.lastrowid), data["status"]),
            )
        connection.commit()

    @staticmethod
    def _refresh_website_profile(
        connection: sqlite3.Connection, project_id: int, data: dict
    ) -> None:
        """Replace only the original generated website values, preserving later edits."""
        replacements = (
            (
                "description", data["description"],
                "Company website, e-commerce, product catalogue, customer requests, and website merge delivery.",
            ),
            ("owner", data["owner"], "Siyanda Nkosi"),
            (
                "members", data["members"],
                "Siyanda Nkosi, Nonhlanhla Hlatshwayo, Ubuntu Hadebe",
            ),
            (
                "milestones", data["milestones"],
                "Website merge; e-commerce integration; testing; launch",
            ),
            (
                "timeline", data["timeline"],
                "Delivery dates to be confirmed by project management",
            ),
        )
        for column, new_value, old_value in replacements:
            connection.execute(
                f"""UPDATE projects SET {column} = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND {column} = ?;""",
                (new_value, project_id, old_value),
            )

    def _project_folder(self, project_id: int) -> Path:
        root = self.files_root.resolve()
        folder = (root / str(int(project_id))).resolve()
        if folder.parent != root:
            raise ValueError("Invalid project storage location.")
        return folder

    @staticmethod
    def _safe_filename(value: str) -> str:
        name = Path(str(value or "document")).name
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
        return safe or "document"

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = self._database.connection()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _row_to_project(row: sqlite3.Row) -> Project:
        keys = set(row.keys())
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            status=row["status"],
            department=row["department"] or "",
            progress=max(0, min(100, int(row["progress"] or 0))),
            members=row["members"] or "",
            milestones=row["milestones"] or "",
            timeline=row["timeline"] or "",
            budget_placeholder=row["budget_placeholder"] or "Budget pending",
            documents=row["documents"] or "",
            activity_feed=row["activity_feed"] or "",
            category=row["category"] if "category" in keys else "Internal Project",
            client_name=row["client_name"] if "client_name" in keys else "",
            owner=row["owner"] if "owner" in keys else "",
            start_date=row["start_date"] if "start_date" in keys else "",
            due_date=row["due_date"] if "due_date" in keys else "",
            created_by=row["created_by"] if "created_by" in keys else "",
            created_at=row["created_at"] if "created_at" in keys else "",
            updated_at=row["updated_at"] if "updated_at" in keys else "",
            document_count=int(row["document_count"] or 0) if "document_count" in keys else 0,
            latest_update=row["latest_update"] if "latest_update" in keys else "",
        )

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> ProjectDocument:
        return ProjectDocument(
            id=row["id"], project_id=row["project_id"], name=row["name"],
            file_path=row["file_path"], document_type=row["document_type"] or "General",
            added_by=row["added_by"] or "", added_at=row["added_at"] or "",
        )

    @staticmethod
    def _row_to_update(row: sqlite3.Row) -> ProjectUpdate:
        return ProjectUpdate(
            id=row["id"], project_id=row["project_id"],
            update_text=row["update_text"], status=row["status"] or "",
            progress=max(0, min(100, int(row["progress"] or 0))),
            added_by=row["added_by"] or "", created_at=row["created_at"] or "",
        )
