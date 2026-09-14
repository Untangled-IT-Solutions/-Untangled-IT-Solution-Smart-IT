from __future__ import annotations
from typing import Any, List
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)
from app.core import theme
from app.ui.pages.base_page import BasePage


class PeoplePage(BasePage):
    TITLE = "People"
    SUBTITLE = "Employee directory and profiles"
    CACHE_KEY = "people"
    CACHE_TTL = 60.0

    def build(self) -> None:
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search employees")
        self.search.setMinimumHeight(42)
        self.search.textChanged.connect(self._filter)
        self._lay.addWidget(self.search)

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
        self._all: List[dict] = []

    def fetch(self) -> Any:
        api = self.session.api
        try:
            if hasattr(api, "get_employees"):
                items = api.get_employees() or []
                return {"items": items}
            data = api.request("GET", "/api/employees")
            items = data.get("employees") or data.get("items") or data.get("data") or []
            return {"items": items if isinstance(items, list) else []}
        except Exception as exc:
            return {"items": [], "error": str(exc)}

    def apply(self, data: Any) -> None:
        self._all = [x for x in (data or {}).get("items") or [] if isinstance(x, dict)]
        self._render(self._all)

    def _render(self, items: List[dict]) -> None:
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for emp in items:
            self.list_lay.addWidget(self._card(emp))
        self.list_lay.addStretch(1)

    def _card(self, emp: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:12px;"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        avatar = QLabel((emp.get("full_name") or emp.get("name") or "?")[:1].upper())
        avatar.setFixedSize(44, 44)
        avatar.setStyleSheet(
            f"background:{theme.PRIMARY}; color:white; border-radius:22px;"
            "font-weight:700; font-size:16px;"
        )
        avatar.setAlignment(avatar.alignment() | 0x84)  # AlignCenter-ish
        from PySide6.QtCore import Qt
        avatar.setAlignment(Qt.AlignCenter)
        lay.addWidget(avatar)
        col = QVBoxLayout()
        name = emp.get("full_name") or emp.get("name") or emp.get("username") or "Employee"
        n = QLabel(str(name))
        n.setStyleSheet("font-weight:700; font-size:14px;")
        col.addWidget(n)
        meta = QLabel(
            f"{emp.get('role') or emp.get('position') or ''}  ·  {emp.get('department') or ''}"
        )
        meta.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        col.addWidget(meta)
        lay.addLayout(col, 1)
        return card

    def _filter(self, text: str) -> None:
        q = (text or "").strip().lower()
        if not q:
            self._render(self._all)
            return
        self._render([
            e for e in self._all
            if q in str(e.get("full_name") or "").lower()
            or q in str(e.get("email") or "").lower()
            or q in str(e.get("department") or "").lower()
        ])
