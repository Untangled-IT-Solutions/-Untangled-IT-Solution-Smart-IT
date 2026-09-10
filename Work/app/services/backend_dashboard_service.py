"""Backend API dashboard service for the Windows desktop application.

The desktop client never connects to MongoDB directly. All dashboard metrics
come from the authenticated backend API.
"""
from __future__ import annotations

from typing import Any


class BackendDashboardService:
    """Fetch dashboard data through the authenticated backend API."""

    def __init__(self, backend_api) -> None:
        self._backend = backend_api

    def get_summary(self) -> dict[str, Any]:
        """Return the authoritative company dashboard summary."""
        return self._backend.request("GET", "/api/dashboard/summary")

    def get_business_lead_dashboard(self) -> dict[str, Any]:
        return self._backend.request("GET", "/api/dashboard/business-lead")

    def get_director_dashboard(self) -> dict[str, Any]:
        return self._backend.request("GET", "/api/dashboard/director")
