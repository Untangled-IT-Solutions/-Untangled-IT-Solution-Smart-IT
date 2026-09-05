"""Version single-source checks."""

from app.__version__ import __version__
from app.utils.config import APP_VERSION


def test_version_is_semver_like():
    parts = __version__.split(".")
    assert len(parts) >= 2


def test_config_matches_version_module():
    assert APP_VERSION == __version__
