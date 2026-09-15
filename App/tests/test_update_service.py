"""Unit tests for the automatic update system (no live GitHub calls)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock
import sys

import pytest

from app.services.update_service import (
    UpdateInfo,
    UpdateService,
    is_newer_version,
    parse_version,
)
from app.services import updater as updater_mod
from app.__version__ import __version__


def test_parse_version_basic():
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v1.0.1") == (1, 0, 1)
    assert parse_version("1.0.10") == (1, 0, 10)


def test_parse_version_rejects_garbage():
    with pytest.raises(ValueError):
        parse_version("not-a-version")


def test_is_newer_version_true():
    assert is_newer_version("1.0.0", "1.0.1") is True
    assert is_newer_version("1.0.9", "1.0.10") is True
    assert is_newer_version("1.0.0", "1.1.0") is True
    assert is_newer_version("1.9.9", "2.0.0") is True


def test_is_newer_version_false_equal_or_older():
    assert is_newer_version("1.0.1", "1.0.1") is False
    assert is_newer_version("1.1.0", "1.0.9") is False
    assert is_newer_version("2.0.0", "1.9.9") is False


def test_current_version_detection():
    service = UpdateService(current_version="1.0.0")
    assert service.current_version == "1.0.0"
    assert __version__


def _release_payload(version: str, assets: list | None = None, **extra):
    installer = f"Untangled-Nexus-Setup-{version}.exe"
    default_assets = [
        {
            "name": installer,
            "browser_download_url": f"https://github.com/example/releases/download/v{version}/{installer}",
        },
        {
            "name": f"{installer}.sha256",
            "browser_download_url": f"https://github.com/example/releases/download/v{version}/{installer}.sha256",
        },
    ]
    data = {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": False,
        "html_url": f"https://github.com/example/releases/tag/v{version}",
        "assets": assets if assets is not None else default_assets,
    }
    data.update(extra)
    return data


def test_new_version_detected():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _release_payload("1.0.1")
    response.raise_for_status = MagicMock()
    session.get.return_value = response

    service = UpdateService(current_version="1.0.0", session=session)
    info = service.check_for_update()
    assert info is not None
    assert info.version == "1.0.1"
    assert info.download_url.endswith("Untangled-Nexus-Setup-1.0.1.exe")
    assert info.checksum_url.endswith(".sha256")


def test_equal_version_returns_none():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _release_payload("1.0.0")
    response.raise_for_status = MagicMock()
    session.get.return_value = response

    service = UpdateService(current_version="1.0.0", session=session)
    assert service.check_for_update() is None


def test_older_remote_returns_none():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _release_payload("0.9.0")
    response.raise_for_status = MagicMock()
    session.get.return_value = response

    service = UpdateService(current_version="1.0.0", session=session)
    assert service.check_for_update() is None


def test_github_unavailable_returns_none():
    import requests

    session = MagicMock()
    session.get.side_effect = requests.ConnectionError("offline")
    service = UpdateService(current_version="1.0.0", session=session)
    assert service.check_for_update() is None


def test_missing_installer_asset_returns_none():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = _release_payload("1.0.1", assets=[])
    response.raise_for_status = MagicMock()
    session.get.return_value = response

    service = UpdateService(current_version="1.0.0", session=session)
    assert service.check_for_update() is None


def test_release_without_checksum_is_rejected():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    installer = "Untangled-Nexus-Setup-1.0.1.exe"
    response.json.return_value = _release_payload("1.0.1", assets=[{
        "name": installer,
        "browser_download_url": f"https://github.com/example/releases/{installer}",
    }])
    session.get.return_value = response
    assert UpdateService(current_version="1.0.0", session=session).check_for_update() is None


def test_wrong_version_installer_asset_is_rejected():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = _release_payload("1.0.2", assets=_release_payload("1.0.1")["assets"])
    session.get.return_value = response
    assert UpdateService(current_version="1.0.0", session=session).check_for_update() is None


def test_untrusted_lookalike_download_host_is_rejected(tmp_path: Path):
    update = UpdateInfo("1.0.1", "v1.0.1", "https://evil.test/?github.com", "https://github.com/hash", "")
    with pytest.raises(ValueError, match="untrusted host"):
        UpdateService(current_version="1.0.0").download_installer(update, destination_dir=tmp_path)


def test_draft_and_prerelease_ignored():
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock()
    response.json.return_value = _release_payload("1.0.1", draft=True)
    session.get.return_value = response
    service = UpdateService(current_version="1.0.0", session=session)
    assert service.check_for_update() is None

    response.json.return_value = _release_payload("1.0.1", prerelease=True)
    assert service.check_for_update() is None


def test_sha256_validation_success(tmp_path: Path):
    content = b"fake-installer-bytes-for-test" * 50
    expected = hashlib.sha256(content).hexdigest()

    update = UpdateInfo(
        version="1.0.1",
        tag_name="v1.0.1",
        download_url="https://github.com/example/releases/download/v1.0.1/Untangled-Nexus-Setup-1.0.1.exe",
        checksum_url="https://github.com/example/releases/download/v1.0.1/Untangled-Nexus-Setup-1.0.1.exe.sha256",
        release_url="https://github.com/example/releases/tag/v1.0.1",
    )

    session = MagicMock()
    download_resp = MagicMock()
    download_resp.raise_for_status = MagicMock()
    download_resp.headers = {"Content-Length": str(len(content))}
    download_resp.iter_content = lambda chunk_size: [content]
    download_resp.__enter__ = lambda s: download_resp
    download_resp.__exit__ = MagicMock(return_value=False)

    checksum_resp = MagicMock()
    checksum_resp.raise_for_status = MagicMock()
    checksum_resp.text = f"{expected}  Untangled-Nexus-Setup-1.0.1.exe"

    def get_side_effect(url, **kwargs):
        if url.endswith(".sha256"):
            return checksum_resp
        return download_resp

    session.get.side_effect = get_side_effect
    service = UpdateService(current_version="1.0.0", session=session)
    path = service.download_installer(update, destination_dir=tmp_path)
    assert path.is_file()
    assert path.read_bytes() == content


def test_invalid_checksum_rejects(tmp_path: Path):
    content = b"fake-installer-bytes-for-test" * 50

    update = UpdateInfo(
        version="1.0.1",
        tag_name="v1.0.1",
        download_url="https://github.com/example/releases/download/v1.0.1/Untangled-Nexus-Setup-1.0.1.exe",
        checksum_url="https://github.com/example/releases/download/v1.0.1/Untangled-Nexus-Setup-1.0.1.exe.sha256",
        release_url="https://github.com/example/releases/tag/v1.0.1",
    )

    session = MagicMock()
    download_resp = MagicMock()
    download_resp.raise_for_status = MagicMock()
    download_resp.headers = {"Content-Length": str(len(content))}
    download_resp.iter_content = lambda chunk_size: [content]
    download_resp.__enter__ = lambda s: download_resp
    download_resp.__exit__ = MagicMock(return_value=False)

    checksum_resp = MagicMock()
    checksum_resp.raise_for_status = MagicMock()
    checksum_resp.text = "0" * 64 + "  Untangled-Nexus-Setup-1.0.1.exe"

    def get_side_effect(url, **kwargs):
        if url.endswith(".sha256"):
            return checksum_resp
        return download_resp

    session.get.side_effect = get_side_effect
    service = UpdateService(current_version="1.0.0", session=session)
    with pytest.raises(RuntimeError, match="verification failed"):
        service.download_installer(update, destination_dir=tmp_path)


def test_updater_main_requires_args():
    assert updater_mod.main([]) == 2
    assert updater_mod.main(["only-one-arg"]) == 2


def test_updater_main_invalid_pid(tmp_path: Path):
    installer = tmp_path / "setup.exe"
    installer.write_bytes(b"x" * 100)
    assert updater_mod.main([str(installer), "not-a-pid"]) == 2


def test_updater_main_missing_installer():
    assert updater_mod.main(["/nonexistent/setup.exe", "1"]) == 1


def test_wait_for_process_already_gone():
    assert updater_mod.wait_for_process(0, timeout=1) is True


def test_updater_restarts_after_successful_install(tmp_path: Path, monkeypatch):
    installer = tmp_path / "setup.exe"
    executable = tmp_path / "UntangledNexus.exe"
    installer.write_bytes(b"installer")
    executable.write_bytes(b"application")
    restarted = []
    monkeypatch.setattr(updater_mod, "wait_for_process", lambda *args, **kwargs: True)
    monkeypatch.setattr(updater_mod, "run_installer", lambda path: 0)
    monkeypatch.setattr(updater_mod, "restart_nexus", lambda path: restarted.append(path) or True)
    assert updater_mod.main([str(installer), "123", str(executable)]) == 0
    assert restarted == [executable]


def test_launch_updater_uses_temporary_copy_and_passes_restart_path(tmp_path: Path, monkeypatch):
    install_dir = tmp_path / "installed"
    install_dir.mkdir()
    updater = install_dir / "updater.exe"
    nexus = install_dir / "UntangledNexus.exe"
    installer = tmp_path / "Untangled-Nexus-Setup-1.0.1.exe"
    updater.write_bytes(b"updater")
    nexus.write_bytes(b"nexus")
    installer.write_bytes(b"installer")
    launched = {}
    service = UpdateService(current_version="1.0.0")
    monkeypatch.setattr(service, "_locate_updater", lambda: updater)
    monkeypatch.setattr("app.services.update_service.tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr("app.services.update_service.subprocess.Popen", lambda args, **kwargs: launched.update(args=args, kwargs=kwargs))
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    service.launch_updater(installer)
    staged = Path(launched["args"][0])
    assert staged.parent == tmp_path / "UntangledNexusUpdates"
    assert staged.read_bytes() == b"updater"
    assert launched["args"][3] == str(nexus.resolve())
