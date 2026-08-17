# app/services/mongo_auth_service.py
"""Complete authentication service using MongoDB with full user management."""

import hashlib
import hmac
import secrets
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.services.mongodb_service import MongoDBService
from app.utils.config import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_HASH_ITERATIONS,
    PASSWORD_HASH_ALGORITHM,
    PASSWORD_RESET_TOKEN_EXPIRY,
    SESSION_EXPIRY_HOURS,
)


class MongoAuthService:
    """Complete authentication service with MongoDB."""

    ROLES = {
        "Director": {
            "modules": ["Dashboard", "People", "Work", "Attendance", "Calendar", 
                       "Approvals", "Office Requests", "Reports", "Settings"],
            "permissions": ["full_access", "manage_users", "manage_attendance", "approve_requests"]
        },
        "Branch Manager": {
            "modules": ["Dashboard", "People", "Approvals", "Work", "Attendance", 
                       "Calendar", "Projects", "Reports", "Settings"],
            "permissions": ["manage_users", "manage_attendance", "approve_requests"]
        },
        "Business Lead": {
            "modules": ["Dashboard", "Approvals", "Work", "Projects", "Reports", "Settings"],
            "permissions": ["approve_requests", "view_reports"]
        },
        "Operations Manager": {
            "modules": ["Dashboard", "People", "Attendance", "Work", "Calendar", 
                       "Approvals", "Office Requests", "Projects", "Settings"],
            "permissions": ["manage_attendance", "assign_work", "manage_staff"]
        },
        "Staff": {
            "modules": ["Dashboard", "Work", "Attendance", "Calendar", "Office Requests", 
                       "Notifications", "Settings"],
            "permissions": ["view_own_work", "clock_in_out"]
        },
        "Intern": {
            "modules": ["Dashboard", "Work", "Attendance", "Calendar", "Office Requests", 
                       "Notifications", "Settings"],
            "permissions": ["view_own_work", "clock_in_out"]
        },
    }

    def __init__(self, mongodb: MongoDBService):
        self._mongo = mongodb
        self._current_user: Optional[Dict[str, Any]] = None
        self._current_session: Optional[Dict[str, Any]] = None

    # ============================================================
    # PASSWORD MANAGEMENT
    # ============================================================

    @classmethod
    def hash_password(cls, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PASSWORD_HASH_ITERATIONS,
        ).hex()
        return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${digest}"

    @classmethod
    def verify_password(cls, password: str, stored_hash: str) -> bool:
        try:
            algorithm, iterations, salt, digest = stored_hash.split("$", 3)
        except ValueError:
            return False
        if algorithm != PASSWORD_HASH_ALGORITHM:
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        ).hex()
        return hmac.compare_digest(candidate, digest)

    @classmethod
    def generate_secure_password(cls, length: int = 16) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @classmethod
    def validate_password_strength(cls, password: str) -> Tuple[bool, str]:
        if len(password) < PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter."
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter."
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number."
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character."
        return True, "Password is strong."

    # ============================================================
    # USER AUTHENTICATION
    # ============================================================

    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate a user and create a session."""
        username = username.strip().lower()
        if not username or not password:
            raise ValueError("Username and password are required.")

        users_collection = self._mongo.get_collection("users")
        user = users_collection.find_one({"username": username})

        if user is None:
            raise ValueError("Invalid username or password.")
        
        if not self.verify_password(password, user["password_hash"]):
            raise ValueError("Invalid username or password.")

        if user.get("status") != "active":
            raise ValueError("Account is inactive. Contact an administrator.")

        # Update last login
        users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login_at": datetime.now(timezone.utc)}}
        )

        # Create session
        session_token = self._mongo.get_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRY_HOURS)

        session_doc = {
            "user_id": user["_id"],
            "employee_id": user["employee_id"],
            "token": session_token,
            "login_at": datetime.now(timezone.utc),
            "last_activity_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
        }

        sessions_collection = self._mongo.get_collection("auth_sessions")
        result = sessions_collection.insert_one(session_doc)
        session_doc["_id"] = result.inserted_id

        self._current_user = user
        self._current_session = session_doc

        # Get employee info
        employee = self.get_employee_by_id(user["employee_id"])

        return {
            "user": user,
            "employee": employee,
            "session": session_doc,
            "token": session_token,
        }

    def logout(self) -> None:
        if self._current_session:
            sessions_collection = self._mongo.get_collection("auth_sessions")
            sessions_collection.update_one(
                {"_id": self._current_session["_id"]},
                {"$set": {"logout_at": datetime.now(timezone.utc)}}
            )
        self._current_user = None
        self._current_session = None

    def require_authenticated(self) -> Dict[str, Any]:
        if self._current_user is None:
            raise PermissionError("Login is required.")
        return self._current_user

    @property
    def current_user(self) -> Optional[Dict[str, Any]]:
        return self._current_user

    @property
    def current_role(self) -> str:
        return self._current_user.get("role", "Anonymous") if self._current_user else "Anonymous"

    # ============================================================
    # USER MANAGEMENT
    # ============================================================

    def create_user(
        self,
        employee_id: ObjectId,
        username: str,
        password: str,
        role: str = "Staff",
        active: bool = True,
        require_password_change: bool = False,
    ) -> Dict[str, Any]:
        """Create a new user account."""
        is_valid, message = self.validate_password_strength(password)
        if not is_valid:
            raise ValueError(message)

        username = username.strip().lower()
        if not re.match(r"^[a-z0-9._]+$", username):
            raise ValueError("Username can only contain letters, numbers, dots, and underscores.")

        employee = self.get_employee_by_id(employee_id)
        if employee is None:
            raise ValueError("Employee not found.")

        users_collection = self._mongo.get_collection("users")
        existing = users_collection.find_one({
            "$or": [
                {"username": username},
                {"employee_id": employee_id}
            ]
        })
        if existing:
            if existing.get("username") == username:
                raise ValueError(f"Username '{username}' is already taken.")
            raise ValueError("This employee already has an account.")

        user_doc = {
            "employee_id": employee_id,
            "username": username,
            "email": employee.get("email", f"{username}@untangled.local"),
            "password_hash": self.hash_password(password),
            "role": role,
            "status": "active" if active else "inactive",
            "full_name": employee.get("full_name", ""),
            "department": employee.get("department", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "last_login_at": None,
            "require_password_change": require_password_change,
        }

        try:
            result = users_collection.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            print(f"✅ User created: {username} with role {role}")
            return user_doc
        except DuplicateKeyError as e:
            raise ValueError(f"Failed to create user: {e}")

    def create_user_with_generated_password(
        self,
        employee_id: ObjectId,
        username: str,
        role: str = "Staff",
        active: bool = True,
    ) -> Tuple[Dict[str, Any], str]:
        password = self.generate_secure_password()
        user = self.create_user(employee_id, username, password, role, active, require_password_change=True)
        return user, password

    def update_user(
        self,
        user_id: ObjectId,
        username: Optional[str] = None,
        role: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        users_collection = self._mongo.get_collection("users")
        update_data = {"updated_at": datetime.now(timezone.utc)}

        if username is not None:
            username = username.strip().lower()
            if not re.match(r"^[a-z0-9._]+$", username):
                raise ValueError("Username can only contain letters, numbers, dots, and underscores.")
            existing = users_collection.find_one({"username": username, "_id": {"$ne": user_id}})
            if existing:
                raise ValueError(f"Username '{username}' is already taken.")
            update_data["username"] = username

        if role is not None:
            if role not in self.ROLES:
                raise ValueError(f"Invalid role: {role}")
            update_data["role"] = role

        if active is not None:
            update_data["status"] = "active" if active else "inactive"

        result = users_collection.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        if result.matched_count == 0:
            raise ValueError("User not found.")
        return users_collection.find_one({"_id": user_id})

    def reset_password(self, user_id: ObjectId, new_password: str) -> None:
        is_valid, message = self.validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(message)

        users_collection = self._mongo.get_collection("users")
        result = users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "password_hash": self.hash_password(new_password),
                    "updated_at": datetime.now(timezone.utc),
                    "require_password_change": False,
                }
            }
        )
        if result.matched_count == 0:
            raise ValueError("User not found.")

    def delete_user(self, user_id: ObjectId) -> None:
        users_collection = self._mongo.get_collection("users")
        result = users_collection.delete_one({"_id": user_id})
        if result.deleted_count == 0:
            raise ValueError("User not found.")

    # ============================================================
    # USER QUERIES
    # ============================================================

    def get_user_by_id(self, user_id: ObjectId) -> Optional[Dict[str, Any]]:
        users_collection = self._mongo.get_collection("users")
        return users_collection.find_one({"_id": user_id})

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        users_collection = self._mongo.get_collection("users")
        return users_collection.find_one({"username": username.strip().lower()})

    def get_user_by_employee_id(self, employee_id: ObjectId) -> Optional[Dict[str, Any]]:
        users_collection = self._mongo.get_collection("users")
        return users_collection.find_one({"employee_id": employee_id})

    def list_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List all users with optional filtering."""
        users_collection = self._mongo.get_collection("users")
        query = {}
        if not include_inactive:
            query["status"] = "active"
        return list(users_collection.find(query).sort("created_at", -1))

    def get_users_by_role(self, role: str) -> List[Dict[str, Any]]:
        users_collection = self._mongo.get_collection("users")
        return list(users_collection.find({"role": role, "status": "active"}))

    # ============================================================
    # EMPLOYEE MANAGEMENT
    # ============================================================

    def get_employee_by_id(self, employee_id: ObjectId) -> Optional[Dict[str, Any]]:
        employees_collection = self._mongo.get_collection("employees")
        return employees_collection.find_one({"_id": employee_id})

    def get_employee_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        employees_collection = self._mongo.get_collection("employees")
        return employees_collection.find_one({"email": email})

    def list_employees(
        self,
        search: str = "",
        department: str = "All",
        status: str = "All",
    ) -> List[Dict[str, Any]]:
        employees_collection = self._mongo.get_collection("employees")
        query = {}
        if search:
            query["$or"] = [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"position": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
            ]
        if department != "All":
            query["department"] = department
        if status != "All":
            query["status"] = status
        return list(employees_collection.find(query).sort("full_name", 1))

    # ============================================================
    # ROLE AND PERMISSION HELPERS
    # ============================================================

    def get_role_modules(self, role: str) -> List[str]:
        role_info = self.ROLES.get(role, self.ROLES["Staff"])
        return role_info.get("modules", [])

    def get_role_permissions(self, role: str) -> List[str]:
        role_info = self.ROLES.get(role, self.ROLES["Staff"])
        return role_info.get("permissions", [])

    def can_access_module(self, role: str, module: str) -> bool:
        modules = self.get_role_modules(role)
        return module in modules

    def has_permission(self, role: str, permission: str) -> bool:
        permissions = self.get_role_permissions(role)
        return permission in permissions

    def get_all_roles(self) -> List[str]:
        return list(self.ROLES.keys())