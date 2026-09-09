"""Dashboard data – Backend API only.

Recent Operational Activity = live view of REAL attendance clock-ins for today (SAST).
Source of truth: backend attendance endpoints (MongoDB attendance collection on server).
Never invent employees, times, or clock-in events.
"""

from __future__ import annotations

from datetime import datetime, date, time as dt_time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.services.backend_api_client import BackendAPIClient, BackendAPIError

SAST = ZoneInfo("Africa/Johannesburg")
UTC = ZoneInfo("UTC")
WORK_START = dt_time(9, 0)  # SAST – label only; lateness policy if backend has no status


def _today_sast() -> date:
    return datetime.now(SAST).date()


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse to timezone-aware datetime in SAST. Never invent values."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Treat naive as UTC (common for Mongo/API) then convert to SAST
            return value.replace(tzinfo=UTC).astimezone(SAST)
        return value.astimezone(SAST)
    text = str(value).strip()
    if not text:
        return None
    try:
        text2 = text.replace("Z", "+00:00")
        if "T" in text2 or " " in text2:
            dt = datetime.fromisoformat(text2[:32])
        else:
            dt = datetime.fromisoformat(text2[:10])
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(SAST)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text[:19], fmt).replace(tzinfo=UTC)
                return dt.astimezone(SAST)
            except Exception:
                continue
    return None


def _parse_date(value: Any) -> Optional[date]:
    dt = _parse_datetime(value)
    if dt is not None:
        return dt.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _is_active_employee(emp: dict) -> bool:
    status = str(emp.get("status") or emp.get("employment_status") or "active").strip().lower()
    if status in ("inactive", "terminated", "archived", "disabled", "left", "deleted"):
        return False
    if emp.get("active") is False:
        return False
    return True


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return None


def _priority_is_high(raw: Any) -> bool:
    return str(raw or "").strip().lower() in ("high", "urgent", "critical", "h", "1")


def _status_is_pending(raw: Any) -> bool:
    return str(raw or "").strip().lower() in (
        "pending", "awaiting", "submitted", "in review", "in_review", "open"
    )


def _record_id(row: dict) -> str:
    for k in ("_id", "id", "attendance_id", "record_id"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _employee_key(row: dict) -> str:
    for k in ("employee_id", "user_id", "emp_id"):
        v = row.get(k)
        if v is not None and str(v).strip():
            return str(v).strip().lower()
    name = (
        row.get("employee_name")
        or row.get("full_name")
        or row.get("name")
        or row.get("employee")
        or ""
    )
    return str(name).strip().lower()


def _clock_in_from_row(row: dict) -> Optional[datetime]:
    for k in (
        "clock_in_at", "started_at", "start_time", "check_in_at",
        "clockInAt", "time_in", "checkin_at",
    ):
        dt = _parse_datetime(row.get(k))
        if dt is not None:
            return dt
    nested = row.get("record")
    if isinstance(nested, dict):
        for k in ("clock_in_at", "started_at", "start_time", "check_in_at"):
            dt = _parse_datetime(nested.get(k))
            if dt is not None:
                return dt
    return None


def _work_date_from_row(row: dict, cin: Optional[datetime]) -> Optional[date]:
    for k in ("work_date", "date", "attendance_date"):
        d = _parse_date(row.get(k))
        if d is not None:
            return d
    if cin is not None:
        return cin.date()
    return _parse_date(row.get("created_at"))


class DashboardService:
    def __init__(self, backend: BackendAPIClient) -> None:
        self._backend = backend
        self._last_activity_error: Optional[str] = None

    # ==================================================================
    # Public
    # ==================================================================

    def get_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        errors: List[str] = []

        try:
            primary = self._backend.get_dashboard_summary()
            if isinstance(primary, dict):
                summary.update(primary)
        except BackendAPIError as exc:
            errors.append(str(exc))

        try:
            self._ensure_total_people(summary)
        except Exception as exc:
            errors.append(f"people: {exc}")

        try:
            self._ensure_attendance(summary)
        except Exception as exc:
            errors.append(f"attendance: {exc}")

        # Recent Operational Activity = real clock-ins only
        activity_result = self.get_today_clock_in_activity()
        if activity_result.get("error"):
            summary["activity_error"] = activity_result["error"]
            # Do not wipe a successful empty list with silence — view can show error
            if "recent_activity" not in summary:
                summary["recent_activity"] = []
                summary["latest_activity"] = []
        else:
            activity = activity_result.get("items") or []
            summary["recent_activity"] = activity
            summary["latest_activity"] = activity
            summary["activity"] = activity

        try:
            self._ensure_tasks(summary)
        except Exception as exc:
            errors.append(f"tasks: {exc}")

        try:
            self._ensure_approvals(summary)
        except Exception as exc:
            errors.append(f"approvals: {exc}")

        if errors and not summary:
            summary["error"] = "; ".join(errors)
        elif errors:
            summary.setdefault("_enrichment_warnings", errors)

        return summary

    def get_today_clock_in_activity(self) -> Dict[str, Any]:
        """
        Canonical method: every employee with a real clock_in_at today (SAST).

        Returns:
            {
              "items": [ activity dicts ],
              "error": optional str if backend failed (not the same as zero rows)
            }
        """
        self._last_activity_error = None
        today = _today_sast()
        raw_rows: List[dict] = []
        fetch_errors: List[str] = []
        any_success = False

        # ---- 1) Canonical today endpoint (exists on live API) ----
        # GET /api/attendance/today — when role is admin/manager should return ALL
        # of today's attendance documents from MongoDB, not only the caller.
        try:
            self._backend.clear_cache()  # never serve stale activity
        except Exception:
            pass
        try:
            data = self._backend.attendance_today(today.isoformat())
            any_success = True
            batch: List[dict] = []
            if isinstance(data, list):
                batch = [r for r in data if isinstance(r, dict)]
            elif isinstance(data, dict):
                for key in (
                    "records", "items", "history", "employees", "data",
                    "results", "rows", "attendance",
                ):
                    val = data.get(key)
                    if isinstance(val, list):
                        batch.extend([r for r in val if isinstance(r, dict)])
                if not batch and (data.get("clock_in_at") or data.get("record")):
                    batch.append(data)
            raw_rows.extend(batch)
        except BackendAPIError as exc:
            fetch_errors.append(str(exc))
        except AttributeError:
            # Older client without attendance_today helper
            ok, batch, err = self._fetch_record_list(
                f"/api/attendance/today?date={today.isoformat()}"
            )
            if ok:
                any_success = True
                raw_rows.extend(batch)
            elif err:
                fetch_errors.append(err)

        # ---- 1b) Other team / admin paths as fallback ----
        team_paths = (
            "/api/admin/attendance/today",
            "/api/attendance/team",
            "/api/admin/attendance/team",
            f"/api/admin/attendance?date={today.isoformat()}",
            f"/api/attendance/records?date={today.isoformat()}",
        )
        for path in team_paths:
            ok, batch, err = self._fetch_record_list(path)
            if ok:
                any_success = True
                raw_rows.extend(batch)
            elif err:
                fetch_errors.append(err)

        # ---- 2) History (may be team-scoped for admin) ----
        history_paths = (
            "/api/admin/attendance/history?days=1",
            "/api/attendance/history?days=1",
            "/api/admin/attendance/history?days=2",
            "/api/attendance/history?days=2",
            "/api/attendance/history?days=1&scope=all",
            "/api/attendance/history?days=1&all=1",
        )
        for path in history_paths:
            ok, batch, err = self._fetch_record_list(path)
            if ok:
                any_success = True
                raw_rows.extend(batch)
            elif err:
                fetch_errors.append(err)

        # ---- 3) Lists embedded on dashboard summary ----
        try:
            primary = self._backend.get_dashboard_summary()
            if isinstance(primary, dict):
                for key in (
                    "working_employees",
                    "clocked_in",
                    "clocked_in_employees",
                    "attendance_records",
                    "today_attendance",
                    "team_attendance",
                ):
                    val = primary.get(key)
                    if isinstance(val, list):
                        any_success = True
                        raw_rows.extend([r for r in val if isinstance(r, dict)])
                att = primary.get("attendance")
                if isinstance(att, dict):
                    for key in ("records", "items", "employees", "details"):
                        val = att.get(key)
                        if isinstance(val, list):
                            any_success = True
                            raw_rows.extend([r for r in val if isinstance(r, dict)])
        except BackendAPIError as exc:
            fetch_errors.append(str(exc))

        # ---- 4) Director/manager path: if we have fewer clock-in ROWS than
        # people_working (or almost none), probe EVERY active employee.
        # people_working is only a COUNT — it does not contain names — so we
        # must ask attendance for each person to learn who the count refers to.
        items = self._dedupe_and_filter(raw_rows, today)
        target_working = None
        try:
            primary = self._backend.get_dashboard_summary()
            if isinstance(primary, dict):
                target_working = _as_int(primary.get("people_working"))
                if target_working is None:
                    target_working = _as_int(primary.get("people_on_site"))
        except BackendAPIError:
            pass

        need_full_probe = len(items) < 2 or (
            target_working is not None and len(items) < int(target_working)
        )
        if need_full_probe:
            probed, probe_ok, probe_err = self._probe_employees_today()
            if probe_ok:
                any_success = True
                raw_rows.extend(probed)
                items = self._dedupe_and_filter(raw_rows, today)
            elif probe_err:
                fetch_errors.append(probe_err)

        items.sort(key=lambda a: a.get("created_at") or "", reverse=True)

        if not any_success and fetch_errors and not items:
            msg = fetch_errors[0]
            self._last_activity_error = msg
            return {"items": [], "error": msg}

        return {"items": items, "error": None}

    def get_business_lead_dashboard(self) -> Dict[str, Any]:
        try:
            data = self._backend.request("GET", "/api/dashboard/business-lead")
            if isinstance(data, dict) and data:
                return data
        except BackendAPIError:
            pass
        return self.get_summary()

    def get_director_dashboard(self) -> Dict[str, Any]:
        try:
            data = self._backend.request("GET", "/api/dashboard/director")
            if isinstance(data, dict) and data:
                return data
        except BackendAPIError:
            pass
        return self.get_summary()

    # ==================================================================
    # Attendance activity helpers
    # ==================================================================

    def _fetch_record_list(self, path: str) -> Tuple[bool, List[dict], Optional[str]]:
        try:
            data = self._backend.request("GET", path)
        except BackendAPIError as exc:
            return False, [], str(exc)

        batch: List[dict] = []
        if isinstance(data, list):
            batch = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            for key in (
                "records", "items", "history", "employees", "data",
                "results", "rows", "clockins", "clock_ins", "attendance",
            ):
                val = data.get(key)
                if isinstance(val, list):
                    batch.extend([r for r in val if isinstance(r, dict)])
                elif isinstance(val, dict):
                    for k2 in ("records", "items", "employees", "data"):
                        inner = val.get(k2)
                        if isinstance(inner, list):
                            batch.extend([r for r in inner if isinstance(r, dict)])
            # Single record payload
            if not batch and (data.get("clock_in_at") or data.get("record")):
                batch.append(data)
        return True, batch, None

    def _probe_employees_today(self) -> Tuple[List[dict], bool, Optional[str]]:
        """
        Ask attendance for each active employee (director/manager path).

        people_working is only a number. To show WHO clocked in, we resolve
        each employee via attendance status/history. Only rows with a real
        clock_in_at are kept — we never invent a row for "working" alone.
        """
        try:
            employees = self._backend.get_employees(force=True)
        except BackendAPIError as exc:
            return [], False, str(exc)
        if not isinstance(employees, list):
            return [], True, None

        out: List[dict] = []
        any_ok = False
        last_err: Optional[str] = None
        today = _today_sast().isoformat()

        for emp in employees:
            if not isinstance(emp, dict) or not _is_active_employee(emp):
                continue
            eid = emp.get("id") or emp.get("employee_id") or emp.get("_id")
            name = (emp.get("full_name") or emp.get("name") or emp.get("display_name") or "").strip()
            dept = emp.get("department") or ""
            if eid is None:
                continue

            data = None
            paths = (
                f"/api/admin/attendance/status?employee_id={eid}",
                f"/api/admin/attendance/today?employee_id={eid}",
                f"/api/admin/attendance/{eid}/today",
                f"/api/admin/employees/{eid}/attendance",
                f"/api/attendance/status?employee_id={eid}",
                f"/api/attendance/today?employee_id={eid}",
                f"/api/attendance/status/{eid}",
                f"/api/attendance/history?days=1&employee_id={eid}",
                f"/api/employees/{eid}/attendance?date={today}",
            )
            for path in paths:
                try:
                    data = self._backend.request("GET", path)
                    any_ok = True
                    break
                except BackendAPIError as exc:
                    last_err = str(exc)
                    continue

            if not isinstance(data, dict):
                continue

            # Normalise various payload shapes into one record dict
            candidates = []
            if isinstance(data.get("record"), dict):
                candidates.append(data["record"])
            for key in ("records", "items", "history", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    candidates.extend([r for r in val if isinstance(r, dict)])
            candidates.append(data)

            best = None
            best_cin = None
            for cand in candidates:
                cin = _clock_in_from_row(cand)
                if cin is None:
                    continue
                if best_cin is None or cin < best_cin:
                    best = cand
                    best_cin = cin
            if best is None:
                continue

            merged = dict(best)
            for key in ("clock_in_at", "started_at", "start_time", "check_in_at", "status", "state", "work_date"):
                if data.get(key) is not None and merged.get(key) is None:
                    merged[key] = data[key]
            merged["employee_id"] = eid
            merged["employee_name"] = name or merged.get("employee_name") or merged.get("name") or str(eid)
            merged["full_name"] = merged["employee_name"]
            merged["name"] = merged["employee_name"]
            if dept:
                merged.setdefault("department", dept)
            out.append(merged)

        return out, any_ok, (None if any_ok else last_err)

    def _dedupe_and_filter(self, raw_rows: List[dict], today: date) -> List[dict]:
        """
        Keep only today's records with valid clock_in_at.
        One row per employee/day. Prefer attendance _id, else employee_id + work_date.
        """
        by_key: Dict[str, dict] = {}

        for row in raw_rows:
            if not isinstance(row, dict):
                continue
            # Unwrap nested record if needed
            if isinstance(row.get("record"), dict) and not _clock_in_from_row(row):
                base = dict(row)
                base.update({k: v for k, v in row["record"].items() if v is not None})
                row = base

            cin = _clock_in_from_row(row)
            if cin is None:
                continue
            work_date = _work_date_from_row(row, cin)
            if work_date is not None and work_date != today:
                continue
            if work_date is None and cin.date() != today:
                continue

            rid = _record_id(row)
            emp_key = _employee_key(row)
            dedupe_key = rid if rid else f"{emp_key}|{today.isoformat()}"

            name = (
                row.get("employee_name")
                or row.get("full_name")
                or row.get("name")
                or row.get("employee")
                or emp_key
                or "Unknown employee"
            )
            dept = row.get("department") or "—"
            status = str(row.get("status") or row.get("state") or "").lower()

            # Description: Clocked In; optional Late only from backend status or clock time
            if "late" in status or cin.timetz().replace(tzinfo=None) > WORK_START:
                activity = f"Clocked In · Late · {cin.strftime('%H:%M')}"
                punctuality = "late"
            elif cin.timetz().replace(tzinfo=None) < WORK_START:
                activity = f"Clocked In · Early · {cin.strftime('%H:%M')}"
                punctuality = "early"
            else:
                activity = f"Clocked In · {cin.strftime('%H:%M')}"
                punctuality = "on_time"

            entry = {
                "employee_id": row.get("employee_id") or row.get("user_id") or emp_key,
                "employee": name,
                "employee_name": name,
                "name": name,
                "department": dept,
                "description": activity,
                "action": activity,
                "activity": activity,
                "created_at": cin.isoformat(),
                "timestamp": cin.isoformat(),
                "timestamp_display": cin.strftime("%H:%M"),
                "status": punctuality,
                "work_date": today.isoformat(),
                "_record_id": rid or dedupe_key,
            }

            prev = by_key.get(dedupe_key)
            if prev is None:
                by_key[dedupe_key] = entry
            else:
                # Same employee/day: keep earliest clock-in as the daily clock-in event
                if (entry.get("created_at") or "") < (prev.get("created_at") or ""):
                    by_key[dedupe_key] = entry

        # Also collapse by employee_id if both id-based and name-based keys slipped in
        by_emp: Dict[str, dict] = {}
        for entry in by_key.values():
            ek = str(entry.get("employee_id") or entry.get("name") or "").strip().lower()
            prev = by_emp.get(ek)
            if prev is None:
                by_emp[ek] = entry
            else:
                if (entry.get("created_at") or "") < (prev.get("created_at") or ""):
                    by_emp[ek] = entry

        return list(by_emp.values())

    # ==================================================================
    # People / attendance KPIs (unchanged product rules)
    # ==================================================================

    def _ensure_total_people(self, summary: Dict[str, Any]) -> None:
        if summary.get("total_people") is not None:
            return
        try:
            employees = self._backend.get_employees(force=False)
        except BackendAPIError:
            return
        if not isinstance(employees, list):
            return
        active = [e for e in employees if isinstance(e, dict) and _is_active_employee(e)]
        summary["total_people"] = len(active)

    def _ensure_attendance(self, summary: Dict[str, Any]) -> None:
        """
        present defaults to people_working (product rule).
        late only if backend supplies it.
        absent = total_people - people_working.
        """
        nested = summary.get("attendance") if isinstance(summary.get("attendance"), dict) else {}

        total = _as_int(summary.get("total_people"))
        working = _as_int(summary.get("people_working"))
        if working is None:
            working = _as_int(summary.get("people_on_site"))

        present = _as_int(summary.get("present_count"))
        if present is None:
            present = _as_int(nested.get("present"))

        late = _as_int(summary.get("late_count"))
        if late is None:
            late = _as_int(nested.get("late"))

        if working is not None:
            if late is None:
                late = 0
            present = max(0, working - late)

        if total is not None and working is not None:
            absent = max(0, total - working)
            pct = int(round((working / total) * 100)) if total > 0 else 0
        else:
            absent = _as_int(summary.get("absent_count"))
            pct = _as_int(summary.get("attendance_pct"))

        if working is not None:
            summary["people_working"] = working
        if total is not None:
            summary["total_people"] = total
            summary["attendance_total"] = total
        if present is not None:
            summary["present_count"] = present
        if late is not None:
            summary["late_count"] = late
        if absent is not None:
            summary["absent_count"] = absent
        if pct is not None:
            summary["attendance_pct"] = pct

        summary["attendance"] = {
            "present": summary.get("present_count"),
            "absent": summary.get("absent_count"),
            "late": summary.get("late_count"),
            "total": summary.get("total_people"),
            "percentage": summary.get("attendance_pct"),
        }

    def _ensure_tasks(self, summary: Dict[str, Any]) -> None:
        if summary.get("tasks_due_today") is not None and summary.get("tasks_high_priority") is not None:
            return
        try:
            data = self._backend.get_tasks("all")
        except BackendAPIError:
            return
        items = data.get("tasks") or data.get("items") or data.get("data") or []
        if not isinstance(items, list):
            return
        today = _today_sast()
        due_today = high_due = 0
        for raw in items:
            if not isinstance(raw, dict):
                continue
            due = _parse_date(raw.get("due_date") or raw.get("due") or raw.get("deadline"))
            if due != today:
                continue
            status = str(raw.get("status") or "").strip().lower()
            if status in ("completed", "cancelled", "canceled", "done"):
                continue
            due_today += 1
            if _priority_is_high(raw.get("priority")):
                high_due += 1
        if summary.get("tasks_due_today") is None:
            summary["tasks_due_today"] = due_today
        if summary.get("tasks_high_priority") is None:
            summary["tasks_high_priority"] = high_due
        summary["tasks"] = {
            "due_today": summary.get("tasks_due_today"),
            "high_priority_due_today": summary.get("tasks_high_priority"),
        }

    def _ensure_approvals(self, summary: Dict[str, Any]) -> None:
        if summary.get("pending_approvals") is not None and summary.get("approvals_queue") is not None:
            return
        try:
            data = self._backend.request("GET", "/api/approvals?status=Pending")
        except BackendAPIError:
            try:
                data = self._backend.request("GET", "/api/approvals")
            except BackendAPIError:
                return
        items = data.get("approvals") or data.get("items") or data.get("data") or []
        if isinstance(data, list):
            items = data
        if not isinstance(items, list):
            items = []
        pending = [r for r in items if isinstance(r, dict) and _status_is_pending(r.get("status"))]
        if summary.get("pending_approvals") is None:
            summary["pending_approvals"] = len(pending)
        if summary.get("approvals_queue") is None:
            queue = []
            for raw in pending[:10]:
                queue.append(
                    {
                        "type": raw.get("request_type") or raw.get("type") or raw.get("title") or "Request",
                        "title": raw.get("title") or raw.get("request_type") or "Request",
                        "employee": raw.get("requested_by") or raw.get("requester") or "—",
                        "when": raw.get("submitted_at") or raw.get("created_at") or "",
                        "status": raw.get("status") or "Pending",
                    }
                )
            summary["approvals_queue"] = queue