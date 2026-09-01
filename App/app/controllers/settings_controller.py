"""Settings controller."""

from app.database.database import Database
from app.models.account import UserAccount
from app.models.role_permission import can_administer_accounts
from app.services.auth_service import AuthService
from app.services.people_service import PeopleService
from app.utils.theme import Theme


class SettingsController:
    """Provides application settings and theme preference actions."""

    def __init__(
        self,
        database: Database,
        auth_service: AuthService,
        people_service: PeopleService,
    ) -> None:
        self._database = database
        self._auth_service = auth_service
        self._people_service = people_service

    def get_theme_mode(self) -> str:
        return Theme.CURRENT_MODE

    def set_theme_mode(self, mode: str) -> str:
        return Theme.apply_mode(mode, persist=True)

    def get_settings(self) -> dict[str, str]:
        return {
            "Company": Theme.COMPANY_LEGAL_NAME,
            "Platform": Theme.COMPANY_NAME,
            "Working Hours": "08:00 - 17:00",
            "Notifications": "Enabled",
            "Application Version": Theme.VERSION,
            "Database Status": "Connected" if self._database.db_path.exists() else "Not initialized",
            "Database Path": str(self._database.db_path),
        }

    def can_administer_accounts(self) -> bool:
        return can_administer_accounts(self._auth_service.current_role)

    def get_accounts(self) -> list[UserAccount]:
        self._auth_service.require_account_admin()
        return self._auth_service.list_accounts()

    def get_employee_options(self) -> list[str]:
        self._auth_service.require_account_admin()
        return [
            f"{employee.id}: {employee.full_name}"
            for employee in self._people_service.get_employees()
            if employee.id is not None
        ]

    def get_role_options(self) -> list[str]:
        return ["Director", "Branch Manager", "Operations Manager", "Staff", "Intern"]

    def create_account(
        self,
        employee_option: str,
        username: str,
        password: str,
        role: str,
        active: bool,
    ) -> UserAccount:
        return self._auth_service.create_account(
            self._parse_employee_id(employee_option),
            username,
            password,
            role,
            active,
        )

    def reset_password(self, account_id: int, password: str) -> None:
        self._auth_service.reset_password(account_id, password)

    def set_account_status(self, account_id: int, active: bool) -> None:
        self._auth_service.set_account_status(account_id, active)

    def change_role(self, account_id: int, role: str) -> None:
        self._auth_service.change_role(account_id, role)

    @staticmethod
    def _parse_employee_id(employee_option: str) -> int:
        try:
            return int(employee_option.split(":", 1)[0])
        except (ValueError, IndexError) as error:
            raise ValueError("Select a valid employee.") from error
