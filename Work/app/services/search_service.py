"""SQLite-backed global search service."""

import sqlite3
from pathlib import Path

from app.database.database import Database
from app.models.search import SearchResult


class SearchService:
    """Searches operational records without coupling the header to any module UI."""

    def __init__(self, database: Database) -> None:
        self._database = database

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def search(self, query: str, limit: int = 30) -> list[SearchResult]:
        """Return matching People, Work, project, RFQ, supplier, and client records."""
        term = query.strip()
        if not term:
            return []
        pattern = f"%{term}%"
        results: list[SearchResult] = []
        with self._connect() as connection:
            people = connection.execute(
                """
                SELECT id, full_name, position, department FROM employees
                WHERE full_name LIKE ? OR position LIKE ? OR department LIKE ?;
                """, (pattern, pattern, pattern)
            ).fetchall()
            work = connection.execute(
                """
                SELECT id, title, category, status, assigned_employee FROM tasks
                WHERE title LIKE ? OR description LIKE ? OR category LIKE ?;
                """, (pattern, pattern, pattern)
            ).fetchall()
            projects = connection.execute(
                """
                SELECT id, name, department, status FROM projects
                WHERE name LIKE ? OR description LIKE ?;
                """, (pattern, pattern)
            ).fetchall()
            suppliers = connection.execute(
                "SELECT id, name, status FROM suppliers WHERE name LIKE ?;", (pattern,)
            ).fetchall()
            clients = connection.execute(
                "SELECT id, name, status FROM clients WHERE name LIKE ?;", (pattern,)
            ).fetchall()
        results.extend(
            SearchResult("People", row["full_name"], f"{row['position']} | {row['department']}", row["id"])
            for row in people
        )
        for row in work:
            source = "RFQ" if row["category"] in {"RFQ", "Tender"} else "Work"
            results.append(SearchResult(source, row["title"], f"{row['category']} | {row['status']} | {row['assigned_employee'] or 'Unassigned'}", row["id"]))
        results.extend(
            SearchResult("Projects", row["name"], f"{row['department'] or 'General'} | {row['status']}", row["id"])
            for row in projects
        )
        results.extend(SearchResult("Suppliers", row["name"], row["status"], row["id"]) for row in suppliers)
        results.extend(SearchResult("Clients", row["name"], row["status"], row["id"]) for row in clients)
        return results[:limit]

    def _connect(self) -> sqlite3.Connection:
        return self._database.connection()  # type: ignore[return-value]
