from __future__ import annotations
from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)
from app.core import theme
from app.ui.pages.base_page import BasePage


class TasksPage(BasePage):
    TITLE = "Tasks"
    SUBTITLE = "My work inbox"
    CACHE_KEY = "tasks"
    CACHE_TTL = 30.0

    def build(self) -> None:
        bar = QHBoxLayout()
        for label, active in (
            ("Inbox", True), ("Reviews", False), ("Overdue", False),
            ("My Tasks", False), ("Team", False), ("Completed", False),
        ):
            b = QPushButton(label)
            if active:
                b.setStyleSheet(
                    f"background:{theme.SUCCESS}; color:white; border-radius:16px; padding:8px 14px;"
                )
            else:
                b.setObjectName("secondary")
                b.setStyleSheet(
                    f"background:{theme.PANEL}; color:{theme.TEXT}; border:1px solid {theme.BORDER};"
                    "border-radius:16px; padding:8px 14px;"
                )
            bar.addWidget(b)
        bar.addStretch(1)
        new_btn = QPushButton("+ New Task")
        bar.addWidget(new_btn)
        self._lay.addLayout(bar)

        stats = QHBoxLayout()
        self._stat_labels = []
        for title in ("Total Tasks", "In Progress", "Due Today", "Completed This Week"):
            card = QFrame()
            card.setStyleSheet(
                f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:12px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            t = QLabel(title)
            t.setStyleSheet(f"color:{theme.MUTED}; font-size:11px;")
            v = QLabel("0")
            v.setStyleSheet("font-size:22px; font-weight:700;")
            cl.addWidget(t)
            cl.addWidget(v)
            stats.addWidget(card)
            self._stat_labels.append(v)
        self._lay.addLayout(stats)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.host = QWidget()
        self.host.setStyleSheet("background:transparent;")
        self.list_lay = QVBoxLayout(self.host)
        self.list_lay.setSpacing(10)
        self.list_lay.addStretch(1)
        scroll.setWidget(self.host)
        self._lay.addWidget(scroll, 1)

    def fetch(self) -> Any:
        api = self.session.api
        try:
            if hasattr(api, "get_tasks"):
                data = api.get_tasks() or {}
            else:
                data = api.request("GET", "/api/tasks")
            items = data.get("tasks") or data.get("items") or data.get("data") or []
            if isinstance(data, list):
                items = data
            return {"items": items if isinstance(items, list) else []}
        except Exception:
            return {"items": []}

    def apply(self, data: Any) -> None:
        items = [t for t in (data or {}).get("items") or [] if isinstance(t, dict)]
        self._stat_labels[0].setText(str(len(items)))
        in_prog = sum(1 for t in items if "progress" in str(t.get("status") or "").lower())
        self._stat_labels[1].setText(str(in_prog))
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for t in items:
            self.list_lay.addWidget(self._card(t))
        self.list_lay.addStretch(1)

    def _card(self, t: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"background:#ECFDF5; border:1px solid {theme.BORDER}; border-left:4px solid {theme.DANGER};"
            "border-radius:12px;"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        title = QLabel(str(t.get("title") or t.get("name") or "Task"))
        title.setStyleSheet("font-weight:700; font-size:14px;")
        row.addWidget(title, 1)
        pri = str(t.get("priority") or "")
        if pri:
            badge = QLabel(pri)
            badge.setStyleSheet(
                "background:#FCE7F3; color:#BE185D; border-radius:8px; padding:2px 8px; font-size:11px;"
            )
            row.addWidget(badge)
        lay.addLayout(row)
        desc = QLabel(str(t.get("description") or t.get("body") or "No description"))
        desc.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        meta = QLabel(
            f"{t.get('assignee') or t.get('assigned_to') or ''}  ·  {t.get('due_date') or t.get('due') or ''}"
        )
        meta.setStyleSheet(f"color:{theme.MUTED}; font-size:11px;")
        lay.addWidget(meta)
        return card
