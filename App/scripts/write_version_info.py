"""Generate PyInstaller Windows version metadata from app.__version__."""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.__version__ import __version__


def main() -> Path:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", __version__)
    if not match:
        raise SystemExit(f"Release version must use X.Y.Z: {__version__!r}")
    major, minor, patch = (int(part) for part in match.groups())
    root = Path(__file__).resolve().parents[1]
    target = root / "build_metadata" / "version_info.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({major}, {minor}, {patch}, 0), prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'Untangled IT Solutions'),
    StringStruct('FileDescription', 'Untangled Nexus Desktop'),
    StringStruct('FileVersion', '{__version__}.0'),
    StringStruct('InternalName', 'UntangledNexus'),
    StringStruct('OriginalFilename', 'UntangledNexus.exe'),
    StringStruct('ProductName', 'Untangled Nexus'),
    StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)\n""",
        encoding="utf-8",
    )
    print(target)
    return target


if __name__ == "__main__":
    main()
