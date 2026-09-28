from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLAN = re.compile(r"^\s*plan:\s*([^\s#]+)", re.IGNORECASE | re.MULTILINE)


def main() -> int:
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "*render*.yaml", "*render*.yml"], cwd=ROOT
    ).decode("utf-8", errors="replace")
    findings: list[str] = []
    for relative in (item for item in output.split("\0") if item):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for match in PLAN.finditer(text):
            if match.group(1).lower() != "free":
                findings.append(f"{relative}: billable Render plan '{match.group(1)}'")
    if findings:
        print("Billing policy violation:")
        print("\n".join(findings))
        return 1
    print("No billable Render plans detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
