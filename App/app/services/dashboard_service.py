"""Dashboard data – Backend API only."""

from __future__ import annotations

from typing import Any, Dict

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class DashboardService:
    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def get_summary(self) -> Dict[str, Any]:
        try:
            return self._backend.get_dashboard_summary()
        except BackendAPIError as exc:
            return {"error": str(exc), "cards": [], "recent": []}

    def get_business_lead_dashboard(self) -> Dict[str, Any]:
        try:
            return self._backend.request("GET", "/api/dashboard/business-lead")
        except BackendAPIError:
            return self.get_summary()

    def get_director_dashboard(self) -> Dict[str, Any]:
        try:
            return self._backend.request("GET", "/api/dashboard/director")
        except BackendAPIError:
            return self.get_summary()
