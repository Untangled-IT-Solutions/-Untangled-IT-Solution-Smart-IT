"""Configuration loading without secrets."""

from app.utils import config


def test_api_base_url_configured():
    assert isinstance(config.API_BASE_URL, str)
    assert config.API_BASE_URL.startswith("http")


def test_company_metadata():
    assert "Untangled" in config.COMPANY_NAME
    assert config.PASSWORD_MIN_LENGTH >= 8


def test_env_example_has_no_secrets():
    text = open(".env.example", encoding="utf-8").read().lower()
    for banned in ("password=", "mongodb+srv://", "jwt_secret=", "secret_key="):
        assert banned not in text
