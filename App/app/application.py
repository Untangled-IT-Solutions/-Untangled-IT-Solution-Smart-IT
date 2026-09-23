"""Application bootstrap – production, Backend/MongoDB only."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import customtkinter as ctk

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles often default to cp1252 while the existing diagnostic output
# contains Unicode symbols. A logging/print statement must never prevent startup.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

from app.utils.config import APP_VERSION, COMPANY_NAME, LOG_DIR
from app.utils.theme import Theme
from app.services.backend_api_client import BackendAPIClient
from app.services.backend_auth_service import BackendAuthService
from app.services.auth_service import AuthService
from app.services.people_service import PeopleService
from app.services.dashboard_service import DashboardService
from app.services.attendance_service import AttendanceService
from app.services.work_service import WorkService
from app.controllers.app_controller import AppController

# Configure logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "untangled.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("untangled")


class Application:
    """Composition root – pure Backend API architecture."""

    def __init__(self) -> None:
        self._init_ui()

        logger.info("=" * 60)
        logger.info("%s v%s – starting", COMPANY_NAME, APP_VERSION)
        logger.info("=" * 60)

        # Single network client
        self.backend = BackendAPIClient()
        print(f"🌐 Connected to backend: {self.backend.base_url}")
        logger.info("Backend client ready → %s", self.backend.base_url)

        # Connectivity checks must not delay creation of the login window.
        from app.utils.async_tasks import run_in_background
        run_in_background(self._temp_root, self.backend.health,
                          lambda health: logger.info("Backend health check completed"),
                          lambda exc: logger.warning("Backend not reachable yet: %s", exc),
                          name="startup-health")

        # Auth stack
        self.mongo_auth = BackendAuthService(self.backend)
        self.auth_service = AuthService(self.mongo_auth)

        # Domain services (all API-backed)
        self.people_service = PeopleService(self.backend)
        self.dashboard_service = DashboardService(self.backend)
        self.attendance_service = AttendanceService(self.backend)
        self.work_service = WorkService(self.backend)

        # Controllers & UI orchestration
        self.controller = AppController(
            auth_service=self.auth_service,
            mongo_auth_service=self.mongo_auth,
            people_service=self.people_service,
            dashboard_service=self.dashboard_service,
            attendance_service=self.attendance_service,
            work_service=self.work_service,
            backend=self.backend,
        )

        logger.info("Application composition complete")

    def _init_ui(self) -> None:
        """Prepare CustomTkinter environment (hidden root)."""
        self._temp_root = ctk.CTk()
        self._temp_root.withdraw()
        Theme.apply_mode()
        ctk.set_default_color_theme("dark-blue")

    def run(self) -> None:
        """Start the application (login → main window)."""
        try:
            self.controller.start()
        except Exception:
            logger.exception("Fatal error while starting application")
            raise
        finally:
            try:
                self._temp_root.destroy()
            except Exception:
                pass


def main() -> None:
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
