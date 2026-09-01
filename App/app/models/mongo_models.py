# app/models/mongo_models.py
"""MongoDB models for new authentication system."""

from datetime import datetime, timezone
from typing import Optional, List
from dataclasses import dataclass, field
from bson import ObjectId
from enum import Enum


class AttendanceStatus(str, Enum):
    CLOCKED_IN = "clocked_in"
    ON_BREAK = "on_break"
    ON_LUNCH = "on_lunch"
    CLOCKED_OUT = "clocked_out"


class ActivityType(str, Enum):
    WORK = "work"
    BREAK = "break"
    LUNCH = "lunch"
    TRAINING = "training"
    MEETING = "meeting"


@dataclass
class MongoUser:
    _id: Optional[ObjectId] = None
    employee_id: Optional[ObjectId] = None
    username: str = ""
    email: str = ""
    password_hash: str = ""
    role: str = "Staff"
    status: str = "active"
    full_name: str = ""
    department: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "employee_id": self.employee_id,
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "role": self.role,
            "status": self.status,
            "full_name": self.full_name,
            "department": self.department,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_login_at": self.last_login_at,
        }


@dataclass
class MongoAttendanceRecord:
    _id: Optional[ObjectId] = None
    employee_id: ObjectId = None
    employee_name: str = ""
    work_date: str = ""
    clock_in_at: Optional[datetime] = None
    clock_out_at: Optional[datetime] = None
    break_started_at: Optional[datetime] = None
    lunch_started_at: Optional[datetime] = None
    break_duration_minutes: int = 0
    lunch_duration_minutes: int = 0
    hours_worked: float = 0.0
    status: str = AttendanceStatus.CLOCKED_OUT.value
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


@dataclass
class MongoDailyActivity:
    _id: Optional[ObjectId] = None
    employee_id: ObjectId = None
    employee_name: str = ""
    date: str = ""
    activities: List[dict] = field(default_factory=list)
    total_hours: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None