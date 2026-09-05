"""Application configuration – production ready."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root or next to the executable
_BASE = Path(__file__).resolve().parents[2]
load_dotenv(_BASE / ".env")
load_dotenv(Path.cwd() / ".env")

# ---------------------------------------------------------------------------
# Backend API (single source of truth – no direct MongoDB from desktop)
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://untangled-nexus-api.onrender.com").rstrip("/")
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production").lower()

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
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = _BASE
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

for _d in (DATA_DIR, LOG_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------
from app.__version__ import __version__ as APP_VERSION  # single source of truth

COMPANY_NAME = "Untangled Nexus"
COMPANY_LEGAL_NAME = "Untangled IT Solutions"
SUBTITLE = "Internal Operations Platform"
