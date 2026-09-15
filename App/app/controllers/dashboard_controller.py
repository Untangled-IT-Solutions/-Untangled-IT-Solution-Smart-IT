"""Dashboard controller."""

from __future__ import annotations

from app.services.dashboard_service import DashboardService


class DashboardController:
    """Coordinates dashboard requests."""

    def __init__(
        self,
        dashboard_service: DashboardService,
        get_current_account=None,
    ) -> None:
        self._dashboard_service = dashboard_service
        self._get_current_account = get_current_account

    # ==================================================================
    # MAIN DASHBOARD
    # ==================================================================

    def get_summary(self):
        """Select the display endpoint from the signed-in role.

        This selection only controls presentation. The API authenticates the
        session again and applies the authoritative scope.
        """
        account = self._get_current_account() if self._get_current_account else None
        role = str(getattr(account, "role", "Staff") or "Staff").strip().lower().replace("_", " ")
        if role == "director":
            return self.get_director_dashboard()
        if role == "business lead":
            return self.get_business_lead_dashboard()
        if role in {"operations manager", "super admin"}:
            return self.get_operations_dashboard()
        if role in {"staff", "intern", "employee"}:
            return self._dashboard_service.get_personal_dashboard()
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

    def get_operations_dashboard(self):
        """Return the Operations command-centre dashboard."""
        return self._dashboard_service.get_operations_dashboard()
