"""Mongo ObjectId–safe task id helpers (never assume int ids)."""

from __future__ import annotations

from typing import Any


def task_id_key(task_id: Any) -> str:
    """Normalize Mongo ObjectId / int / str for comparison and API calls."""
    if task_id is None:
        return ""
    return str(task_id).strip()


def format_ticket(task_id: Any) -> str:
    """Display ticket label; supports integer and ObjectId strings."""
    if task_id is None or task_id == "":
        return "NEW"
    s = str(task_id).strip()
    if s.isdigit():
        return f"#{int(s):04d}"
    return f"#{s[-6:]}" if len(s) > 6 else f"#{s}"


# Aliases used by views
_task_id_key = task_id_key
_format_ticket = format_ticket
