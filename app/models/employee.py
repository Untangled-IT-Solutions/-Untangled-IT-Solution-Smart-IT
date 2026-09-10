"""Employee model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Employee:
    """Represents an Untangled IT Solutions employee."""

    id: int | str | None
    employee_number: str
    first_name: str
    last_name: str
    full_name: str
    position: str
    department: str
    role: str
    reports_to: str
    mentor: str
    email: str
    phone: str
    status: str
    employment_type: str
    date_joined: str
    clocked_in: bool
    current_task: str
    profile_photo: str
    skills: str
    permissions: str
    performance_score: float
    training_progress: float
    notes: str
    username: str = ""
    team: str = ""
    slack_handle: str = ""
    timezone: str = "Africa/Johannesburg (SAST)"
    presence: str = "offline"
