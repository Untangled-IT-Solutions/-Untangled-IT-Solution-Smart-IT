from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAD_RUNTIME_FILE = re.compile(r"(^|/)\.env$|\.(?:log|db)$", re.IGNORECASE)
MONGODB_CREDENTIAL = re.compile(
    r"mongodb\+srv://(?P<user>[^\s:/@]+):(?P<password>[^\s@]+)@",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT = re.compile(
    r"(?:mongodb_uri|jwt_secret|secret_key|api_key|metrics_token)\s*[:=]\s*"
    r"[\"'](?P<value>[^\"']{8,})[\"']",
    re.IGNORECASE,
)
PLACEHOLDERS = {
    "change-me",
    "changeme",
    "example",
    "password",
    "secret",
    "user",
    "username",
    "your-password",
    "your-secret",
}


def tracked_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=ROOT
    ).decode("utf-8", errors="replace")
    return [path for path in output.split("\0") if path]


def is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        normalized in PLACEHOLDERS
        or "..." in normalized
        or "${" in normalized
        or "<" in normalized
        or normalized.startswith("test-")
    )


def main() -> int:
    findings: list[str] = []
    for relative in tracked_files():
        normalized = relative.replace("\\", "/")
        if BAD_RUNTIME_FILE.search(normalized):
            findings.append(f"{relative}: tracked runtime or environment file")
            continue
        if "/tests/" in f"/{normalized}" or normalized.endswith((".md", ".example")):
            continue
        path = ROOT / relative
        try:
            if path.stat().st_size > 5_000_000:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            uri = MONGODB_CREDENTIAL.search(line)
            if uri and not (
                is_placeholder(uri.group("user"))
                or is_placeholder(uri.group("password"))
            ):
                findings.append(f"{relative}:{line_number}: embedded MongoDB credential")
            assignment = SECRET_ASSIGNMENT.search(line)
            if assignment and not is_placeholder(assignment.group("value")):
                findings.append(f"{relative}:{line_number}: embedded secret assignment")
    if findings:
        print("Potential secrets detected:")
        print("\n".join(findings))
        return 1
    print("Repository secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
