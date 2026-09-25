"""Application configuration – production ready."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

def _get_base_dir() -> Path:
    """Return the correct base directory for both development and frozen (PyInstaller) builds."""
    if getattr(sys, "frozen", False):
        # Running as a packaged executable
        # sys._MEIPASS is the temp folder where PyInstaller extracts files
        return Path(sys._MEIPASS)
    # Running from source
    return Path(__file__).resolve().parents[2]

_BASE = _get_base_dir()

# Load .env – try several sensible locations
load_dotenv(_BASE / ".env")
load_dotenv(Path.cwd() / ".env")
if getattr(sys, "frozen", False):
    # Also look next to the .exe
    load_dotenv(Path(sys.executable).parent / ".env")

# ---------------------------------------------------------------------------
# Backend API (single source of truth – no direct MongoDB from desktop)
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://untangled-nexus-api.onrender.com").rstrip("/")
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production").lower()
APP_CHANNEL: str = os.getenv("APP_CHANNEL", ENVIRONMENT).strip().lower()

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
PASSWORD_MIN_LENGTH = 8
SESSION_EXPIRY_HOURS = 8

# ---------------------------------------------------------------------------
# Attendance defaults
# ---------------------------------------------------------------------------
WORK_HOURS_PER_DAY = 8
LUNCH_BREAK_DURATION = 60  # minutes
BREAK_DURATION = 15

# ---------------------------------------------------------------------------
# Paths – writable locations for logs / cache / data
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    # Installed app → use a writable folder under LocalAppData
    _USER_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "UntangledNexus"
    PROJECT_ROOT = Path(sys.executable).parent
    DATA_DIR = _USER_DATA / "data"
    LOG_DIR = _USER_DATA / "logs"
    CACHE_DIR = _USER_DATA / "cache"
else:
    PROJECT_ROOT = _BASE
    DATA_DIR = PROJECT_ROOT / "data"
    LOG_DIR = PROJECT_ROOT / "logs"
    CACHE_DIR = PROJECT_ROOT / "cache"

for _d in (DATA_DIR, LOG_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
from app.__version__ import __version__ as APP_VERSION  # single source of truth

COMPANY_NAME = (
    "Untangled Nexus"
    if APP_CHANNEL == "production"
    else f"Untangled Nexus [{APP_CHANNEL.upper()}]"
)
COMPANY_LEGAL_NAME = "Untangled IT Solutions"
SUBTITLE = "Internal Operations Platform"
