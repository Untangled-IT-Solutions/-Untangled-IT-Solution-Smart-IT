from types import SimpleNamespace

import pytest

from app import db as database
from app.local_staging import STAGING_ACCOUNTS, seed_local_staging


async def test_local_staging_seed_creates_disposable_role_accounts(api):
    _client, db, _people, _headers = api
    await db.users.delete_many({})
    await db.employees.delete_many({})
    await seed_local_staging(db, "local-staging-password")
    assert await db.users.count_documents({}) == len(STAGING_ACCOUNTS)
    assert await db.employees.count_documents({}) == len(STAGING_ACCOUNTS)
    assert await db.users.count_documents({"role": "Director"}) == 1
    assert await db.tasks.count_documents({}) >= 3
    assert await db.approvals.count_documents({"current_stage": "Director"}) == 1


async def test_ephemeral_database_requires_localhost_acknowledgement(monkeypatch):
    settings = SimpleNamespace(
        local_ephemeral_db=True,
        local_ephemeral_ack="",
        node_env="staging",
        nexus_staging_password="local-staging-password",
    )
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    monkeypatch.delenv("RENDER", raising=False)
    with pytest.raises(RuntimeError, match="restricted to an acknowledged local host"):
        await database.connect_db()
