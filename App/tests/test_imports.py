"""Critical module import gate (services/models without GUI deps)."""

import importlib
import pytest


def test_import_core_services():
    import app.services.backend_api_client  # noqa: F401
    import app.services.backend_auth_service  # noqa: F401
    import app.services.auth_service  # noqa: F401
    import app.services.work_service  # noqa: F401
    import app.services.attendance_service  # noqa: F401


def test_import_gui_modules_if_available():
    pytest.importorskip("customtkinter")
    import app.controllers.app_controller  # noqa: F401
    import app.controllers.navigation_controller  # noqa: F401
    import app.views.login_view  # noqa: F401
    import app.views.task_view  # noqa: F401


def test_main_module_path_exists():
    from pathlib import Path
    assert Path("main.py").is_file()
