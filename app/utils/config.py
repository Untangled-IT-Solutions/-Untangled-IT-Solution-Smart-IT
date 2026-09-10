
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
# Use the database that has your quotes (test database)
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "test")  # Changed to "test" for quotes

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
# Company Information (from Theme - kept for compatibility)
# ============================================================
COMPANY_NAME = "Untangled Nexus"
COMPANY_LEGAL_NAME = "Untangled IT Solutions"
# app/utils/config.py
"""Application configuration with all constants."""