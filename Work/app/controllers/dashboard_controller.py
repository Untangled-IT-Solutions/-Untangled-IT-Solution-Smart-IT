"""Dashboard controller."""

from __future__ import annotations

from app.services.dashboard_service import DashboardService


class DashboardController:
    """Coordinates dashboard requests."""

    def __init__(
        self,
        dashboard_service: DashboardService,
    ) -> None:
        self._dashboard_service = dashboard_service

    # ==================================================================
    # MAIN DASHBOARD
    # ==================================================================

    def get_summary(self):
        """Return the main dashboard summary."""
        return self._dashboard_service.get_summary()

    # ==================================================================
    # ROLE-SPECIFIC DASHBOARDS
    # ==================================================================

    def get_business_lead_dashboard(self):
        """Return the Business Lead dashboard."""
        return self._dashboard_service.get_business_lead_dashboard()

    def get_director_dashboard(self):
        """Return the Director dashboard."""
        return self._dashboard_service.get_director_dashboard()