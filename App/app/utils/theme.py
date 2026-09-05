"""Centralized Untangled Nexus theme constants and preference storage."""

from pathlib import Path
import json

import customtkinter as ctk


class Theme:
    """Application color, font, spacing, branding, and mode tokens."""

    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    PREFERENCES_PATH = PROJECT_ROOT / "data" / "preferences.json"
    LOGO_PATH = PROJECT_ROOT / "assets" / "logo" / "logo.png"
    LOGO_DARK_PATH = PROJECT_ROOT / "assets" / "logo" / "logo_dark.png"
    
    # ✅ FIXED: Changed from .png to .ico to match iconbitmap() requirements
    ICON_PATH = PROJECT_ROOT / "assets" / "icons" / "icon.ico" 

    COMPANY_NAME = "Untangled Nexus"
    COMPANY_LEGAL_NAME = "Untangled IT Solutions"
    SUBTITLE = "Internal Operations Platform"
    VERSION = __import__("app.__version__", fromlist=["__version__"]).__version__

    MODES = ("dark", "light")
    CURRENT_MODE = "light"

    _PALETTES = {
        "dark": {
            "BG": "#10141C",
            "PANEL": "#171C27",
            "PANEL_ALT": "#1D2432",
            "BORDER": "#2A3141",
            "TEXT": "#FFFFFF",
            "MUTED_TEXT": "#B7C0CC",
            "ACCENT": "#7CB518",
            "ACCENT_HOVER": "#5E8E12",
            "SUCCESS": "#22C55E",
            "WARNING": "#F59E0B",
            "DANGER": "#EF4444",
            "DANGER_HOVER": "#DC2626",
            "SUCCESS_HOVER": "#16A34A",
            "INFO": "#38BDF8",
            "PURPLE": "#8B5CF6",
        },
        "light": {
            "BG": "#F7F9F8",
            "PANEL": "#FFFFFF",
            "PANEL_ALT": "#EEF3F0",
            "BORDER": "#DCE5DF",
            "TEXT": "#1F2723",
            "MUTED_TEXT": "#526158",
            "ACCENT": "#6FA814",
            "ACCENT_HOVER": "#5E8E12",
            "SUCCESS": "#15803D",
            "WARNING": "#B45309",
            "DANGER": "#B91C1C",
            "DANGER_HOVER": "#991B1B",
            "SUCCESS_HOVER": "#166534",
            "INFO": "#0369A1",
            "PURPLE": "#6D28D9",
        },
    }

    SIDEBAR_WIDTH = 248
    HEADER_HEIGHT = 76
    RADIUS = 8
    CARD_BORDER_WIDTH = 0
    SPACING = 16

    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = (FONT_FAMILY, 30, "bold")
    FONT_HEADING = (FONT_FAMILY, 22, "bold")
    FONT_BODY = (FONT_FAMILY, 14)
    FONT_SMALL = (FONT_FAMILY, 12)
    FONT_BUTTON = (FONT_FAMILY, 13, "bold")

    BG = _PALETTES["light"]["BG"]
    PANEL = _PALETTES["light"]["PANEL"]
    PANEL_ALT = _PALETTES["light"]["PANEL_ALT"]
    BORDER = _PALETTES["light"]["BORDER"]
    TEXT = _PALETTES["light"]["TEXT"]
    MUTED_TEXT = _PALETTES["light"]["MUTED_TEXT"]
    ACCENT = _PALETTES["light"]["ACCENT"]
    ACCENT_HOVER = _PALETTES["light"]["ACCENT_HOVER"]
    SUCCESS = _PALETTES["light"]["SUCCESS"]
    WARNING = _PALETTES["light"]["WARNING"]
    DANGER = _PALETTES["light"]["DANGER"]
    DANGER_HOVER = _PALETTES["light"]["DANGER_HOVER"]
    SUCCESS_HOVER = _PALETTES["light"]["SUCCESS_HOVER"]
    INFO = _PALETTES["light"]["INFO"]
    PURPLE = _PALETTES["light"]["PURPLE"]

    @classmethod
    def load_preference(cls) -> str:
        """Load the saved theme mode, defaulting to Untangled dark."""
        try:
            data = json.loads(cls.PREFERENCES_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return "light"
        mode = str(data.get("theme", "dark")).lower()
        return mode if mode in cls.MODES else "light"

    @classmethod
    def save_preference(cls, mode: str) -> None:
        """Persist the user's chosen theme mode."""
        cls.PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.PREFERENCES_PATH.write_text(
            json.dumps({"theme": mode}, indent=2), encoding="utf-8"
        )

    @classmethod
    def apply_mode(cls, mode: str | None = None, persist: bool = False) -> str:
        """Apply a light or dark mode to class tokens and CustomTkinter."""
        selected = (mode or cls.load_preference()).lower()
        if selected not in cls.MODES:
            selected = "dark"
        palette = cls._PALETTES[selected]
        for key, value in palette.items():
            setattr(cls, key, value)
        cls.CURRENT_MODE = selected
        ctk.set_appearance_mode(selected)
        ctk.set_default_color_theme("green")
        if persist:
            cls.save_preference(selected)
        return selected

    @classmethod
    def toggle_mode(cls) -> str:
        """Switch between dark and light modes and save the preference."""
        next_mode = "light" if cls.CURRENT_MODE == "dark" else "dark"
        return cls.apply_mode(next_mode, persist=True)

    @classmethod
    def logo_for_current_mode(cls) -> Path:
        """Return the best logo for the active background."""
        return cls.LOGO_DARK_PATH if cls.CURRENT_MODE == "dark" else cls.LOGO_PATH