from __future__ import annotations
from datetime import date as Date, datetime, timedelta, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pymongo.errors import DuplicateKeyError
from app.security import employee_reference_values, require_session, serialize_id, today_south_africa
from app.domain import PEOPLE_OVERSIGHT, role, require_roles, refs, own, employee_by_reference, date_string, now, name, as_datetime, change, audit

router = APIRouter(tags=['attendance'])


def _serialize_attendance(record):
    return serialize_id(record)


async def _get_today_record(db, employee_id):
    employee = await employee_by_reference(db, employee_id)
    return await db['attendance'].find_one({'employee_id': {'$in': refs(employee)}, 'work_date': today_south_africa()})


async def attendance_filter(ctx, employee_id=None):
    if employee_id is not None:
        employee = await employee_by_reference(ctx['db'], employee_id)
        if role(ctx) not in PEOPLE_OVERSIGHT and not own(ctx, employee['_id']):
            raise HTTPException(403, 'You can only view your own attendance.')
        return {'employee_id': {'$in': refs(employee)}}
    return {} if role(ctx) in PEOPLE_OVERSIGHT else {'employee_id': {'$in': refs(ctx['employee'])}}


@router.get('/api/attendance/today')
@router.get('/api/admin/attendance/today')
async def attendance_today(date: str | None = None, employee_id: str | None = None, ctx: dict = Depends(require_session)):
    query = await attendance_filter(ctx, employee_id)
    work_date = date_string(date) if date else today_south_africa()
    rows = await ctx['db']['attendance'].find({**query, 'work_date': work_date}).to_list(None)
    records = serialize_id(rows)
    return {'success': True, 'records': records, 'attendance': records[0] if records else None, 'date': work_date}


@router.get('/api/attendance/team')
@router.get('/api/admin/attendance/team')
async def attendance_team(date: str | None = None, ctx: dict = Depends(require_session)):
    require_roles(ctx, PEOPLE_OVERSIGHT)
    return await attendance_today(date, None, ctx)


@router.get('/api/admin/attendance')
@router.get('/api/attendance/records')
async def attendance_by_date(date: str | None = None, employee_id: str | None = None, ctx: dict = Depends(require_session)):
    return await attendance_today(date, employee_id, ctx)


@router.get('/api/attendance/history')
@router.get('/api/admin/attendance/history')
async def attendance_history(days: int = Query(1, ge=1, le=366), employee_id: str | None = None, ctx: dict = Depends(require_session)):
    today = Date.fromisoformat(today_south_africa())
    query = await attendance_filter(ctx, employee_id)
    query['work_date'] = {'$gte': (today - timedelta(days=days-1)).isoformat(), '$lte': today.isoformat()}
    rows = await ctx['db']['attendance'].find(query).sort('work_date', -1).to_list(None)
    return {'success': True, 'records': serialize_id(rows), 'days': days}


@router.get('/api/attendance/working-now')
async def working_now(ctx: dict = Depends(require_session)):
    require_roles(ctx, PEOPLE_OVERSIGHT)
    on_shift = await ctx['db']['attendance'].find({'work_date': today_south_africa(), 'clock_in_at': {'$exists': True, '$ne': None}, 'clock_out_at': None}).to_list(None)
    working = [row for row in on_shift if str(row.get('status') or '').lower() not in {'on_break', 'break'}]
    return {
        'success': True,
        'records': serialize_id(working),
        'count': len(working),
        'on_break_count': len(on_shift) - len(working),
        'on_shift_count': len(on_shift),
    }


async def _attendance_action(ctx, action):
    employee, db = ctx['employee'], ctx['db']
    today = today_south_africa()
    collection = db['attendance']
    record = await collection.find_one({'employee_id': {'$in': refs(employee)}, 'work_date': today})
    current = now()
    if action == 'clock_in':
        if record and record.get('clock_in_at'):
            raise HTTPException(409, 'Attendance already started for this day.')
        doc = {'employee_id': employee['_id'], 'employee_name': name(employee), 'department': employee.get('department'),
            'work_date': today, 'clock_in_at': current, 'clock_out_at': None, 'status': 'clocked_in',
            'break_started_at': None, 'break_seconds': 0, 'break_duration_minutes': 0, 'updated_at': current}
        if record:
            record = await change(collection, record, doc, audit(ctx, action))
        else:
            doc.update(_id=f"{employee['_id']}:{today}", revision=0, created_at=current, history=[audit(ctx, action)])
            try:
                await collection.insert_one(doc)
            except DuplicateKeyError:
                raise HTTPException(409, 'Attendance already started for this day.')
            record = doc
    else:
        if not record or not record.get('clock_in_at') or record.get('clock_out_at'):
            raise HTTPException(409, 'You are not currently clocked in.')
        updates = {}
        started = record.get('break_started_at')
        if action == 'clock_out':
            if started or record.get('status') in {'on_break', 'break'}:
                raise HTTPException(409, 'End the active break before clocking out.')
            updates.update(clock_out_at=current, status='clocked_out')
        elif action == 'break_start':
            if started or record.get('status') in {'on_break', 'break'}:
                raise HTTPException(409, 'Break already started.')
            updates.update(break_started_at=current, break_ended_at=None, status='on_break')
        elif action == 'break_end':
            if not started:
                raise HTTPException(409, 'No active break.')
            updates['status'] = 'clocked_in'
        else:
            raise HTTPException(422, 'Invalid attendance action.')
        if started and action == 'break_end':
            seconds = float(record.get('break_seconds') or float(record.get('break_duration_minutes') or 0)*60) + max(0, (current-as_datetime(started)).total_seconds())
            updates.update(break_started_at=None, break_ended_at=current, break_seconds=seconds, break_duration_minutes=seconds/60)
        if action == 'clock_out':
            break_seconds = float(updates.get('break_seconds', record.get('break_seconds') or float(record.get('break_duration_minutes') or 0) * 60))
            shift_seconds = max(0, (current - as_datetime(record['clock_in_at'])).total_seconds())
            work_seconds = max(0, shift_seconds - break_seconds)
            updates.update(work_seconds=work_seconds, hours_worked=work_seconds / 3600)
        record = await change(collection, record, updates, audit(ctx, action))
    return {'success': True, 'attendance': serialize_id(record)}


@router.post("/api/attendance/clock-in")
async def clock_in(body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    if body.get('employee_id') is not None and not own(ctx, body['employee_id']):
        raise HTTPException(403, 'Attendance actions use your authenticated employee identity.')
    return await _attendance_action(ctx, "clock_in")


@router.post("/api/attendance/clock-out")
async def clock_out(body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    if body.get('employee_id') is not None and not own(ctx, body['employee_id']):
        raise HTTPException(403, 'Attendance actions use your authenticated employee identity.')
    return await _attendance_action(ctx, "clock_out")


@router.post("/api/attendance/break-start", operation_id="attendance_break_start")
@router.post("/api/attendance/break/start")
async def break_start(body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    if body.get('employee_id') is not None and not own(ctx, body['employee_id']):
        raise HTTPException(403, 'Attendance actions use your authenticated employee identity.')
    return await _attendance_action(ctx, "break_start")


@router.post("/api/attendance/break-end", operation_id="attendance_break_end")
@router.post("/api/attendance/break/end")
async def break_end(body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    if body.get('employee_id') is not None and not own(ctx, body['employee_id']):
        raise HTTPException(403, 'Attendance actions use your authenticated employee identity.')
    return await _attendance_action(ctx, "break_end")


@router.get("/api/attendance/status")
async def attendance_status(ctx: dict = Depends(require_session)):
    """Current user's today attendance status (desktop header polls this)."""
    db, employee = ctx["db"], ctx["employee"]
    emp_id = employee.get("_id") or employee.get("employee_id")
    record = await _get_today_record(db, emp_id)
    ser = _serialize_attendance(record)

    # IMPORTANT: no record for today means not_started — never default to clocked_out.
    # The previous fallback made the desktop disable Clock In on a fresh day.
    if not record:
        status = "not_started"
        state = "not_started"
    else:
        raw = str(record.get("status") or "").strip().lower().replace(" ", "_").replace("-", "_")
        has_in = bool(record.get("clock_in_at") or record.get("started_at"))
        has_out = bool(record.get("clock_out_at"))
        # Active break: explicit status, OR break_started_at with no completed end after it
        bs = record.get("break_started_at")
        be = record.get("break_ended_at")
        break_open = False
        if bs and has_in and not has_out:
            if not be:
                break_open = True
            else:
                try:
                    def _ts(v):
                        if isinstance(v, datetime):
                            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
                        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
                    break_open = _ts(bs) > _ts(be)
                except Exception:
                    break_open = raw in ("on_break", "break", "paused")
        on_break = raw in ("on_break", "break", "paused") or break_open

        if has_in and not has_out:
            if on_break:
                status = "on_break"
                state = "on_break"
            else:
                status = "clocked_in"
                state = "working"
        elif has_in and has_out:
            status = "clocked_out"
            state = "completed"
        elif raw in ("clocked_in", "working", "in", "active", "checked_in"):
            status = "clocked_in"
            state = "working"
        elif raw in ("on_break", "break"):
            status = "on_break"
            state = "on_break"
        elif raw in ("clocked_out", "completed", "out", "checked_out", "done"):
            status = "clocked_out"
            state = "completed"
        else:
            status = "not_started"
            state = "not_started"

    return {
        "success": True,
        "status": status,
        "state": state if record else "not_started",
        "attendance": ser,
        "record": ser,
        "clocked_in": bool(record and record.get("clock_in_at") and not record.get("clock_out_at")),
        "on_break": status == "on_break",
    }
