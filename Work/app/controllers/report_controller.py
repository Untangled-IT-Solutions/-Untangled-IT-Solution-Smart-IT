# app/controllers/report_controller.py
"""Report controller."""

from app.services.report_service import ReportService


class ReportController:
    """Controls report operations."""

    def __init__(self, report_service: ReportService) -> None:
        self._service = report_service

    def get_report_types(self) -> list:
        """Get list of report types."""
        return self._service.get_report_types()

    def preview(self, report_type: str) -> list:
        """Preview a report."""
        return self._service.preview(report_type)

    def export(self, report_type: str, format: str) -> str:
        """Export a report."""
        return self._service.export(report_type, format)