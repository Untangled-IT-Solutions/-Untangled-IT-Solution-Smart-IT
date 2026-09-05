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
