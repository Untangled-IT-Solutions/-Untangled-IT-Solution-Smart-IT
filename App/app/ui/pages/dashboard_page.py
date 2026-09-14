from __future__ import annotations
from typing import Any
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout
from app.core import theme
from app.ui.pages.base_page import BasePage


class DashboardPage(BasePage):
    TITLE = "Dashboard"
    SUBTITLE = "Live operations overview"
    CACHE_KEY = "dashboard"
    CACHE_TTL = 20.0

    def build(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(16)
        self._vals = []
        specs = [
            ("People Online", "#DBEAFE", "#1D4ED8"),
            ("Open Tasks", "#FEF3C7", "#B45309"),
            ("Pending Approvals", "#FCE7F3", "#BE185D"),
            ("Unread Notifications", "#DCFCE7", "#15803D"),
        ]
        for i, (title, bg, fg) in enumerate(specs):
            card = QFrame()
            card.setMinimumHeight(120)
            card.setStyleSheet(
                f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:14px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(18, 16, 18, 16)
            icon = QLabel("  ")
            icon.setFixedSize(36, 36)
            icon.setStyleSheet(f"background:{bg}; border-radius:10px;")
            cl.addWidget(icon)
            lbl = QLabel(title)
            lbl.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
            val = QLabel("—")
            val.setStyleSheet(f"font-size:30px; font-weight:700; color:{fg};")
            cl.addWidget(lbl)
            cl.addWidget(val)
            cl.addStretch(1)
            grid.addWidget(card, i // 2, i % 2)
            self._vals.append(val)
        self._lay.addLayout(grid)
        self.note = QLabel("")
        self.note.setStyleSheet(f"color:{theme.MUTED};")
        self._lay.addWidget(self.note)
        self._lay.addStretch(1)

    def fetch(self) -> Any:
        api = self.session.api
        try:
            if hasattr(api, "get_dashboard_summary"):
                return api.get_dashboard_summary() or {}
            return api.request("GET", "/api/dashboard/summary") or {}
        except Exception as exc:
            return {"_error": str(exc)}

    def apply(self, data: Any) -> None:
        data = data or {}
        if data.get("_error"):
            self.note.setText(f"Could not refresh dashboard: {data['_error']}")
        else:
            self.note.setText("Synced with server")
        nested = data.get("summary") if isinstance(data.get("summary"), dict) else data
        keys = [
            ("people_online", "online", "employees"),
            ("open_tasks", "tasks", "task_count"),
            ("pending_approvals", "approvals", "pending"),
            ("notifications", "unread", "unread_notifications"),
        ]
        for lbl, opts in zip(self._vals, keys):
            v = "—"
            for k in opts:
                if nested.get(k) is not None:
                    v = nested.get(k)
                    break
            lbl.setText(str(v))
