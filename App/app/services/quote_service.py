"""Quote domain service – Backend API only (no Tk).

Views and presenters should prefer this over calling BackendAPIClient directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.services.backend_api_client import BackendAPIClient, BackendAPIError

logger = logging.getLogger("untangled.quotes")


class QuoteService:
    """HTTP-backed quote operations."""

    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def list_quotes(self) -> List[Dict[str, Any]]:
        try:
            data = self._backend.request("GET", "/api/quotes")
            items = data.get("quotes") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return [q for q in items if isinstance(q, dict)]
        except BackendAPIError as exc:
            logger.warning("list_quotes failed: %s", exc)
            raise

    def set_status(self, reference: str, status: str, note: str = "") -> Dict[str, Any]:
        payload = {"status": status, "note": note or ""}
        return self._backend.request(
            "POST",
            f"/api/quotes/{reference}/status",
            payload,
        )

    def assign(self, reference: str, assignee: Dict[str, Any] | str) -> Dict[str, Any]:
        if isinstance(assignee, str):
            payload = {"assigned_to": assignee}
        else:
            payload = {"assigned_to": assignee}
        return self._backend.request(
            "POST",
            f"/api/quotes/{reference}/assign",
            payload,
        )
