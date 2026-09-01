"""Operational reporting and export service."""

import csv
from pathlib import Path

from app.database.database import Database


class ReportService:
    """Builds attendance, employee, work, approval, RFQ, and project reports."""

    REPORT_QUERIES = {
        "Attendance": "SELECT employee_name, work_date, clock_in_at, clock_out_at, hours_worked FROM attendance_records ORDER BY work_date DESC;",
        "Employee": "SELECT employee_number, full_name, department, position, status, current_task FROM employees ORDER BY full_name;",
        "Work": "SELECT title, category, assigned_employee, priority, status, due_date FROM tasks ORDER BY due_date;",
        "Approval": "SELECT title, request_type, requested_by, department, amount, status, current_stage FROM approvals ORDER BY submitted_at DESC;",
        "RFQ": "SELECT title, assigned_employee, priority, status, due_date FROM tasks WHERE category IN ('RFQ', 'Tender') ORDER BY due_date;",
        "Project": "SELECT name, status, department, progress, members, milestones, timeline FROM projects ORDER BY name;",
    }

    def __init__(self, database: Database) -> None:
        self._database = database
        self.output_dir = Path(__file__).resolve().parents[2] / "generated" / "reports"

    def preview(self, report_type: str) -> list[dict[str, object]]:
        """Return rows for a report preview."""
        query = self.REPORT_QUERIES[report_type]
        with self._database.connection() as connection:
            rows = connection.execute(query).fetchall()
        return [dict(row) for row in rows]

    def export(self, report_type: str, file_type: str) -> Path:
        """Export a report to CSV, Excel-compatible CSV, or printable PDF HTML."""
        rows = self.preview(report_type)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        suffix = {"CSV": "csv", "Excel": "csv", "PDF": "html"}[file_type]
        path = self.output_dir / f"{report_type.lower()}_report.{suffix}"
        if file_type in {"CSV", "Excel"}:
            self._write_csv(path, rows)
            return path
        self._write_printable_html(path, report_type, rows)
        return path

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        headers = list(rows[0].keys()) if rows else ["message"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
            else:
                writer.writerow({"message": "No records found"})

    @staticmethod
    def _write_printable_html(path: Path, report_type: str, rows: list[dict[str, object]]) -> None:
        headers = list(rows[0].keys()) if rows else ["message"]
        body_rows = rows or [{"message": "No records found"}]
        header_html = "".join(f"<th>{header}</th>" for header in headers)
        row_html = "".join(
            "<tr>" + "".join(f"<td>{row.get(header, '')}</td>" for header in headers) + "</tr>"
            for row in body_rows
        )
        path.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>"
            f"{report_type} Report</title><style>body{{font-family:Segoe UI,Arial;"
            "color:var(--text)}}table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid var(--border);padding:8px;text-align:left}"
            "th{background:var(--panel)}</style></head><body>"
            f"<h1>{report_type} Report</h1><table><thead><tr>{header_html}</tr></thead>"
            f"<tbody>{row_html}</tbody></table></body></html>",
            encoding="utf-8",
        )
