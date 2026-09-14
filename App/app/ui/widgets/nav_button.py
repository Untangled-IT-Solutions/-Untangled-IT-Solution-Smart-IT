"""Sidebar nav button with coloured icon chip (matches original CTk sidebar)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy

from app.core import theme


class NavButton(QFrame):
    clicked = Signal(str)

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(44)

        color = theme.NAV_COLORS.get(name, theme.PRIMARY)
        icon = theme.NAV_ICONS.get(name, "•")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 10, 4)
        lay.setSpacing(10)

        chip = QLabel(icon)
        chip.setFixedSize(28, 28)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(
            f"background:{color}; color:white; border-radius:8px; font-size:13px; font-weight:700;"
        )
        self._chip = chip
        lay.addWidget(chip)

        self._text = QLabel(name)
        self._text.setStyleSheet(f"color:{theme.TEXT}; font-size:13px; font-weight:500;")
        lay.addWidget(self._text, 1)

        self._badge = QLabel("")
        self._badge.setStyleSheet(
            "background:#EF4444; color:white; border-radius:8px; padding:1px 6px;"
            "font-size:10px; font-weight:700;"
        )
        self._badge.hide()
        lay.addWidget(self._badge)
        self._apply_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_style()

    def set_badge(self, count: int) -> None:
        if count and count > 0:
            self._badge.setText("9+" if count > 9 else str(count))
            self._badge.show()
        else:
            self._badge.hide()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                f"QFrame {{ background:{theme.PRIMARY_SOFT}; border-radius:12px; }}"
            )
            self._text.setStyleSheet(
                f"color:{theme.PRIMARY_DARK}; font-size:13px; font-weight:700;"
            )
        else:
            self.setStyleSheet("QFrame { background:transparent; border-radius:12px; }")
            self._text.setStyleSheet(
                f"color:{theme.TEXT}; font-size:13px; font-weight:500;"
            )

    def enterEvent(self, event) -> None:  # noqa: N802
        if not self._active:
            self.setStyleSheet(
                f"QFrame {{ background:{theme.PANEL_ALT}; border-radius:12px; }}"
            )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.name)
        super().mousePressEvent(event)
