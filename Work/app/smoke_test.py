from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.database import Database
from app.services.notification_service import NotificationService
from app.services.attendance_service import AttendanceService
from app.services.calendar_service import CalendarService


def run():
    db = Database()
    db.initialize()
    notif = NotificationService(db)
    att = AttendanceService(db, notif)
    cal = CalendarService(db, notif)

    with db.connection() as conn:
        row = conn.execute("SELECT id, full_name FROM employees LIMIT 1;").fetchone()
        if not row:
            print("No employees found")
            return
        eid = row["id"]
        name = row["full_name"]
        # Clean up any existing attendance record for today so the smoke test runs deterministically
        conn.execute("DELETE FROM attendance_records WHERE employee_id = ? AND work_date = ?;", (eid, date.today().isoformat()))
        # Remove any prior smoke event created earlier to avoid duplicates
        conn.execute("DELETE FROM calendar_events WHERE title = ?;", ("Smoke Event",))

    print("Using employee:", eid, name)

    try:
        rec = att.get_today_record(eid)
        print("Today record before:", rec)
    except Exception as e:
        print("Error get_today_record:", e)

    try:
        r = att.clock_in(eid)
        print("Clocked in:", r)
    except Exception as e:
        print("Clock in error:", e)

    try:
        r2 = att.start_break(eid)
        print("Started break:", r2)
    except Exception as e:
        print("Start break error:", e)

    try:
        r3 = att.end_break(eid)
        print("Ended break:", r3)
    except Exception as e:
        print("End break error:", e)

    try:
        r4 = att.clock_out(eid)
        print("Clocked out:", r4)
    except Exception as e:
        print("Clock out error:", e)

    # Calendar
    try:
        ev = cal.create_event("Smoke Event", "Meeting", date.today().isoformat(), "", "General", "Smoke test", "None")
        print("Created event:", ev)
    except Exception as e:
        print("Create event error:", e)

    try:
        month = cal.get_month_events(date.today().year, date.today().month)
        print("Month events count:", len(month))
    except Exception as e:
        print("Get month events error:", e)


if __name__ == '__main__':
    run()
