"""Reports controller."""

from pathlib import Path

from app.services.report_service import ReportService


class ReportController:
    """Coordinates report preview and export actions."""

    def __init__(self, report_service: ReportService) -> None:
        self._report_service = report_service

    def get_report_types(self) -> list[str]:
        return list(self._report_service.REPORT_QUERIES)

    def preview(self, report_type: str) -> list[dict[str, object]]:
        return self._report_service.preview(report_type)

    def export(self, report_type: str, file_type: str) -> Path:
        return self._report_service.export(report_type, file_type)
