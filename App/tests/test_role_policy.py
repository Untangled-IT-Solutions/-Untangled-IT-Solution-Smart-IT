"""Canonical Untangled role policy tests."""

from app.models.account import UserAccount
from app.models.role_permission import (
    ACCOUNT_ADMIN_ROLES,
    MANAGEMENT_ROLES,
    can_administer_accounts,
    can_manage_attendance,
    permissions_for_role,
)


def test_business_lead_replaces_branch_manager_policy() -> None:
    assert "Branch Manager" not in MANAGEMENT_ROLES
    assert "Branch Manager" not in ACCOUNT_ADMIN_ROLES
    assert can_manage_attendance("Business Lead")
    assert not can_administer_accounts("Business Lead")
    assert permissions_for_role("Branch Manager") == permissions_for_role("Staff")


def test_account_admin_roles_are_director_and_operations_manager() -> None:
    director = UserAccount(1, 1, "zandile", "Zandile Johanna Maredi", "Director")
    business_lead = UserAccount(2, 2, "benny", "Benny Moremi", "Business Lead")
    operations = UserAccount(3, 3, "ubuntu", "Ubuntu Hadebe", "Operations Manager")

    assert director.is_admin
    assert operations.is_admin
    assert not business_lead.is_admin
