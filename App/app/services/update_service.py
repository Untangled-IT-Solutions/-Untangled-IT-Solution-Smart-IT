"""Automatic update checks and installer download for Untangled Nexus.

Talks only to the public GitHub Releases API. Never blocks the UI thread
and never crashes the application when the network is unavailable.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from app.__version__ import __version__

logger = logging.getLogger("untangled.update")

# ---------------------------------------------------------------------------
# GitHub repository that publishes Untangled-Nexus-Setup-X.Y.Z.exe
# Adjust these if the desktop release repository differs from the API repo.
# ---------------------------------------------------------------------------
GITHUB_OWNER = "Siyanda-UntangledItS"
GITHUB_REPOSITORY = "untangled-nexus"

REQUEST_TIMEOUT_SECONDS = 15
DOWNLOAD_TIMEOUT_SECONDS = 120
INSTALLER_NAME_PATTERN = re.compile(
    r"^Untangled-Nexus-Setup-(\d+\.\d+\.\d+)\.exe$", re.IGNORECASE
)
CHECKSUM_SUFFIX = ".sha256"

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True)
class UpdateInfo:
    """Structured information about an available release."""

    version: str
    tag_name: str
    download_url: str
    checksum_url: Optional[str]
    release_url: str


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a semantic version string into a comparable tuple.

    Accepts ``1.0.0``, ``v1.0.0``, and optional pre-release/build suffixes
    (suffixes are ignored for ordering).
    """
    cleaned = (version or "").strip()
    if cleaned.lower().startswith("v"):
        cleaned = cleaned[1:]
    match = _SEMVER_RE.match(cleaned)
    if not match:
        raise ValueError(f"Invalid semantic version: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_newer_version(current: str, candidate: str) -> bool:
    """Return True if *candidate* is strictly newer than *current*."""
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        return False


def _find_asset(assets: list, name_predicate) -> Optional[dict]:
    for asset in assets or []:
        name = asset.get("name") or ""
        if name_predicate(name):
            return asset
    return None


class UpdateService:
    """Check GitHub Releases and download the official installer."""

    def __init__(
        self,
        owner: str = GITHUB_OWNER,
        repository: str = GITHUB_REPOSITORY,
        current_version: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.owner = owner
        self.repository = repository
        self.current_version = (current_version or __version__).lstrip("v")
        self._session = session or requests.Session()
        self._session.headers.setdefault(
            "Accept", "application/vnd.github+json"
        )
        self._session.headers.setdefault(
            "User-Agent", f"UntangledNexus/{self.current_version}"
        )
        self._download_lock = threading.Lock()
        self._downloading = False

    @property
    def is_downloading(self) -> bool:
        return self._downloading

    def check_for_update(self) -> Optional[UpdateInfo]:
        """Query the latest GitHub release.

        Returns :class:`UpdateInfo` when a newer non-draft, non-prerelease
        version is available; otherwise ``None``. Network errors are logged
        and return ``None`` so startup is never blocked.
        """
        url = (
            f"https://api.github.com/repos/{self.owner}/{self.repository}/releases/latest"
        )
        try:
            response = self._session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            if response.status_code == 404:
                logger.info(
                    "No GitHub releases found for %s/%s",
                    self.owner,
                    self.repository,
                )
                return None
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.warning("Update check failed (network): %s", exc)
            return None
        except (ValueError, TypeError) as exc:
            logger.warning("Update check failed (parse): %s", exc)
            return None

        if data.get("draft") or data.get("prerelease"):
            logger.info("Latest release is draft/prerelease – skipping")
            return None

        tag_name = str(data.get("tag_name") or "")
        remote_version = tag_name.lstrip("v")
        if not remote_version:
            return None

        if not is_newer_version(self.current_version, remote_version):
            logger.info(
                "No update (current=%s, latest=%s)",
                self.current_version,
                remote_version,
            )
            return None

        assets = data.get("assets") or []
        installer_name = f"Untangled-Nexus-Setup-{remote_version}.exe"
        installer = _find_asset(
            assets, lambda n: n.lower() == installer_name.lower()
        )
        if installer is None:
            installer = _find_asset(
                assets, lambda n: bool(INSTALLER_NAME_PATTERN.match(n))
            )
        if installer is None:
            logger.warning("Release %s has no installer asset", tag_name)
            return None

        download_url = installer.get("browser_download_url")
        if not download_url:
            logger.warning("Installer asset missing download URL")
            return None

        checksum_name = f"{installer.get('name') or installer_name}{CHECKSUM_SUFFIX}"
        checksum_asset = _find_asset(
            assets, lambda n: n.lower() == checksum_name.lower()
        )
        checksum_url = (
            checksum_asset.get("browser_download_url") if checksum_asset else None
        )

        return UpdateInfo(
            version=remote_version,
            tag_name=tag_name,
            download_url=download_url,
            checksum_url=checksum_url,
            release_url=str(data.get("html_url") or ""),
        )

    def download_installer(
        self,
        update: UpdateInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        destination_dir: Optional[Path] = None,
    ) -> Path:
        """Download the installer to a temp directory and verify SHA256.

        Raises on failure. Call from a background thread only.
        """
        if not self._download_lock.acquire(blocking=False):
            raise RuntimeError("An update download is already in progress.")
        self._downloading = True
        try:
            return self._download_and_verify(update, progress_callback, destination_dir)
        finally:
            self._downloading = False
            self._download_lock.release()

    def _download_and_verify(
        self,
        update: UpdateInfo,
        progress_callback: Optional[Callable[[int, int], None]],
        destination_dir: Optional[Path],
    ) -> Path:
        dest_root = Path(destination_dir or tempfile.gettempdir()) / "UntangledNexusUpdates"
        dest_root.mkdir(parents=True, exist_ok=True)
        installer_name = f"Untangled-Nexus-Setup-{update.version}.exe"
        target = dest_root / installer_name

        if (
            "github.com" not in update.download_url
            and "githubusercontent.com" not in update.download_url
        ):
            raise ValueError("Refusing to download installer from untrusted host.")

        logger.info("Downloading update %s → %s", update.version, target)
        try:
            with self._session.get(
                update.download_url,
                stream=True,
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                hasher = hashlib.sha256()
                with open(target, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        fh.write(chunk)
                        hasher.update(chunk)
                        received += len(chunk)
                        if progress_callback:
                            try:
                                progress_callback(received, total)
                            except Exception:
                                pass
        except requests.RequestException as exc:
            if target.exists():
                try:
                    target.unlink()
                except OSError:
                    pass
            raise RuntimeError(f"Download failed: {exc}") from exc

        if target.stat().st_size < 1024:
            target.unlink(missing_ok=True)
            raise RuntimeError("Downloaded installer is suspiciously small.")

        expected_hash = self._fetch_expected_checksum(update)
        if expected_hash:
            actual = hasher.hexdigest().lower()
            if actual != expected_hash.lower():
                target.unlink(missing_ok=True)
                raise RuntimeError(
                    "Update verification failed. "
                    "The downloaded installer may be corrupted."
                )
            logger.info("SHA256 verified for %s", installer_name)
        else:
            logger.warning(
                "No checksum published for %s – skipping verification",
                installer_name,
            )

        return target

    def _fetch_expected_checksum(self, update: UpdateInfo) -> Optional[str]:
        if not update.checksum_url:
            return None
        try:
            response = self._session.get(
                update.checksum_url, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            text = response.text.strip()
            first_token = text.split()[0] if text else ""
            if re.fullmatch(r"[0-9a-fA-F]{64}", first_token):
                return first_token.lower()
            logger.warning("Checksum file format not recognized")
            return None
        except requests.RequestException as exc:
            logger.warning("Could not download checksum: %s", exc)
            return None

    def launch_updater(self, installer_path: Path) -> None:
        """Start updater.exe with the installer path and current PID, then exit Nexus."""
        installer_path = Path(installer_path).resolve()
        if not installer_path.is_file():
            raise FileNotFoundError(f"Installer not found: {installer_path}")

        updater = self._locate_updater()
        if updater is None:
            raise FileNotFoundError(
                "updater.exe was not found next to UntangledNexus.exe. "
                "Reinstall Nexus from the official installer."
            )

        pid = os.getpid()
        creationflags = 0
        if sys.platform == "win32":
            creationflags = 0x00000008 | 0x00000200  # DETACHED | NEW_GROUP

        logger.info("Launching updater: %s %s %s", updater, installer_path, pid)
        subprocess.Popen(
            [str(updater), str(installer_path), str(pid)],
            cwd=str(updater.parent),
            creationflags=creationflags,
            close_fds=True,
        )

    def _locate_updater(self) -> Optional[Path]:
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "updater.exe")
        project_root = Path(__file__).resolve().parents[2]
        candidates.append(project_root / "dist" / "UntangledNexus" / "updater.exe")
        candidates.append(project_root / "dist" / "updater.exe")
        candidates.append(project_root / "updater.exe")
        for path in candidates:
            if path.is_file():
                return path
        return None

    def install_update(self, installer_path: Path) -> None:
        """Public entry used by the UI: start updater and request app shutdown."""
        self.launch_updater(installer_path)
