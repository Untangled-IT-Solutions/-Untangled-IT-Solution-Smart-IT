"""Plan or apply required management login provisioning.

Passwords are accepted only through environment variables so they do not leak
into shell history or process arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import close_db, connect_db, get_db
from app.management_provisioning import (
    ProvisioningError,
    build_management_plan,
    provision_management_accounts,
    public_plan,
)


async def run(apply: bool):
    await connect_db()
    try:
        values = dict(os.environ)
        plan = await build_management_plan(get_db(), values)
        if not apply:
            print(json.dumps({"mode": "plan", "changes": public_plan(plan)}, indent=2))
            return
        result = await provision_management_accounts(get_db(), values)
        print(json.dumps({"mode": "applied", "accounts": result}, indent=2))
    finally:
        await close_db()


def main():
    parser = argparse.ArgumentParser(description="Provision the three required Nexus management accounts.")
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply the reviewed plan. Temporary passwords must be supplied through the documented environment variables.",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(args.apply))
    except (ProvisioningError, RuntimeError) as exc:
        print(f"Provisioning stopped: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
