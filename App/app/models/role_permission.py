"""Role permission definitions."""


ROLE_PERMISSIONS = {
    "Director": ("Executive Briefs", "Company Health", "Compliance"),
    "Business Lead": ("Approvals", "Reports", "Operations"),
    "Operations Manager": ("Manage Staff", "Assign Tasks", "Edit Tasks", "View Reports"),
    "Staff": ("View Own Work", "Update Own Work Status"),
    "Intern": ("View Own Work", "Update Own Work Status"),
}

ROLE_MODULES = {
    "Director": ("Dashboard", "People", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Tasks", "Reports", "Quote Management", "Order Management", "User Management", "Settings"),
    "Business Lead": ("Dashboard", "Attendance", "Approvals", "Notifications", "Projects", "Tasks", "Reports", "Quote Management", "Order Management", "Settings"),
    "Operations Manager": ("Dashboard", "People", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Projects", "Tasks", "Reports", "Quote Management", "Order Management", "User Management", "Settings"),
    "Staff": ("Dashboard", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Tasks", "Settings"),
    "Intern": ("Dashboard", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Tasks", "Settings"),
    "Super Admin": ("Dashboard", "People", "Attendance", "Calendar", "Approvals", "Office Requests", "Notifications", "Projects", "Tasks", "Reports", "Quote Management", "Order Management", "User Management", "Settings"),
}

MANAGEMENT_ROLES = ("Director", "Business Lead", "Operations Manager")
ACCOUNT_ADMIN_ROLES = ("Director", "Operations Manager")


def permissions_for_role(role: str) -> tuple[str, ...]:
    """Return the default access set for a role or staff position."""
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["Staff"])


def can_access_module(role: str, module: str) -> bool:
    """Return whether a role may open a module in the navigation layer."""
    modules = ROLE_MODULES.get(role, ROLE_MODULES["Staff"])
    return module in modules


def can_manage_attendance(role: str) -> bool:
    """Return whether a role may view or operate on other employees' attendance."""
    return role in ("Director", "Business Lead", "Operations Manager", "Super Admin")


def can_administer_accounts(role: str) -> bool:
    """Return whether a role may create, activate, reset, or relink accounts."""
    return role in ACCOUNT_ADMIN_ROLES
