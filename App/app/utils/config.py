# app/utils/config.py
"""Application configuration with all constants."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================
# MongoDB Configuration
# ============================================================
# Prefer API_BASE_URL for shared business data (quotes, orders, users).
# Direct Mongo access is only for controlled internal operations.
# There is intentionally no hardcoded credential fallback.
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "untangled_its")

if not MONGO_URI:
    # Soft warning at import time; callers that need Mongo must check.
    # Prefer Backend API (API_BASE_URL) for production desktop usage.
    pass

# ============================================================
# Backend API (preferred for Work desktop app)
# ============================================================
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:10000")

# ============================================================
# Password Security
# ============================================================
PASSWORD_MIN_LENGTH = 8
PASSWORD_HASH_ITERATIONS = 260000
PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_RESET_TOKEN_EXPIRY = 3600  # 1 hour in seconds

# ============================================================
# Session Settings
# ============================================================
SESSION_EXPIRY_HOURS = 8

# ============================================================
# Attendance Settings
# ============================================================
WORK_HOURS_PER_DAY = 8
LUNCH_BREAK_DURATION = 60  # minutes
BREAK_DURATION = 15  # minutes

# ============================================================
# Application Paths
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# ============================================================
# Company Information
# ============================================================
COMPANY_NAME = "Untangled Nexus"
COMPANY_LEGAL_NAME = "Untangled IT Solutions"
