"""Version single-source checks."""

from app.__version__ import __version__
from app.utils.config import APP_VERSION
from scripts.write_version_info import main as write_version_info


def test_version_is_semver_like():
    parts = __version__.split(".")
    assert len(parts) >= 2


def test_config_matches_version_module():
    assert APP_VERSION == __version__


def test_windows_version_metadata_uses_application_version():
    target = write_version_info()
    text = target.read_text(encoding="utf-8")
    assert f"StringStruct('ProductVersion', '{__version__}')" in text
    assert f"StringStruct('FileVersion', '{__version__}.0')" in text
