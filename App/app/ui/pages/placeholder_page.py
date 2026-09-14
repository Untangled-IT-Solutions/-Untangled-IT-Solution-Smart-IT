from __future__ import annotations
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from app.core import theme
from app.ui.pages.base_page import BasePage


class PlaceholderPage(BasePage):
    def __init__(self, name: str, session) -> None:
        self.TITLE = name
        self.SUBTITLE = f"{name} · connected to production API"
        self.CACHE_KEY = None
        super().__init__(session)

    def build(self) -> None:
        card = QFrame()
        card.setStyleSheet(
            f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:14px;"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 28, 24, 28)
        title = QLabel(self.TITLE)
        title.setStyleSheet("font-size:18px; font-weight:700;")
        cl.addWidget(title)
        msg = QLabel(
            "This screen uses the same BasePage + background-worker pattern as Dashboard, "
            "People, Tasks, and Notifications.\n\n"
            "Port widgets from the CustomTkinter view into fetch()/apply() to keep the UI "
            "identical without freezing."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color:{theme.MUTED}; font-size:13px;")
        cl.addWidget(msg)
        self._lay.addWidget(card)
        self._lay.addStretch(1)
