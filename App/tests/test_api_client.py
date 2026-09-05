"""Backend API client initialization and environment safety."""

from app.services.backend_api_client import BackendAPIClient, BackendAPIError


def test_client_defaults_to_production_when_env_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("API_BASE_URL", raising=False)
    client = BackendAPIClient()
    assert "localhost" not in client.base_url
    assert client._allow_dev_fallback is False


def test_client_honours_explicit_api_base_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_BASE_URL", "https://example-api.test")
    client = BackendAPIClient()
    assert client.base_url == "https://example-api.test"


def test_client_dev_can_use_localhost(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("API_BASE_URL", raising=False)
    client = BackendAPIClient()
    assert client.base_url == BackendAPIClient.LOCAL_URL
    assert client._allow_dev_fallback is True


def test_backend_api_error_has_status():
    err = BackendAPIError("nope", status_code=503)
    assert err.status_code == 503
