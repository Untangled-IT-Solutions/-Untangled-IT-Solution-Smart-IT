from bson import ObjectId
import pytest
from mongomock_motor import AsyncMongoMockClient

from app.management_provisioning import (
    ProvisioningError,
    build_management_plan,
    provision_management_accounts,
)
from app.security import verify_password


PASSWORDS = {
    "NEXUS_ZANDILE_TEMP_PASSWORD": "zandile-temporary-phrase",
    "NEXUS_BENNY_TEMP_PASSWORD": "benny-temporary-phrase",
    "NEXUS_UBUNTU_TEMP_PASSWORD": "ubuntu-temporary-phrase",
}


async def employees(db, benny_role="Branch Manager"):
    for full_name, role, email in (
        ("Zandile Joana Maredi", "Staff", "zandile@test.invalid"),
        ("Benny Moremi", benny_role, "benny@test.invalid"),
        ("Ubuntu Hadebe", "Staff", "ubuntu@test.invalid"),
    ):
        await db.employees.insert_one({
            "_id": ObjectId(), "full_name": full_name, "role": role,
            "email": email, "status": "active",
        })


async def test_provisioning_links_existing_employees_without_duplicates():
    db = AsyncMongoMockClient(tz_aware=True).phase7
    await employees(db)
    before_ids = {row["_id"] async for row in db.employees.find({})}

    result = await provision_management_accounts(db, PASSWORDS)
    assert [item["role"] for item in result] == ["Director", "Branch Manager", "Operations Manager"]
    assert await db.employees.count_documents({}) == 3
    assert {row["_id"] async for row in db.employees.find({})} == before_ids
    assert await db.users.count_documents({}) == 3

    expected = {
        "Zandile Joana Maredi": ("Director", PASSWORDS["NEXUS_ZANDILE_TEMP_PASSWORD"]),
        "Benny Moremi": ("Branch Manager", PASSWORDS["NEXUS_BENNY_TEMP_PASSWORD"]),
        "Ubuntu Hadebe": ("Operations Manager", PASSWORDS["NEXUS_UBUNTU_TEMP_PASSWORD"]),
    }
    async for user in db.users.find({}):
        role, password = expected[user["full_name"]]
        assert user["role"] == role
        assert user["status"] == "active"
        assert user["require_password_change"] is True
        assert verify_password(password, user["password_hash"])
        assert "password" not in user and "hashed_password" not in user

    # Reapplying updates the same accounts and never duplicates employees/users.
    await provision_management_accounts(db, PASSWORDS)
    assert await db.employees.count_documents({}) == 3
    assert await db.users.count_documents({}) == 3


async def test_plan_refuses_to_guess_benny_role_before_writing():
    db = AsyncMongoMockClient(tz_aware=True).phase7_bad_role
    await employees(db, benny_role="Staff")
    with pytest.raises(ProvisioningError, match="refusing to guess"):
        await build_management_plan(db, {})
    assert await db.users.count_documents({}) == 0


async def test_plan_refuses_ambiguous_employee_records():
    db = AsyncMongoMockClient(tz_aware=True).phase7_duplicates
    await employees(db)
    await db.employees.insert_one({
        "_id": ObjectId(), "full_name": "Ubuntu Hadebe",
        "role": "Operations Manager", "email": "other@test.invalid",
    })
    with pytest.raises(ProvisioningError, match="ambiguous"):
        await build_management_plan(db, {})
    assert await db.users.count_documents({}) == 0
