"""Authentication service structure (no live credentials)."""

from app.services.backend_api_client import BackendAPIClient
from app.services.backend_auth_service import BackendAuthService
from app.services.auth_service import AuthService
from app.services.mongo_auth_service import MongoAuthService


def test_backend_auth_service_constructs():
    client = BackendAPIClient(base_url="https://example-api.test")
    svc = BackendAuthService(client)
    assert svc is not None


def test_mongo_auth_alias_is_backend_auth():
    assert MongoAuthService is BackendAuthService


def test_auth_service_constructs():
    client = BackendAPIClient(base_url="https://example-api.test")
    backend_auth = BackendAuthService(client)
    auth = AuthService(backend_auth)
    assert auth is not None


def test_backend_auth_tracks_required_password_change(monkeypatch):
    client = BackendAPIClient(base_url="https://example-api.test")
    monkeypatch.setattr(
        client,
        "login",
        lambda username, password: {
            "token": "test-token",
            "user": {"id": "u1", "require_password_change": True},
            "employee": {"id": "e1"},
        },
    )
    calls = []
    monkeypatch.setattr(client, "change_password", lambda current, new: calls.append((current, new)))
    service = BackendAuthService(client)
    service.authenticate("person@example.test", "temporary")
    assert service.requires_password_change is True
    service.change_password("temporary", "new-password")
    assert service.requires_password_change is False
    assert calls == [("temporary", "new-password")]
