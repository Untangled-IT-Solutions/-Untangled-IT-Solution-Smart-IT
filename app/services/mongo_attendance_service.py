# app/services/mongo_attendance_service.py
"""Attendance service with timer using MongoDB."""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.services.mongodb_service import MongoDBService
from app.models.mongo_models import AttendanceStatus


class MongoAttendanceService:
    """Attendance service with real-time tracking."""
    
    def __init__(self, mongodb: MongoDBService):
        self._mongo = mongodb
        self._active_timers: Dict[ObjectId, datetime] = {}
    
    def _get_today_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def clock_in(self, employee_id: ObjectId, employee_name: str) -> Dict[str, Any]:
        """Clock in an employee."""
        attendance = self._mongo.get_collection("attendance")
        today = self._get_today_str()
        now = datetime.now(timezone.utc)
        
        # Check if already clocked in
        existing = attendance.find_one({
            "employee_id": employee_id,
            "work_date": today,
        })
        
        if existing and existing.get("clock_in_at") and not existing.get("clock_out_at"):
            raise ValueError("Employee is already clocked in.")
        
        record = {
            "employee_id": employee_id,
            "employee_name": employee_name,
            "work_date": today,
            "clock_in_at": now,
            "clock_out_at": None,
            "break_started_at": None,
            "lunch_started_at": None,
            "break_duration_minutes": 0,
            "lunch_duration_minutes": 0,
            "hours_worked": 0,
            "status": AttendanceStatus.CLOCKED_IN.value,
            "created_at": now,
        }
        
        if existing:
            attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": record}
            )
            result = attendance.find_one({"_id": existing["_id"]})
        else:
            result = attendance.insert_one(record)
            result = attendance.find_one({"_id": result.inserted_id})
        
        self._active_timers[employee_id] = now
        return result
    
    def clock_out(self, employee_id: ObjectId) -> Dict[str, Any]:
        """Clock out an employee."""
        attendance = self._mongo.get_collection("attendance")
        today = self._get_today_str()
        now = datetime.now(timezone.utc)
        
        record = attendance.find_one({
            "employee_id": employee_id,
            "work_date": today,
        })
        
        if not record:
            raise ValueError("No attendance record found for today.")
        
        if not record.get("clock_in_at"):
            raise ValueError("Employee hasn't clocked in.")
        
        if record.get("clock_out_at"):
            raise ValueError("Employee already clocked out.")
        
        # Calculate hours worked
        clock_in = record["clock_in_at"]
        total_seconds = (now - clock_in).total_seconds()
        hours = total_seconds / 3600
        
        # Subtract break and lunch time
        break_minutes = record.get("break_duration_minutes", 0)
        lunch_minutes = record.get("lunch_duration_minutes", 0)
        total_break_hours = (break_minutes + lunch_minutes) / 60
        hours = max(0, hours - total_break_hours)
        
        attendance.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "clock_out_at": now,
                    "hours_worked": round(hours, 2),
                    "status": AttendanceStatus.CLOCKED_OUT.value,
                    "updated_at": now,
                }
            }
        )
        
        if employee_id in self._active_timers:
            del self._active_timers[employee_id]
        
        return attendance.find_one({"_id": record["_id"]})
    
    def start_break(self, employee_id: ObjectId) -> Dict[str, Any]:
        """Start a break."""
        attendance = self._mongo.get_collection("attendance")
        today = self._get_today_str()
        now = datetime.now(timezone.utc)
        
        record = attendance.find_one({
            "employee_id": employee_id,
            "work_date": today,
        })
        
        if not record:
            raise ValueError("No attendance record found.")
        
        if record.get("status") != AttendanceStatus.CLOCKED_IN.value:
            raise ValueError("Must be clocked in to take a break.")
        
        if record.get("break_started_at"):
            raise ValueError("Already on break.")
        
        attendance.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "break_started_at": now,
                    "status": AttendanceStatus.ON_BREAK.value,
                    "updated_at": now,
                }
            }
        )
        
        return attendance.find_one({"_id": record["_id"]})
    
    def end_break(self, employee_id: ObjectId) -> Dict[str, Any]:
        """End a break."""
        attendance = self._mongo.get_collection("attendance")
        today = self._get_today_str()
        now = datetime.now(timezone.utc)
        
        record = attendance.find_one({
            "employee_id": employee_id,
            "work_date": today,
        })
        
        if not record:
            raise ValueError("No attendance record found.")
        
        if not record.get("break_started_at"):
            raise ValueError("Not on break.")
        
        break_start = record["break_started_at"]
        duration = int((now - break_start).total_seconds() / 60)
        
        attendance.update_one(
            {"_id": record["_id"]},
            {
                "$set": {
                    "break_started_at": None,
                    "break_duration_minutes": record.get("break_duration_minutes", 0) + duration,
                    "status": AttendanceStatus.CLOCKED_IN.value,
                    "updated_at": now,
                }
            }
        )
        
        return attendance.find_one({"_id": record["_id"]})
    
    def get_today_record(self, employee_id: ObjectId) -> Optional[Dict[str, Any]]:
        """Get today's attendance record."""
        attendance = self._mongo.get_collection("attendance")
        return attendance.find_one({
            "employee_id": employee_id,
            "work_date": self._get_today_str(),
        })
    
    def get_timer_status(self, employee_id: ObjectId) -> Dict[str, Any]:
        """Get current timer status."""
        record = self.get_today_record(employee_id)
        if not record:
            return {"status": "not_started"}
        
        status = record.get("status", "clocked_out")
        result = {"status": status}
        
        if status == AttendanceStatus.CLOCKED_IN.value and record.get("clock_in_at"):
            elapsed = (datetime.now(timezone.utc) - record["clock_in_at"]).total_seconds()
            result["elapsed_seconds"] = int(elapsed)
            result["elapsed_hours"] = round(elapsed / 3600, 2)
        
        if status == AttendanceStatus.ON_BREAK.value and record.get("break_started_at"):
            elapsed = (datetime.now(timezone.utc) - record["break_started_at"]).total_seconds()
            result["break_elapsed_minutes"] = int(elapsed / 60)
        
        return result