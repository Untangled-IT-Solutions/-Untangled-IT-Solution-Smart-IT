"""Projects – Backend API only."""

from __future__ import annotations

from typing import List, Optional

from app.models.project import Project
from app.services.backend_api_client import BackendAPIClient, BackendAPIError


class ProjectService:
    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend

    def _to_model(self, raw: dict) -> Project:
        progress = raw.get("progress") or 0
        try:
            progress = int(progress)
        except (TypeError, ValueError):
            progress = 0
        return Project(
            id=raw.get("id") or raw.get("_id"),
            name=str(raw.get("name") or raw.get("title") or "Untitled"),
            description=raw.get("description"),
            status=str(raw.get("status") or "Active"),
            department=raw.get("department"),
            progress=progress,
            members=str(raw.get("members") or ""),
            milestones=str(raw.get("milestones") or ""),
            timeline=str(raw.get("timeline") or ""),
            budget_placeholder=str(raw.get("budget_placeholder") or "Budget pending"),
            documents=str(raw.get("documents") or ""),
            activity_feed=str(raw.get("activity_feed") or ""),
        )

    def get_projects(self) -> List[Project]:
        try:
            data = self._backend.request("GET", "/api/projects")
            items = data.get("projects") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return [self._to_model(i) for i in items if isinstance(i, dict)]
        except BackendAPIError as exc:
            print(f"⚠️ projects fetch failed: {exc}")
            return []

    def get_project(self, project_id: int) -> Optional[Project]:
        try:
            data = self._backend.request("GET", f"/api/projects/{project_id}")
            raw = data.get("project") or data
            if isinstance(raw, dict):
                return self._to_model(raw)
        except BackendAPIError as exc:
            print(f"⚠️ project fetch failed: {exc}")
        return None
