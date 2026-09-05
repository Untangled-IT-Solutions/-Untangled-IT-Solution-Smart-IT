"""Application bootstrap – production, Backend/MongoDB only."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import customtkinter as ctk

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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

        # Quick connectivity check (does not block login if backend is cold)
        try:
            health = self.backend.health()
            print(f"✅ Backend health: {health.get('status') or health.get('ok') or 'ok'}")
        except Exception as exc:
            print(f"⚠️  Backend not reachable yet: {exc}")
            print("   Login will still be attempted. If using Render free tier, the first request may take 30–60s (cold start).")


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
