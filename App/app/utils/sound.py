# app/utils/sound.py
"""Notification sound utilities with repeating reminder until notifications are read.

Windows-first: uses winsound with the bundled WAV (most reliable).
Falls back to playsound / system sounds on other platforms.
"""
from __future__ import annotations

import os
import platform
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional


def _candidate_sound_paths() -> List[Path]:
    """Return possible locations for notification.wav / .mp3 / .ogg."""
    bases: List[Path] = []

    # 1. PyInstaller frozen path (most important for installed app)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        bases.extend([
            meipass / "app" / "assets",
            meipass / "assets",
            meipass / "app" / "assets" / "sounds",
            meipass / "assets" / "sounds",
        ])

    # 2. Development / normal paths
    here = Path(__file__).resolve()
    bases.extend([
        here.parent.parent / "assets",                 # app/assets
        here.parent.parent.parent / "assets",          # project/assets
        Path.cwd() / "app" / "assets",
        Path.cwd() / "assets",
        Path.cwd() / "app" / "assets" / "sounds",
        Path.cwd() / "assets" / "sounds",
    ])

    # 3. Next to the executable (Inno Setup install location)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        bases.extend([
            exe_dir / "app" / "assets",
            exe_dir / "assets",
            exe_dir / "_internal" / "app" / "assets",
            exe_dir / "_internal" / "assets",
        ])

    names = ["notification.wav", "notification.mp3", "notification.ogg"]
    paths: List[Path] = []
    for base in bases:
        for name in names:
            paths.append(base / name)
    return paths


def _find_sound_file() -> Optional[Path]:
    for p in _candidate_sound_paths():
        if p.is_file():
            return p
    return None


class SoundManager:
    """Manages notification sounds across platforms.

    - One-shot play for newly arrived notifications
    - Repeating reminder until stop_reminder() (while unread remain)
    """
    _instance = None
    _enabled = True
    _reminder_active = False
    _reminder_thread: Optional[threading.Thread] = None
    _reminder_interval_seconds = 18
    _lock = threading.Lock()
    _last_play_at = 0.0  # throttle rapid repeats

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def set_enabled(cls, enabled: bool):
        cls._enabled = bool(enabled)
        if not cls._enabled:
            cls.stop_reminder()
        print(f"🔊 SoundManager enabled={cls._enabled}")

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @classmethod
    def play_notification_sound(cls, blocking: bool = False):
        """Play a single notification sound (non-blocking by default)."""
        if not cls._enabled:
            print("🔇 Sound skipped (disabled)")
            return

        # Throttle: don't stack more than once per 1.5s from parallel calls
        now = time.time()
        if now - cls._last_play_at < 1.5:
            return
        cls._last_play_at = now

        def _play():
            try:
                sound_file = _find_sound_file()
                system = platform.system()
                print(f"🔊 Playing notification sound (OS={system}, file={sound_file})")

                # ---------- Windows (most reliable path first) ----------
                if system == "Windows":
                    try:
                        import winsound
                        if sound_file and sound_file.suffix.lower() == ".wav":
                            winsound.PlaySound(
                                str(sound_file),
                                winsound.SND_FILENAME | winsound.SND_ASYNC,
                            )
                            print(f"✅ winsound played: {sound_file}")
                            return
                        # System alias
                        winsound.PlaySound(
                            "SystemAsterisk",
                            winsound.SND_ALIAS | winsound.SND_ASYNC,
                        )
                        print("✅ winsound SystemAsterisk")
                        return
                    except Exception as e:
                        print(f"⚠️ winsound failed: {e}")
                        try:
                            import winsound
                            winsound.MessageBeep(winsound.MB_ICONASTERISK)
                            print("✅ winsound MessageBeep")
                            return
                        except Exception as e2:
                            print(f"⚠️ MessageBeep failed: {e2}")

                # ---------- playsound (cross-platform) ----------
                if sound_file:
                    try:
                        from playsound import playsound
                        playsound(str(sound_file), block=False)
                        print(f"✅ playsound played: {sound_file}")
                        return
                    except ImportError:
                        print("ℹ️ playsound not installed (pip install playsound)")
                    except Exception as e:
                        print(f"⚠️ playsound failed: {e}")

                # ---------- macOS ----------
                if system == "Darwin":
                    try:
                        import subprocess
                        target = str(sound_file) if sound_file else "/System/Library/Sounds/Glass.aiff"
                        subprocess.run(
                            ["afplay", target],
                            capture_output=True,
                            check=False,
                        )
                        print(f"✅ afplay: {target}")
                        return
                    except Exception as e:
                        print(f"⚠️ afplay failed: {e}")

                # ---------- Linux ----------
                if system == "Linux":
                    try:
                        import subprocess
                        if sound_file:
                            for cmd in (["paplay", str(sound_file)], ["aplay", str(sound_file)]):
                                try:
                                    r = subprocess.run(cmd, capture_output=True, check=False)
                                    if r.returncode == 0:
                                        print(f"✅ {' '.join(cmd)}")
                                        return
                                except FileNotFoundError:
                                    continue
                        for f in (
                            "/usr/share/sounds/freedesktop/stereo/complete.oga",
                            "/usr/share/sounds/freedesktop/stereo/message.oga",
                        ):
                            if os.path.exists(f):
                                subprocess.run(["paplay", f], capture_output=True, check=False)
                                print(f"✅ paplay system: {f}")
                                return
                    except Exception as e:
                        print(f"⚠️ Linux sound failed: {e}")

                # Last resort: terminal bell
                print("\a", end="", flush=True)
                print("🔔 Fell back to terminal bell")
            except Exception as e:
                print(f"⚠️ Sound play error: {e}")
                import traceback
                traceback.print_exc()

        if blocking:
            _play()
        else:
            threading.Thread(target=_play, daemon=True, name="PlayNotifSound").start()

    @classmethod
    def start_reminder(cls, interval_seconds: Optional[int] = None):
        """Repeat the notification sound until stop_reminder()."""
        if not cls._enabled:
            return
        with cls._lock:
            if cls._reminder_active:
                return
            cls._reminder_active = True
            if interval_seconds is not None and interval_seconds > 5:
                cls._reminder_interval_seconds = int(interval_seconds)

        def _loop():
            while True:
                slept = 0
                interval = cls._reminder_interval_seconds
                while slept < interval:
                    with cls._lock:
                        if not cls._reminder_active or not cls._enabled:
                            return
                    time.sleep(1)
                    slept += 1
                with cls._lock:
                    if not cls._reminder_active or not cls._enabled:
                        return
                try:
                    print("🔔 Reminder beep (unread notifications still present)")
                    cls.play_notification_sound(blocking=False)
                except Exception:
                    pass

        t = threading.Thread(target=_loop, daemon=True, name="NotificationReminder")
        with cls._lock:
            cls._reminder_thread = t
        t.start()
        print("🔔 Notification reminder sound started (plays until notifications are read)")

    @classmethod
    def stop_reminder(cls):
        with cls._lock:
            was_active = cls._reminder_active
            cls._reminder_active = False
        if was_active:
            print("🔕 Notification reminder sound stopped")

    @classmethod
    def is_reminder_active(cls) -> bool:
        with cls._lock:
            return cls._reminder_active

    @classmethod
    def debug_paths(cls):
        """Print where the sound file is expected."""
        print("🔊 Sound file search paths:")
        found = None
        for p in _candidate_sound_paths():
            exists = p.is_file()
            print(f"   {'✅' if exists else '❌'} {p}")
            if exists and found is None:
                found = p
        print(f"→ Using: {found}")