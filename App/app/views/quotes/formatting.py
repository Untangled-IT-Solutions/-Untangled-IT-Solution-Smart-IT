"""Pure formatting helpers for quote UI (no Tk, no network)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.views.quotes.constants import (
    STATUS_COLORS,
    STATUS_ICONS,
    STATUS_OPTIONS,
    MONGO_TO_DISPLAY,
    DISPLAY_TO_MONGO,
)


def map_mongo_to_display(mongo_status: Any) -> str:
    if mongo_status is None:
        return "Pending"
    key = str(mongo_status).strip()
    return MONGO_TO_DISPLAY.get(key, MONGO_TO_DISPLAY.get(key.lower(), key or "Pending"))


def map_display_to_mongo(display: str) -> str:
    return DISPLAY_TO_MONGO.get(display, display)


def format_date(value: Any, long: bool = False) -> str:
    if value is None or value == "":
        return "—"
    text = str(value).strip()
    try:
        cleaned = text.replace("Z", "+00:00")
        if "T" in cleaned:
            dt = datetime.fromisoformat(cleaned)
        else:
            return text[:16]
        if long:
            return dt.strftime("%d %b %Y, %H:%M")
        return dt.strftime("%d %b %Y")
    except Exception:
        return text[:19].replace("T", " ")


def format_rand(value: Any) -> str:
    try:
        return f"R {float(value):,.2f}"
    except Exception:
        return "R 0.00"


def darken_color(hex_color: str, amount: int = 40) -> str:
    try:
        h = hex_color.lstrip("#")
        r = max(0, int(h[0:2], 16) - amount)
        g = max(0, int(h[2:4], 16) - amount)
        b = max(0, int(h[4:6], 16) - amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, "#9E9E9E")


def status_icon(status: str) -> str:
    return STATUS_ICONS.get(status, "•")


def quotation_lines(quote: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines = quote.get("quotation_lines") or quote.get("line_items") or quote.get("items") or []
    if isinstance(lines, list):
        return [x for x in lines if isinstance(x, dict)]
    return []


def quotation_total(quote: Dict[str, Any]) -> float:
    total = quote.get("quotation_total") or quote.get("total") or quote.get("amount")
    if total is not None:
        try:
            return float(total)
        except Exception:
            pass
    s = 0.0
    for line in quotation_lines(quote):
        try:
            s += float(line.get("total") or line.get("amount") or 0)
        except Exception:
            continue
    return s


def missing_client_fields(quote: Dict[str, Any]) -> List[str]:
    required = [
        ("client_name", "Client name"),
        ("client_email", "Client email"),
        ("client_phone", "Client phone"),
    ]
    missing = []
    for key, label in required:
        val = quote.get(key) or quote.get(key.replace("client_", ""))
        if not val:
            missing.append(label)
    return missing


def is_assigned_to_user(quote: Dict[str, Any], username: str) -> bool:
    if not username:
        return False
    u = username.strip().lower()
    assigned = quote.get("assigned_to") or {}
    fields = []
    if isinstance(assigned, dict):
        fields = [
            assigned.get("username"),
            assigned.get("email"),
            assigned.get("full_name"),
            assigned.get("display_name"),
            assigned.get("name"),
            assigned.get("employee_id"),
            assigned.get("id"),
        ]
    else:
        fields = [assigned]
    fields += [quote.get("assigned_username"), quote.get("assignee")]
    return any(str(f or "").strip().lower() == u for f in fields)
