# app/controllers/user_management_controller.py
"""User management controller for creating and managing users."""

from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId

try:
    from app.services.mongo_auth_service import MongoAuthService
except ImportError:
    MongoAuthService = None

from app.services.mongodb_service import MongoDBService


class UserManagementController:
    """Controller for user management operations."""

    def __init__(
        self,
        auth_service=None,  # Make optional
        mongodb: MongoDBService = None,
    ):
        self._auth = auth_service
        self._mongo = mongodb

    def _check_auth(self):
        """Check if authentication service is available."""
        if not self._auth:
            raise ValueError("MongoDB authentication service is not available. Please check MongoDB connection.")

    # ============================================================
    # USER CREATION METHODS
    # ============================================================

    def create_user_with_password(
        self,
        employee_id: str,
        username: str,
        password: str,
        role: str = "Staff",
        active: bool = True,
    ) -> Dict[str, Any]:
        """Create a user with a specific password."""
        self._check_auth()
        employee_oid = ObjectId(employee_id)
        return self._auth.create_user(
            employee_id=employee_oid,
            username=username,
            password=password,
            role=role,
            active=active,
        )

    def create_user_with_generated_password(
        self,
        employee_id: str,
        username: str,
        role: str = "Staff",
        active: bool = True,
    ) -> Tuple[Dict[str, Any], str]:
        """Create a user with an auto-generated password."""
        self._check_auth()
        employee_oid = ObjectId(employee_id)
        return self._auth.create_user_with_generated_password(
            employee_id=employee_oid,
            username=username,
            role=role,
            active=active,
        )

    def create_user_from_employee(
        self,
        employee_id: str,
        username: Optional[str] = None,
        role: str = "Staff",
        active: bool = True,
    ) -> Tuple[Dict[str, Any], str]:
        """Create a user from an employee record with auto-generated username and password."""
        self._check_auth()
        employee_oid = ObjectId(employee_id)
        
        # Get employee details
        employee = self._auth.get_employee_by_id(employee_oid)
        if not employee:
            raise ValueError("Employee not found.")

        # Generate username from employee name
        if username is None:
            username = self._generate_username(employee["full_name"])
            username = self._ensure_unique_username(username)

        return self._auth.create_user_with_generated_password(
            employee_id=employee_oid,
            username=username,
            role=role,
            active=active,
        )

    def _generate_username(self, full_name: str) -> str:
        """Generate a username from full name."""
        parts = full_name.lower().split()
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return parts[0] if parts else "user"

    def _ensure_unique_username(self, base_username: str) -> str:
        """Ensure the username is unique."""
        self._check_auth()
        users = self._auth.list_users(include_inactive=True)
        existing_usernames = {u["username"] for u in users}
        
        if base_username not in existing_usernames:
            return base_username
        
        # Add a number suffix
        counter = 1
        while f"{base_username}{counter}" in existing_usernames:
            counter += 1
        return f"{base_username}{counter}"

    # ============================================================
    # USER MANAGEMENT METHODS
    # ============================================================

    def get_all_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """Get all users with employee details."""
        self._check_auth()
        users = self._auth.list_users(include_inactive)
        # Add employee details to each user
        for user in users:
            try:
                employee = self._auth.get_employee_by_id(user["employee_id"])
                if employee:
                    user["employee_full_name"] = employee.get("full_name")
                    user["employee_department"] = employee.get("department")
                    user["employee_position"] = employee.get("position")
            except Exception:
                pass
        return users

    def reset_user_password(self, user_id: str, new_password: str) -> None:
        """Reset a user's password."""
        self._check_auth()
        self._auth.reset_password(ObjectId(user_id), new_password)

    def reset_user_password_generated(self, user_id: str) -> str:
        """Reset a user's password with a generated one."""
        self._check_auth()
        new_password = self._auth.generate_secure_password()
        self._auth.reset_password(ObjectId(user_id), new_password)
        return new_password

    def set_user_status(self, user_id: str, active: bool) -> None:
        """Activate or deactivate a user."""
        self._check_auth()
        self._auth.update_user(ObjectId(user_id), active=active)

    def set_user_role(self, user_id: str, role: str) -> None:
        """Change a user's role."""
        self._check_auth()
        self._auth.update_user(ObjectId(user_id), role=role)

    def delete_user(self, user_id: str) -> None:
        """Delete a user account."""
        self._check_auth()
        self._auth.delete_user(ObjectId(user_id))

    # ============================================================
    # EMPLOYEE MANAGEMENT METHODS
    # ============================================================

    def get_employees(self) -> List[Dict[str, Any]]:
        """Get all employees."""
        self._check_auth()
        return self._auth.list_employees()

    def get_employees_without_accounts(self) -> List[Dict[str, Any]]:
        """Get employees who don't have user accounts."""
        self._check_auth()
        all_employees = self._auth.list_employees()
        users = self._auth.list_users(include_inactive=True)
        user_employee_ids = {u["employee_id"] for u in users}
        
        return [
            emp for emp in all_employees 
            if emp["_id"] not in user_employee_ids
        ]

    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get an employee by ID."""
        self._check_auth()
        return self._auth.get_employee_by_id(ObjectId(employee_id))

    # ============================================================
    # DASHBOARD AND STATISTICS
    # ============================================================

    def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics."""
        self._check_auth()
        users = self._auth.list_users(include_inactive=True)
        
        stats = {
            "total_users": len(users),
            "active_users": len([u for u in users if u.get("status") == "active"]),
            "inactive_users": len([u for u in users if u.get("status") != "active"]),
            "roles": {},
            "last_login": None,
        }
        
        # Count by role
        for user in users:
            role = user.get("role", "Unknown")
            stats["roles"][role] = stats["roles"].get(role, 0) + 1
        
        # Find last login
        active_users = [u for u in users if u.get("last_login_at")]
        if active_users:
            stats["last_login"] = max(u["last_login_at"] for u in active_users)
        
        return stats