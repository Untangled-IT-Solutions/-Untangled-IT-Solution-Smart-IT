"""Reports – Backend API only."""

from __future__ import annotations

from typing import List

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class ReportService:
    DEFAULT_TYPES = [
        "Attendance Summary",
        "Task Workload",
        "Quote Pipeline",
        "Order Status",
        "Approvals Overview",
    ]

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def get_report_types(self) -> list:
        try:
            data = self._backend.request("GET", "/api/reports/types")
            types = data.get("types") or data.get("items") or []
            if types:
                return list(types)
        except BackendAPIError:
            pass
        return list(self.DEFAULT_TYPES)

    def preview(self, report_type: str) -> list:
        try:
            data = self._backend.request(
                "GET", f"/api/reports/preview?type={report_type}"
            )
            rows = data.get("rows") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                rows = data
            return list(rows)
        except BackendAPIError as exc:
            print(f"⚠️ report preview failed: {exc}")
            return [{"error": str(exc)}]

    def export(self, report_type: str, format: str) -> str:
        try:
            data = self._backend.request(
                "POST",
                "/api/reports/export",
                {"type": report_type, "format": format},
            )
            return str(data.get("path") or data.get("url") or data.get("message") or "Export queued")
        except BackendAPIError as exc:
            return f"Export failed: {exc}"
