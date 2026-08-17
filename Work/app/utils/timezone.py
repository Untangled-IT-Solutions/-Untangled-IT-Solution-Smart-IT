"""Datetime helpers for consistent UTC storage and local display."""

from datetime import datetime, timezone

TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def now_utc() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_timestamp(value: datetime) -> str:
    """Format an aware datetime as a UTC timestamp string."""
    return value.astimezone(timezone.utc).strftime(TIME_FORMAT)


def parse_timestamp(value: str) -> datetime:
    """Parse a stored UTC timestamp string into an aware UTC datetime."""
    return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=timezone.utc)


def utc_to_local(value: str) -> str:
    """Convert a stored UTC timestamp string to the local timezone for display."""
    if not value:
        return ""
    return parse_timestamp(value).astimezone().strftime(TIME_FORMAT)


def local_to_utc(value: str) -> str:
    """Convert a local timestamp string to UTC storage format."""
    if not value:
        return ""
    local_tz = datetime.now().astimezone().tzinfo
    local_dt = datetime.strptime(value, TIME_FORMAT).replace(tzinfo=local_tz)
    return local_dt.astimezone(timezone.utc).strftime(TIME_FORMAT)
