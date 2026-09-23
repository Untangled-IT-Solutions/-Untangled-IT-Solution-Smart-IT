"""Safe, idempotent provisioning for the required management accounts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool

from app.domain import ROLES, name, now, refs
from app.security import hash_pbkdf2_sha256, normalise_login


class ProvisioningError(RuntimeError):
    """Raised before an unsafe or ambiguous provisioning change."""


@dataclass(frozen=True)
class ManagementTarget:
    key: str
    full_name: str
    fixed_role: str | None
    allowed_roles: frozenset[str]
    password_env: str
    username_env: str


TARGETS = (
    ManagementTarget(
        "zandile", "Zandile Joana Maredi", "Director", frozenset({"Director"}),
        "NEXUS_ZANDILE_TEMP_PASSWORD", "NEXUS_ZANDILE_USERNAME",
    ),
    ManagementTarget(
        "benny", "Benny Moremi", None, frozenset({"Business Lead", "Branch Manager"}),
        "NEXUS_BENNY_TEMP_PASSWORD", "NEXUS_BENNY_USERNAME",
    ),
    ManagementTarget(
        "ubuntu", "Ubuntu Hadebe", "Operations Manager", frozenset({"Operations Manager"}),
        "NEXUS_UBUNTU_TEMP_PASSWORD", "NEXUS_UBUNTU_USERNAME",
    ),
)


def _exact(value: str):
    return {"$regex": "^" + re.escape(value.strip()) + "$", "$options": "i"}


async def _find_employee(db, target: ManagementTarget):
    parts = target.full_name.split()
    query = {
        "$or": [
            {"full_name": _exact(target.full_name)},
            {"name": _exact(target.full_name)},
            {"first_name": _exact(parts[0]), "surname": _exact(parts[-1])},
            {"first_name": _exact(parts[0]), "last_name": _exact(parts[-1])},
        ]
    }
    rows = await db["employees"].find(query).limit(3).to_list(3)
    if not rows:
        raise ProvisioningError(f"Existing employee not found: {target.full_name}.")
    exact_rows = [
        row for row in rows
        if str(row.get("full_name") or row.get("name") or "").strip().casefold()
        == target.full_name.casefold()
    ]
    candidates = exact_rows or rows
    if len(candidates) != 1:
        raise ProvisioningError(
            f"Employee identity is ambiguous for {target.full_name}; resolve duplicates before provisioning."
        )
    return candidates[0]


async def _find_account(db, employee, username_hint: str):
    identity_values = refs(employee)
    clauses: list[dict[str, Any]] = [
        {"employee_id": {"$in": identity_values}},
        {"nexus_employee_id": str(employee["_id"])},
    ]
    if username_hint:
        clauses.extend([
            {"username": _exact(username_hint)},
            {"email": _exact(username_hint)},
        ])
    rows = await db["users"].find({"$or": clauses}).limit(3).to_list(3)
    if len(rows) > 1:
        raise ProvisioningError(
            f"Multiple login accounts match employee {name(employee)}; resolve them before provisioning."
        )
    if not rows:
        return None
    account = rows[0]
    linked_values = {str(value) for value in identity_values}
    linked = (
        str(account.get("employee_id")) in linked_values
        or str(account.get("nexus_employee_id")) == str(employee["_id"])
    )
    same_person = str(account.get("full_name") or "").strip().casefold() == name(employee).strip().casefold()
    if not linked and not (account.get("employee_id") is None and same_person):
        raise ProvisioningError(
            f"Username/email for {name(employee)} belongs to another employee account."
        )
    return account


def _canonical_role(target: ManagementTarget, employee, account):
    if target.fixed_role:
        return target.fixed_role
    for candidate in (employee.get("role"), (account or {}).get("role")):
        canonical = next((item for item in ROLES if item.casefold() == str(candidate or "").strip().casefold()), None)
        if canonical in target.allowed_roles:
            return canonical
    choices = " or ".join(sorted(target.allowed_roles))
    raise ProvisioningError(
        f"{target.full_name} must already use the canonical role {choices}; refusing to guess."
    )


def _username(target: ManagementTarget, employee, account, values: dict[str, str]):
    candidate = (
        values.get(target.username_env)
        or (account or {}).get("username")
        or (account or {}).get("email")
        or employee.get("email")
        or employee.get("email_address")
    )
    username = normalise_login(candidate)
    if not username:
        raise ProvisioningError(
            f"No existing email/username for {target.full_name}; set {target.username_env}."
        )
    return username


async def build_management_plan(db, values: dict[str, str]):
    """Resolve every employee/account before any record is changed."""
    plan = []
    for target in TARGETS:
        employee = await _find_employee(db, target)
        username_hint = normalise_login(
            values.get(target.username_env)
            or employee.get("email")
            or employee.get("email_address")
        )
        account = await _find_account(db, employee, username_hint)
        plan.append({
            "target": target,
            "employee": employee,
            "account": account,
            "role": _canonical_role(target, employee, account),
            "username": _username(target, employee, account, values),
            "action": "update" if account else "create",
        })

    usernames = [item["username"] for item in plan]
    if len(set(usernames)) != len(usernames):
        raise ProvisioningError("Management usernames must be unique.")
    return plan


def public_plan(plan):
    """Return a credential-free description suitable for console output."""
    return [
        {
            "employee": item["target"].full_name,
            "employee_id": str(item["employee"]["_id"]),
            "username": item["username"],
            "role": item["role"],
            "action": item["action"],
        }
        for item in plan
    ]


async def provision_management_accounts(
    db,
    values: dict[str, str],
    *,
    hash_password: Callable[[str], str] = hash_pbkdf2_sha256,
):
    """Link and reset the three accounts without creating employee records."""
    plan = await build_management_plan(db, values)

    passwords = {}
    for item in plan:
        target = item["target"]
        password = values.get(target.password_env) or ""
        if len(password) < 12:
            raise ProvisioningError(f"{target.password_env} must contain at least 12 characters.")
        if normalise_login(password) == item["username"]:
            raise ProvisioningError(f"{target.password_env} must not match the username.")
        passwords[target.key] = password

    # Hash all secrets before the first database mutation.
    hashes = {}
    for item in plan:
        target = item["target"]
        hashes[target.key] = await run_in_threadpool(hash_password, passwords[target.key])

    results = []
    for item in plan:
        target = item["target"]
        employee = item["employee"]
        account = item["account"]
        event = {
            "action": "management-account-provisioned",
            "created_at": now(),
            "note": "Existing employee linked; first-login password change required.",
        }
        fields = {
            "employee_id": employee["_id"],
            "nexus_employee_id": str(employee["_id"]),
            "username": item["username"],
            "username_normalized": item["username"],
            "email": employee.get("email") or employee.get("email_address") or item["username"],
            "full_name": target.full_name,
            "role": item["role"],
            "status": "active",
            "password_hash": hashes[target.key],
            "require_password_change": True,
            "updated_at": now(),
        }
        try:
            if account:
                await db["users"].update_one(
                    {"_id": account["_id"]},
                    {"$set": fields, "$unset": {"password": "", "hashed_password": ""}, "$push": {"history": event}},
                )
                user_id = account["_id"]
            else:
                user_id = ObjectId()
                await db["users"].insert_one({"_id": user_id, **fields, "created_at": now(), "history": [event]})
        except DuplicateKeyError as exc:
            raise ProvisioningError(
                f"A duplicate account key blocked {target.full_name}; no employee record was created."
            ) from exc

        await db["employees"].update_one(
            {"_id": employee["_id"]},
            {"$set": {"role": item["role"], "updated_at": now()}},
        )
        await db["api_sessions"].update_many(
            {"user_id": user_id}, {"$set": {"status": "revoked", "revoked_at": now()}},
        )
        results.append({**public_plan([item])[0], "user_id": str(user_id)})
    return results
