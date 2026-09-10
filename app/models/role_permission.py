"""Role permission definitions."""


ROLE_PERMISSIONS = {
    "Director": ("Executive Briefs", "Company Health", "Compliance"),
    "Super User": ("Submit Sprint Planning Tasks", "Reports", "Operations"),
    "Superuser": ("Submit Sprint Planning Tasks", "Reports", "Operations"),
    "Administrator": ("Manage Staff", "Assign Tasks", "Edit Tasks", "View Reports"),
    "Admin": ("Manage Staff", "Assign Tasks", "Edit Tasks", "View Reports"),
    "Super Admin": ("Manage Staff", "Assign Tasks", "Edit Tasks", "View Reports"),
    "Branch Manager": ("Approvals", "Reports", "Operations", "Manage Staff"),
    "Business Lead": ("Approvals", "Reports", "Operations"),
    "Operations Manager": ("Manage Staff", "Assign Tasks", "Edit Tasks", "View Reports"),
    "Staff": ("View Own Work", "Update Own Work Status"),
    "Intern": ("View Own Work", "Update Own Work Status"),
}

ROLE_MODULES = {
    "Director": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Reports", "Search"),
    "Super User": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Projects", "Reports", "Search"),
    "Superuser": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Projects", "Reports", "Search"),
    "Administrator": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Projects", "Reports", "Search"),
    "Admin": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Projects", "Reports", "Search"),
    "Super Admin": ("Dashboard", "People", "Work", "Attendance", "Calendar", "Approvals", "Office Requests", "Projects", "Reports", "Search"),
    "Branch Manager": ("Dashboard", "People", "Approvals", "Work", "Attendance", "Calendar", "Projects", "Reports", "Search"),
    "Business Lead": ("Dashboard", "Approvals", "Work", "Projects", "Reports", "Search"),
    "Operations Manager": ("Dashboard", "People", "Attendance", "Work", "Calendar", "Approvals", "Office Requests", "Projects", "Search"),
    "Staff": ("Dashboard", "Work", "Attendance", "Calendar", "Office Requests", "Notifications", "Search"),
    "Intern": ("Dashboard", "Work", "Attendance", "Calendar", "Office Requests", "Notifications", "Search"),
}

MANAGEMENT_ROLES = (
    "Director", "Branch Manager", "Business Lead", "Operations Manager",
    "Super User", "Superuser", "Administrator", "Admin", "Super Admin",
)
ACCOUNT_ADMIN_ROLES = (
    "Director", "Branch Manager", "Operations Manager",
    "Administrator", "Admin", "Super Admin",
)


def permissions_for_role(role: str) -> tuple[str, ...]:
    """Return the default access set for a role or staff position."""
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["Staff"])


def can_access_module(role: str, module: str) -> bool:
    """Return whether a role may open a module in the navigation layer."""
    modules = ROLE_MODULES.get(role, ROLE_MODULES["Staff"])
    return module in modules


def can_manage_attendance(role: str) -> bool:
    """Return whether a role may view or operate on other employees' attendance."""
    return role in MANAGEMENT_ROLES


def can_administer_accounts(role: str) -> bool:
    """Return whether a role may create, activate, reset, or relink accounts."""
    return role in ACCOUNT_ADMIN_ROLES
