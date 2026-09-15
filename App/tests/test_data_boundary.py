"""Architecture guard for the desktop/server data boundary."""

import ast
from pathlib import Path


APP_ROOT = Path("app")


def test_desktop_has_no_database_driver_imports():
    forbidden_roots = {"bson", "motor", "pymongo", "sqlite3"}
    findings = []
    for path in APP_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".", 1)[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".", 1)[0]}
            else:
                continue
            blocked = names & forbidden_roots
            if blocked:
                findings.append(f"{path}:{node.lineno}: {sorted(blocked)}")
    assert findings == []


def test_desktop_has_no_direct_database_calls_or_credentials():
    forbidden = ("MongoClient(", "AsyncIOMotorClient(", ".get_collection(", "MONGODB_URI", "MONGO_URI")
    findings = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                findings.append(f"{path}: {token}")
    assert findings == []


def test_retired_work_view_is_only_a_compatibility_layer():
    text = (APP_ROOT / "views" / "work_view.py").read_text(encoding="utf-8")
    assert "get_collection" not in text
    assert "BackendAPIClient" not in text
    assert "WorkView = TaskView" in text

