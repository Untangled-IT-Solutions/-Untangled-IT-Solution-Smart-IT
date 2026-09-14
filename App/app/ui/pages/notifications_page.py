from __future__ import annotations
from typing import Any, Callable, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)
from app.core import cache, theme
from app.core.workers import run_async
from app.ui.pages.base_page import BasePage


class NotificationsPage(BasePage):
    TITLE = "Notifications"
    SUBTITLE = "Employee & Director notification centre"
    CACHE_KEY = "notifications"
    CACHE_TTL = 15.0

    def __init__(self, session, on_unread: Optional[Callable[[int], None]] = None) -> None:
        self._on_unread = on_unread
        super().__init__(session)

    def build(self) -> None:
        tools = QHBoxLayout()
        self.role = QComboBox()
        self.role.addItems(["All", "Director", "Staff"])
        self.role.setMinimumHeight(36)
        self.role.setFixedWidth(120)
        tools.addWidget(self.role)
        self.unread_only = QCheckBox("Unread only")
        tools.addWidget(self.unread_only)
        tools.addStretch(1)
        self.mark_btn = QPushButton("✓  Mark all as read")
        self.mark_btn.setCursor(Qt.PointingHandCursor)
        self.mark_btn.clicked.connect(self._mark_all)
        tools.addWidget(self.mark_btn)
        self._lay.addLayout(tools)

        self.banner = QLabel("")
        self.banner.setStyleSheet(f"color:{theme.MUTED}; padding:4px 0;")
        self._lay.addWidget(self.banner)

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

        self.role.currentTextChanged.connect(lambda _: self.load(on_done=lambda: None))
        self.unread_only.toggled.connect(lambda _: self.load(on_done=lambda: None))

    def fetch(self) -> Any:
        api = self.session.api
        try:
            data = api.request("GET", "/api/notifications")
        except Exception as exc:
            return {"items": [], "unread": 0, "error": str(exc)}
        items = data.get("notifications") or data.get("items") or data.get("data") or []
        if isinstance(data, list):
            items = data
        unread = 0
        try:
            c = api.request("GET", "/api/notifications/unread-count")
            unread = int(c.get("count") or c.get("unread") or 0)
        except Exception:
            unread = sum(
                1 for n in items
                if isinstance(n, dict) and not (n.get("is_read") or n.get("read") or n.get("isRead"))
            )
        return {"items": items if isinstance(items, list) else [], "unread": unread}

    def apply(self, data: Any) -> None:
        data = data or {}
        items = [n for n in data.get("items") or [] if isinstance(n, dict)]
        if self.unread_only.isChecked():
            items = [n for n in items if not (n.get("is_read") or n.get("read") or n.get("isRead"))]
        unread = int(data.get("unread") or 0)
        if self._on_unread:
            self._on_unread(unread)
        if unread:
            self.banner.setText(f"You have {unread} missed notification(s)")
            self.banner.setStyleSheet("color:#B91C1C; font-weight:600;")
        else:
            self.banner.setText("All caught up — no unread notifications")
            self.banner.setStyleSheet(f"color:{theme.MUTED};")

        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for n in items:
            self.list_lay.addWidget(self._card(n))
        self.list_lay.addStretch(1)

    def _card(self, n: dict) -> QFrame:
        read = bool(n.get("is_read") or n.get("read") or n.get("isRead"))
        card = QFrame()
        card.setStyleSheet(
            f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:12px;"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        dot = QLabel("●" if not read else "○")
        dot.setStyleSheet(
            f"color:{theme.PRIMARY if not read else theme.BORDER}; font-size:12px;"
        )
        lay.addWidget(dot)
        col = QVBoxLayout()
        title = QLabel(str(n.get("title") or "Notification"))
        title.setStyleSheet("font-weight:700; font-size:14px;")
        col.addWidget(title)
        msg = QLabel(str(n.get("message") or n.get("body") or ""))
        msg.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        msg.setWordWrap(True)
        col.addWidget(msg)
        lay.addLayout(col, 1)
        meta = QLabel(str(n.get("created_at") or n.get("createdAt") or "")[:16])
        meta.setStyleSheet(f"color:{theme.MUTED}; font-size:11px;")
        lay.addWidget(meta)
        return card

    def _mark_all(self) -> None:
        self.mark_btn.setEnabled(False)
        api = self.session.api

        def work():
            try:
                return api.request("POST", "/api/notifications/mark-all-read", {})
            except Exception:
                return api.request("POST", "/api/notifications/mark-all", {})

        def ok(_):
            self.mark_btn.setEnabled(True)
            cache.invalidate("notifications")
            self.load(on_done=lambda: None)

        def err(_):
            self.mark_btn.setEnabled(True)

        run_async(work, ok, err)
