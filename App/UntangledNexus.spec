# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Untangled Nexus desktop client (Windows, Python 3.12)."""

from pathlib import Path

block_cipher = None
ROOT = Path(SPECPATH)

# Only package runtime assets – never .env secrets
datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / ".env.example"), "."),
]

hiddenimports = [
    "customtkinter",
    "darkdetect",
    "PIL",
    "PIL._tkinter_finder",
    "requests",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    "dotenv",
    "tzdata",
]

a = Analysis(
    ["main.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter.test", "pymongo", "bson"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = ROOT / "assets" / "Branding" / "icon.ico"
if not icon_path.exists():
    icon_path = ROOT / "assets" / "logo.ico"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="UntangledNexus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="UntangledNexus",
)
