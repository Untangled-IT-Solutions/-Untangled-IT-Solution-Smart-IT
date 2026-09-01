"""Static navigation smoke test for Untangled Nexus."""
from pathlib import Path

EXPECTED = [
    "Dashboard", "People", "Attendance", "Calendar", "Approvals",
    "Office Requests", "Notifications", "Projects", "Tasks", "Reports",
    "Quote Management", "Order Management", "Quote Sync",
    "User Management", "Settings",
]

source = Path(__file__).with_name("controllers").joinpath("app_controller.py").read_text(encoding="utf-8")
missing = [name for name in EXPECTED if f'destination == "{name}"' not in source]
if missing:
    raise SystemExit(f"NAVIGATION_ROUTE_TEST_FAILED: {missing}")
print(f"NAVIGATION_ROUTE_TEST_OK: {len(EXPECTED)}/{len(EXPECTED)} routes present")
