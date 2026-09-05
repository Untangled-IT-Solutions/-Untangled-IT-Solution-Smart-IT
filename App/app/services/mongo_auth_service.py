"""Compatibility shim – prefer app.services.backend_auth_service.BackendAuthService.

Historically named MongoAuthService even though the desktop never talks to MongoDB.
"""

from app.services.backend_auth_service import BackendAuthService

# Backwards-compatible alias
MongoAuthService = BackendAuthService

__all__ = ["BackendAuthService", "MongoAuthService"]
