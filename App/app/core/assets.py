"""Load logos / window icons from project assets (or bundled fallbacks)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt

from app.core.theme import find_asset


def logo_pixmap(max_w: int = 180, max_h: int = 140) -> Optional[QPixmap]:
    for rel in (
        ("logo", "mainlogo.png"),
        ("logo", "logo.png"),
        ("logo", "mainlogo.PNG"),
        ("Branding", "logo.png"),
    ):
        path = find_asset(*rel)
        if path:
            pm = QPixmap(str(path))
            if not pm.isNull():
                return pm.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return None


def window_icon() -> QIcon:
    for rel in (
        ("icons", "icon.ico"),
        ("Branding", "icon.ico"),
        ("logo", "logo.png"),
        ("logo", "mainlogo.png"),
    ):
        path = find_asset(*rel)
        if path:
            return QIcon(str(path))
    return QIcon()
