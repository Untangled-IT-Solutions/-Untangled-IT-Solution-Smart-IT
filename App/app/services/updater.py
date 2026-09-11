"""Standalone updater process for Untangled Nexus.

Compiled to updater.exe and shipped next to UntangledNexus.exe.

Usage:
    updater.exe "C:\\path\\to\\Untangled-Nexus-Setup-1.0.1.exe" <nexus-pid>

Responsibilities:
  1. Wait for the main Nexus process to exit (do not kill unless timed out).
  2. Launch the Inno Setup installer.
  3. Exit.

This process must remain independent of the main Nexus process so Windows
can replace files that the running executable was using.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

WAIT_TIMEOUT_SECONDS = 90
POLL_INTERVAL_SECONDS = 0.5


def _pid_is_running(pid: int) -> bool:
    """Return True if a process with the given PID still exists."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, wintypes.DWORD(pid)
            )
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            try:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return str(pid) in (result.stdout or "")
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def wait_for_process(pid: int, timeout: float = WAIT_TIMEOUT_SECONDS) -> bool:
    """Wait until *pid* exits. Returns True if it exited, False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_is_running(pid):
            time.sleep(1.0)
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return not _pid_is_running(pid)


def run_installer(installer_path: Path) -> int:
    """Launch the Inno Setup installer and return its exit code."""
    installer_path = installer_path.resolve()
    if not installer_path.is_file():
        print(f"ERROR: Installer not found: {installer_path}", file=sys.stderr)
        return 1

    args = [
        str(installer_path),
        "/SILENT",
        "/NORESTART",
        "/CLOSEAPPLICATIONS",
        "/RESTARTAPPLICATIONS",
    ]
    try:
        completed = subprocess.run(args, check=False)
        return int(completed.returncode or 0)
    except OSError as exc:
        print(f"ERROR: Failed to launch installer: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if len(argv) < 2:
        print(
            "Usage: updater.exe <path-to-installer.exe> <nexus-process-id>",
            file=sys.stderr,
        )
        return 2

    installer = Path(argv[0])
    try:
        pid = int(argv[1])
    except ValueError:
        print(f"ERROR: Invalid PID: {argv[1]!r}", file=sys.stderr)
        return 2

    if not installer.is_file():
        print(f"ERROR: Installer not found: {installer}", file=sys.stderr)
        return 1

    exited = wait_for_process(pid, timeout=WAIT_TIMEOUT_SECONDS)
    if not exited:
        print(
            f"WARNING: Nexus process {pid} did not exit within "
            f"{WAIT_TIMEOUT_SECONDS}s – proceeding carefully.",
            file=sys.stderr,
        )

    return run_installer(installer)


if __name__ == "__main__":
    sys.exit(main())
