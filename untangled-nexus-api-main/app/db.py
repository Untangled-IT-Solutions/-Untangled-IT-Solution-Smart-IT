from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse, unquote

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

_client: Any | None = None
_db_name: str | None = None


def _resolve_db_name(uri: str) -> str:
    """
    Resolve MongoDB database name safely.

    Atlas URIs often look like:
      mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true
    (no path DB) — host contains dots and must NOT be used as the DB name.
    """
    # Explicit override wins
    explicit = (os.getenv("MONGODB_DB") or os.getenv("MONGO_DB") or "").strip()
    if explicit and "." not in explicit and "/" not in explicit:
        return explicit

    try:
        # urlparse works for mongodb:// ; for mongodb+srv:// path is still usable
        parsed = urlparse(uri)
        path = (parsed.path or "").lstrip("/")
        if path:
            # path may be "dbname" or "dbname/extra"
            name = unquote(path.split("/")[0]).strip()
            if name and "." not in name and name.lower() not in ("mongodb", "mongodb+srv"):
                return name
    except Exception:
        pass

    # Regex fallback: ...mongodb.net/dbname?...
    m = re.search(r"mongodb(?:\+srv)?://[^/]+/([^/?]+)", uri)
    if m:
        name = unquote(m.group(1)).strip()
        if name and "." not in name:
            return name

    # Safe default used by this project
    return "untangled_its"


async def connect_db() -> None:
    global _client, _db_name
    settings = get_settings()
    if settings.local_ephemeral_db:
        if settings.node_env != "staging":
            raise RuntimeError("LOCAL_EPHEMERAL_DB is allowed only when NODE_ENV=staging")
        if settings.local_ephemeral_ack != "localhost-only" or os.getenv("RENDER"):
            raise RuntimeError("Ephemeral staging is restricted to an acknowledged local host")
        if len(settings.nexus_staging_password) < 12:
            raise RuntimeError("NEXUS_STAGING_PASSWORD must contain at least 12 characters")
        try:
            from mongomock_motor import AsyncMongoMockClient
        except ImportError as exc:
            raise RuntimeError(
                "Local staging requires requirements-dev.txt"
            ) from exc
        _db_name = "untangled_its_staging_ephemeral"
        _client = AsyncMongoMockClient(tz_aware=True)
        await ensure_indexes(get_db())
        from app.local_staging import seed_local_staging
        await seed_local_staging(get_db(), settings.nexus_staging_password)
        print(f"Local ephemeral MongoDB ready (database={_db_name})")
        return
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required")

    _db_name = settings.mongodb_db if "mongodb_db" in settings.model_fields_set else _resolve_db_name(settings.mongodb_uri)
    _client = AsyncIOMotorClient(
        settings.mongodb_uri,
        maxPoolSize=settings.mongodb_max_pool_size,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=10000,
    )
    # Verify connectivity
    await _client.admin.command("ping")
    await ensure_indexes(get_db())
    print(f"MongoDB connected (database={_db_name})")


async def close_db() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("Database not connected")
    name = _db_name or "untangled_its"
    # Final guard — never allow host-like names
    if not name or "." in name or " " in name:
        name = "untangled_its"
    return _client[name]


async def ensure_indexes(db):
    # New canonical keys protect newly administered accounts without rewriting
    # legacy employee IDs or deleting duplicates from an existing database.
    await db['users'].create_index('nexus_employee_id', unique=True, sparse=True, name='nexus_employee_identity_unique')
    await db['users'].create_index('username_normalized', unique=True, sparse=True, name='nexus_username_unique')
    await db['login_attempts'].create_index('expires_at', expireAfterSeconds=0, name='nexus_login_attempt_expiry')
    await db['api_sessions'].create_index('token_hash', sparse=True, name='nexus_token_hash')
    await db['api_sessions'].create_index('expires_at', expireAfterSeconds=0, name='nexus_session_expiry')
    await db['notifications'].create_index(
        [('employee_id', 1), ('read', 1), ('created_at', -1)],
        name='nexus_notification_inbox',
    )
    await db['notifications'].create_index(
        [('reference_type', 1), ('reference_id', 1)],
        sparse=True,
        name='nexus_notification_reference',
    )
    await db['audit_events'].create_index(
        [('created_at', -1), ('employee_id', 1)],
        name='nexus_audit_timeline',
    )
    await db['documents'].create_index([('employee_id', 1), ('expiry_date', 1)], name='nexus_document_employee_expiry')
    await db['documents'].create_index([('expiry_status', 1), ('expiry_date', 1)], name='nexus_document_expiry_status')
