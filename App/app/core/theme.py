"""Exact Untangled Nexus light palette (from original Theme + LoginView)."""

from pathlib import Path

# Login / brand greens (from login_view.py)
PRIMARY = "#60920D"
PRIMARY_HOVER = "#74AE10"
PRIMARY_DARK = "#3F6508"
PRIMARY_SOFT = "#E8F5E0"
BRIGHT = "#6CE000"

# App shell (Theme light palette)
BG = "#F7F9F8"
PANEL = "#FFFFFF"
PANEL_ALT = "#EEF3F0"
BORDER = "#DCE5DF"
TEXT = "#1F2723"
MUTED = "#526158"
ACCENT = "#6FA814"
ACCENT_HOVER = "#5E8E12"
SUCCESS = "#15803D"
WARNING = "#B45309"
DANGER = "#B91C1C"
INFO = "#0369A1"

COMPANY_NAME = "Untangled Nexus"
COMPANY_LEGAL = "Untangled IT Solutions"
SUBTITLE = "Internal Operations Platform"
VERSION = "2.0.0"

SIDEBAR_WIDTH = 248
HEADER_HEIGHT = 76

# Nav item accent colours (match original sidebar chips)
NAV_COLORS = {
    "Dashboard": "#3B82F6",
    "People": "#A855F7",
    "Attendance": "#22C55E",
    "Calendar": "#EC4899",
    "Approvals": "#10B981",
    "Office Requests": "#F59E0B",
    "Notifications": "#EF4444",
    "Projects": "#0D9488",
    "Tasks": "#F97316",
    "Reports": "#6366F1",
    "Quote Management": "#A855F7",
    "Order Management": "#0EA5E9",
    "Quote Sync": "#06B6D4",
    "User Management": "#64748B",
    "Settings": "#6B7280",
}

NAV_ICONS = {
    "Dashboard": "⌂",
    "People": "👥",
    "Attendance": "⏱",
    "Calendar": "▦",
    "Approvals": "☑",
    "Office Requests": "▤",
    "Notifications": "🔔",
    "Projects": "📁",
    "Tasks": "✓",
    "Reports": "▥",
    "Quote Management": "💬",
    "Order Management": "📦",
    "Quote Sync": "↻",
    "User Management": "👤",
    "Settings": "⚙",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def asset_candidates(*parts: str) -> list[Path]:
    """Search app assets and typical App install locations."""
    root = project_root()
    paths = [
        root / "app" / "assets" / Path(*parts),
        root / "assets" / Path(*parts),
        root.parent / "assets" / Path(*parts),
        root.parent / "App" / "assets" / Path(*parts),
        root.parent / "app" / "assets" / Path(*parts),
    ]
    # also one level up from cwd patterns
    cwd = Path.cwd()
    paths += [
        cwd / "assets" / Path(*parts),
        cwd / "app" / "assets" / Path(*parts),
        cwd / "App" / "assets" / Path(*parts),
    ]
    return paths


def find_asset(*parts: str) -> Path | None:
    for p in asset_candidates(*parts):
        if p.is_file():
            return p
    return None


APP_QSS = f"""
* {{
    font-family: "Segoe UI";
}}
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QFrame#sidebar {{
    background-color: {PANEL};
    border-right: 1px solid {BORDER};
}}
QFrame#topBar {{
    background-color: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QFrame#card {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#notifCard {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QPushButton {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{ background-color: {PRIMARY_HOVER}; }}
QPushButton:disabled {{ background-color: #A8B896; color: #F5F5F5; }}
QPushButton#secondary {{
    background-color: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QPushButton#secondary:hover {{ background-color: {BORDER}; }}
QPushButton#danger {{ background-color: {DANGER}; }}
QPushButton#danger:hover {{ background-color: #991B1B; }}
QPushButton#success {{ background-color: {SUCCESS}; }}
QPushButton#warning {{ background-color: {WARNING}; color: white; }}
QPushButton#navBtn {{
    background-color: transparent;
    color: {TEXT};
    text-align: left;
    padding: 10px 12px;
    border-radius: 12px;
    font-weight: 500;
    font-size: 13px;
}}
QPushButton#navBtn:hover {{ background-color: {PANEL_ALT}; }}
QLineEdit, QComboBox, QTextEdit {{
    background-color: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    selection-background-color: {PRIMARY_SOFT};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1.5px solid {PRIMARY}; }}
QLabel#title {{ font-size: 22px; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ font-size: 12px; color: {MUTED}; }}
QLabel#muted {{ color: {MUTED}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #C5D0C8; border-radius: 5px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def apply_app_style(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
