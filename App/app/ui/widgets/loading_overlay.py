from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from app.core import theme


class LoadingOverlay(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background-color: rgba(247, 249, 248, 200);"
        )
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setFixedSize(300, 110)
        card.setStyleSheet(
            f"background:{theme.PANEL}; border:1px solid {theme.BORDER}; border-radius:14px;"
        )
        cl = QVBoxLayout(card)
        self.label = QLabel("Loading…")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("font-weight:700; font-size:14px;")
        cl.addWidget(self.label)
        hint = QLabel("Fetching data from server")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color:{theme.MUTED}; font-size:12px;")
        cl.addWidget(hint)
        lay.addWidget(card)
        self.hide()

    def show_message(self, text: str = "Loading…") -> None:
        self.label.setText(text)
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
