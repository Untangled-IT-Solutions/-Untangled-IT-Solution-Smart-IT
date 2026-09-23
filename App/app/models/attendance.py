"""Attendance domain model."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class AttendanceRecord:
    """Represents one employee's attendance for a work day."""

    id: int | None
    employee_id: int
    employee_name: str
    work_date: str
    clock_in_at: str
    clock_out_at: str
    break_started_at: str
    break_duration_minutes: int
    hours_worked: float
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def punctuality_status(self) -> str:
        """Classify clock-in against the 08:00-09:00 attendance window."""
        if not self.clock_in_at:
            return "absent"
        try:
            clocked = datetime.fromisoformat(str(self.clock_in_at).replace("Z", "+00:00"))
            if clocked.tzinfo is None:
                clocked = clocked.replace(tzinfo=ZoneInfo("UTC"))
            local = clocked.astimezone(ZoneInfo("Africa/Johannesburg"))
            if local.time() < datetime.strptime("08:00:00", "%H:%M:%S").time():
                return "early"
            if local.time() <= datetime.strptime("09:00:00", "%H:%M:%S").time():
                return "on_time"
            return "late"
        except (ValueError, TypeError):
            return "unknown"

    @property
    def punctuality_emoji(self) -> str:
        return {"early": "🟡", "on_time": "🟢", "late": "🔴", "absent": "⚫", "unknown": "⚪"}.get(
            self.punctuality_status, "⚪"
        )

    @property
    def is_clocked_in(self) -> bool:
        return bool(self.clock_in_at) and not bool(self.clock_out_at)

    @property
    def is_on_break(self) -> bool:
        return self.is_clocked_in and bool(self.break_started_at)
