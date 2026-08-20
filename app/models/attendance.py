"""Attendance domain model."""

from dataclasses import dataclass


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
    def is_clocked_in(self) -> bool:
        return bool(self.clock_in_at) and not bool(self.clock_out_at)

    @property
    def is_on_break(self) -> bool:
        return self.is_clocked_in and bool(self.break_started_at)
