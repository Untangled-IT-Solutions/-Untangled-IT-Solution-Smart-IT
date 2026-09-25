"""Configuration loading without secrets."""

import os
import subprocess
import sys

from app.utils import config


def test_api_base_url_configured():
    assert isinstance(config.API_BASE_URL, str)
    assert config.API_BASE_URL.startswith("http")


def test_company_metadata():
    assert "Untangled" in config.COMPANY_NAME
    assert config.PASSWORD_MIN_LENGTH >= 8


def test_production_channel_has_unambiguous_name():
    assert config.APP_CHANNEL == "production"
    assert config.COMPANY_NAME == "Untangled Nexus"


def test_staging_channel_is_visible_in_application_name():
    env = dict(os.environ, APP_CHANNEL="staging", ENVIRONMENT="staging")
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "from app.utils.config import COMPANY_NAME; print(COMPANY_NAME)",
        ],
        env=env,
        text=True,
    )
    assert output.strip() == "Untangled Nexus [STAGING]"


def test_env_example_has_no_secrets():
    text = open(".env.example", encoding="utf-8").read().lower()
    for banned in ("password=", "mongodb+srv://", "jwt_secret=", "secret_key="):
        assert banned not in text
