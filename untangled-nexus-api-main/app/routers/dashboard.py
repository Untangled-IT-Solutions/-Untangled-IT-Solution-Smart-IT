from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.security import require_session, today_south_africa, serialize_id

router = APIRouter(tags=["dashboard"])

_cache: dict[str, Any] = {"at": 0.0, "payload": None}


def _as_date(value: Any) -> Optional[datetime]:
    """Parse to timezone-aware UTC. Naive values are treated as UTC (Mongo / isoformat)."""
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _format_sast_hm(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Africa/Johannesburg")).strftime("%H:%M")


def _is_late(clock_in: datetime, status: str = "") -> bool:
    """Late if clock-in after 09:00 Africa/Johannesburg on that calendar day."""
    sast = clock_in.astimezone(ZoneInfo("Africa/Johannesburg"))
    work_start = sast.replace(hour=9, minute=0, second=0, microsecond=0)
    return sast > work_start or "late" in (status or "").lower()


def _activity_from_attendance(record: dict, meta: Optional[dict]) -> Optional[dict]:
    cin = _as_date(record.get("clock_in_at"))
    if not cin:
        return None
    hh_in = _format_sast_hm(cin)
    status_raw = str(record.get("status") or "").lower()
    late = _is_late(cin, status_raw)
    name = (meta or {}).get("name") or record.get("employee_name") or "Employee"
    department = (meta or {}).get("department") or record.get("department") or "—"
    cout = _as_date(record.get("clock_out_at"))

    if cout:
        activity = f"Clocked Out · {_format_sast_hm(cout)} · In {hh_in}"
        status = "clocked_out"
        event_at = cout
    elif "break" in status_raw:
        activity = f"On Break · In {hh_in} (Late)" if late else f"On Break · In {hh_in}"
        status = "on_break"
        event_at = cin
    else:
        activity = f"Clocked In · Late · {hh_in}" if late else f"Clocked In · {hh_in}"
        status = "late" if late else "on_time"
        event_at = cin

    return {
        "employee_id": str(record.get("employee_id") or ""),
        "employee": name,
        "employee_name": name,
        "name": name,
        "department": department,
        "description": activity,
        "action": activity,
        "activity": activity,
        "created_at": event_at.isoformat(),
        "timestamp": event_at.isoformat(),
        "status": status,
        "work_date": record.get("work_date") or today_south_africa(),
        "clock_in_at": record.get("clock_in_at"),
        "clock_out_at": record.get("clock_out_at"),
    }


async def _dashboard_data(db, ctx):
    from datetime import timedelta, time as day_time, date
    from app.domain import PEOPLE_OVERSIGHT, BUSINESS_WORK, role, refs, name, now, SAST
    from app.security import is_active
    from app.routers.tasks import visibility_filter, payload as task_payload, state, CLOSED
    current_role = role(ctx)
    people_manager = current_role in PEOPLE_OVERSIGHT
    business_lead = current_role in BUSINESS_WORK
    today = date.fromisoformat(today_south_africa())
    start = datetime.combine(today, day_time.min, SAST)
    end = start + timedelta(days=1)
    week = start - timedelta(days=start.weekday())
    if people_manager:
        people_query = {}
    elif business_lead and ctx['employee'].get('department'):
        people_query = {'department': ctx['employee']['department']}
    else:
        people_query = {'_id': ctx['employee']['_id']}
    people = await db['employees'].find(people_query).to_list(None)
    active = [p for p in people if is_active(p.get('status'))]
    attendance_query = {'work_date': today.isoformat()}
    if not people_manager:
        if business_lead and ctx['employee'].get('department'):
            attendance_query['department'] = ctx['employee']['department']
        else:
            attendance_query['employee_id'] = {'$in': refs(ctx['employee'])}
    attendance = await db['attendance'].find(attendance_query).to_list(None)
    tasks = await db['work_assignments'].find(visibility_filter(ctx)).to_list(None)
    if people_manager:
        approvals_query = {}
    elif business_lead:
        approvals_query = {'$or': [
            {'employee_id': {'$in': refs(ctx['employee'])}},
            {'current_stage': 'Business'},
        ]}
    else:
        approvals_query = {'employee_id': {'$in': refs(ctx['employee'])}}
    approvals = await db['approvals'].find(approvals_query).to_list(None)
    task_rows = [task_payload(t) for t in tasks]
    due = [t for t in tasks if state(t.get('status')) not in CLOSED and _as_date(t.get('due_date')) and start <= _as_date(t['due_date']) < end]
    overdue = [t for t in tasks if state(t.get('status')) not in CLOSED and _as_date(t.get('due_date')) and _as_date(t['due_date']) < now()]
    completed = [t for t in tasks if state(t.get('status')) == 'Completed' and _as_date(t.get('completed_at')) and _as_date(t['completed_at']) >= week]
    working = {str(a['employee_id']) for a in attendance if a.get('clock_in_at') and not a.get('clock_out_at')}
    on_leave = {str(a['employee_id']) for a in approvals if a.get('request_type') == 'Leave' and a.get('status') == 'Approved' and a.get('start_date', '9999') <= today.isoformat() <= a.get('end_date', '')}
    pending = [a for a in approvals if str(a.get('status')).lower() == 'pending']
    activity = [_activity_from_attendance(a, None) for a in attendance]
    activity = [a for a in activity if a]
    total = len(active)
    present = len(working)
    late = sum(bool(_as_date(a.get('clock_in_at')) and _is_late(_as_date(a['clock_in_at']))) for a in attendance)
    waiting = sum(state(t.get('status')) in {'Waiting Review', 'Escalated'} for t in tasks)
    attendance_rows = []
    for record in attendance:
        activity_row = _activity_from_attendance(record, None)
        if activity_row:
            attendance_rows.append(activity_row)
    task_status = {label: sum(state(t.get('status')) == label for t in tasks) for label in ('Pending', 'Assigned', 'In Progress', 'Waiting Review', 'Escalated', 'Completed')}
    result = {'success': True, 'role': role(ctx), 'total_people': total, 'total_employees': len(people), 'active_employees': total,
        'people_working': present, 'people_on_site': present, 'people_on_leave': len(on_leave),
        'tasks_due_today': len(due), 'tasks_high_priority': sum(str(t.get('priority')).lower() in {'high','urgent','critical'} for t in due),
        'tasks_overdue': len(overdue), 'tasks_waiting_review': waiting, 'completed_this_week': len(completed),
        'tasks_in_progress': sum(state(t.get('status')) == 'In Progress' for t in tasks), 'pending_tasks': sum(state(t.get('status')) == 'Pending' for t in tasks),
        'pending_approvals': len(pending), 'upcoming_deadlines': len(due), 'actual_task_hours': sum(t['elapsed_hours'] for t in task_rows),
        'present_count': present, 'absent_count': max(0,total-present-len(on_leave)), 'late_count': late,
        'attendance_total': total, 'attendance_pct': round(present/total*100) if total else None,
        'latest_activity': activity, 'recent_activity': activity, 'activity': activity,
        'attendance_rows': attendance_rows, 'task_status': task_status,
        'approvals_queue': [{'id': str(a['_id']), 'title': a.get('title'), 'type': a.get('request_type'), 'employee': a.get('requested_by'), 'when': a.get('submitted_at'), 'status': a.get('status'), 'current_stage': a.get('current_stage')} for a in ([a for a in pending if a.get('current_stage') == 'Director'] if role(ctx) == 'Director' else pending)[:8]],
    }
    result['attendance'] = {'present': present, 'absent': result['absent_count'], 'late': late, 'total': total, 'percentage': result['attendance_pct'], 'pct': result['attendance_pct'], 'clocked_in_today': sum(bool(a.get('clock_in_at')) for a in attendance)}
    result['tasks'] = {'due_today': len(due), 'high_priority_due_today': result['tasks_high_priority']}
    return result, {'people': people, 'active': active, 'attendance': attendance, 'tasks': tasks,
                    'task_rows': task_rows, 'approvals': approvals, 'pending': pending,
                    'due': due, 'overdue': overdue, 'completed': completed,
                    'start': start, 'end': end, 'today': today}


def _task_item(task: dict) -> dict:
    from app.routers.tasks import payload
    row = payload(task)
    return {key: row.get(key) for key in (
        'id', 'title', 'status', 'priority', 'assigned_employee', 'assignee',
        'department', 'due_date', 'estimated_hours', 'actual_hours', 'elapsed_hours',
        'created_at', 'completed_at')}


def _approval_item(row: dict) -> dict:
    return {'id': str(row.get('_id') or ''), 'title': row.get('title'),
            'type': row.get('request_type'), 'employee': row.get('requested_by'),
            'when': row.get('submitted_at') or row.get('created_at'),
            'status': row.get('status'), 'current_stage': row.get('current_stage')}


async def _personal_dashboard(db, ctx, common, raw):
    from app.domain import refs, name
    employee = ctx['employee']
    own_attendance = raw['attendance'][0] if raw['attendance'] else {}
    clock_in = _as_date(own_attendance.get('clock_in_at'))
    clock_out = _as_date(own_attendance.get('clock_out_at'))
    hours = None
    if clock_in:
        hours = round(max(0, ((clock_out or datetime.now(timezone.utc)) - clock_in).total_seconds()) / 3600, 2)
    attendance_status = 'Not clocked in'
    if clock_in:
        attendance_status = 'Clocked out' if clock_out else 'Clocked in'
    notifications = await db['notifications'].count_documents({
        'employee_id': {'$in': refs(employee)}, 'read': {'$ne': True}})
    pending_leave = sum(a.get('request_type') == 'Leave' and str(a.get('status')).lower() == 'pending' for a in raw['approvals'])
    return {
        'success': True, 'dashboard_type': 'personal', 'role': common['role'],
        'employee': {'id': str(employee['_id']), 'name': name(employee),
                     'department': employee.get('department'), 'position': employee.get('position') or employee.get('job_title')},
        'total_people': 1, 'tasks_due_today': common['tasks_due_today'],
        'tasks_in_progress': common['tasks_in_progress'], 'pending_tasks': common['pending_tasks'],
        'actual_task_hours': common['actual_task_hours'], 'hours_worked_today': hours,
        'attendance_status': attendance_status, 'leave_balance': employee.get('leave_balance'),
        'my_pending_leave': pending_leave, 'pending_approvals': len(raw['pending']),
        'unread_notifications': notifications,
        'my_tasks': [_task_item(t) for t in raw['tasks'][:12]],
    }


async def _director_dashboard(db, ctx, common, raw):
    from app.routers.tasks import state, CLOSED
    important = [t for t in raw['tasks'] if state(t.get('status')) not in CLOSED and str(t.get('priority') or '').lower() in {'high', 'urgent', 'critical'}]
    director_queue = [a for a in raw['pending'] if a.get('current_stage') == 'Director']
    expired_docs = await db['documents'].count_documents({'expiry_status': 'expired'})
    health = 'Attention required' if raw['overdue'] or expired_docs else 'On track'
    business_summary = {
        'health': health, 'people_working': common['people_working'],
        'people_on_leave': common['people_on_leave'], 'overdue_work': common['tasks_overdue'],
        'completed_this_week': common['completed_this_week'],
    }
    return {
        'success': True, 'dashboard_type': 'director', 'role': common['role'],
        'business_health': health, 'business_summary': business_summary,
        'total_people': common['total_people'],
        'people_working': common['people_working'], 'people_on_leave': common['people_on_leave'],
        'attendance': common['attendance'], 'important_work': [_task_item(t) for t in important[:8]],
        'important_work_count': len(important), 'tasks_overdue': common['tasks_overdue'],
        'completed_this_week': common['completed_this_week'],
        'pending_approvals': len(director_queue),
        'approvals_queue': [_approval_item(a) for a in director_queue[:8]],
        'compliance_attention': expired_docs,
    }


async def _business_dashboard(db, ctx, common, raw):
    task_dump = {'total': len(raw['tasks']), **common['task_status'],
                 'overdue': common['tasks_overdue'], 'due_today': common['tasks_due_today']}
    return {
        'success': True, 'dashboard_type': 'business_lead', 'role': common['role'],
        'department': ctx['employee'].get('department'), 'total_people': common['total_people'],
        'people_working': common['people_working'], 'people_on_leave': common['people_on_leave'],
        'attendance': common['attendance'], 'attendance_rows': common['attendance_rows'],
        'business_overview': {'team_members': common['total_people'],
                              'people_working': common['people_working'], 'tasks': task_dump},
        'task_dump': task_dump,
        'team_work': [_task_item(t) for t in raw['tasks'][:30]],
        'actual_task_hours': common['actual_task_hours'],
        'task_duration': {'actual_hours': common['actual_task_hours'],
                          'estimated_hours': sum(float(t.get('estimated_hours') or 0) for t in raw['tasks'])},
        'latest_activity': common['latest_activity'][:20],
        'business_activity': common['latest_activity'][:20],
        'pending_approvals': common['pending_approvals'],
        'approvals_queue': common['approvals_queue'],
    }


async def _operations_dashboard(db, ctx, common, raw):
    from app.routers.tasks import workload, decision_queue, state
    from app.routers.notifications import recipient
    office = await db['office_requests'].find({}).sort('created_at', -1).to_list(None)
    events = await db['calendar_events'].find({}).to_list(None)
    documents = await db['documents'].find({'expiry_status': {'$in': ['expired', 'expiring_soon']}}).to_list(None)
    unread = await db['notifications'].count_documents({**recipient(ctx), 'read': {'$ne': True}})
    leave = [a for a in raw['approvals'] if a.get('request_type') == 'Leave' and str(a.get('status')).lower() == 'pending']
    review = [t for t in raw['tasks'] if state(t.get('status')) in {'Waiting Review', 'Escalated'}]
    incoming = [t for t in raw['tasks'] if state(t.get('status')) == 'Pending']
    upcoming = []
    for event in events:
        event_at = _as_date(event.get('start_date') or event.get('start'))
        if event_at and event_at >= raw['start'].astimezone(timezone.utc):
            upcoming.append(event)
    upcoming.sort(key=lambda e: str(e.get('start_date') or e.get('start') or ''))
    operational_issues = (
        [{'type': 'Overdue task', 'title': t.get('title'), 'reference_id': str(t.get('_id'))} for t in raw['overdue'][:10]] +
        [{'type': 'Document expiry', 'title': d.get('name') or d.get('document_type'), 'reference_id': str(d.get('_id'))} for d in documents[:10]]
    )
    result = dict(common)
    employee_workload = (await workload(ctx))['workload']
    result.update({
        'dashboard_type': 'operations',
        'incoming_task_dump': [_task_item(t) for t in incoming[:30]],
        'assignment_queue': [_task_item(t) for t in incoming[:30]],
        'employee_workload': employee_workload, 'workload': employee_workload,
        'task_duration': {'actual_hours': common['actual_task_hours'],
                          'estimated_hours': sum(float(t.get('estimated_hours') or 0) for t in raw['tasks'])},
        'decision_queue': await decision_queue(ctx),
        'qa_review_queue': [_task_item(t) for t in review[:30]],
        'leave_queue': [_approval_item(a) for a in leave[:30]],
        'office_requests': [{'id': str(o.get('_id')), 'item': o.get('item'), 'quantity': o.get('quantity'),
                             'requested_by': o.get('requested_by'), 'status': o.get('status'),
                             'current_stage': o.get('current_stage')} for o in office[:30]],
        'calendar_upcoming': [{'id': str(e.get('_id')), 'title': e.get('title'),
                               'start_date': e.get('start_date') or e.get('start'),
                               'end_date': e.get('end_date') or e.get('end')} for e in upcoming[:20]],
        'notifications_unread': unread,
        'hr': {'active_employees': common['active_employees'],
               'people_on_leave': common['people_on_leave'], 'documents_needing_attention': len(documents)},
        'operational_issues': operational_issues,
    })
    return result


async def _build_summary(db, ctx, forced_type: str | None = None):
    from app.domain import role
    common, raw = await _dashboard_data(db, ctx)
    current_role = role(ctx)
    kind = forced_type or ({'Director': 'director', 'Business Lead': 'business_lead',
                            'Operations Manager': 'operations', 'Super Admin': 'operations'}).get(current_role)
    if kind == 'director':
        result = await _director_dashboard(db, ctx, common, raw)
    elif kind == 'business_lead':
        result = await _business_dashboard(db, ctx, common, raw)
    elif kind == 'operations':
        result = await _operations_dashboard(db, ctx, common, raw)
    elif current_role == 'Branch Manager':
        result = dict(common, dashboard_type='management')
    else:
        result = await _personal_dashboard(db, ctx, common, raw)
    return serialize_id(result)


@router.get('/api/dashboard/summary')
@router.get('/api/v1/nexus/dashboard')
async def dashboard_summary(ctx: dict = Depends(require_session)):
    # Do not share cached management data across identities or after role changes.
    return await _build_summary(ctx['db'], ctx)


@router.get('/api/dashboard/business-lead')
async def business_lead(ctx: dict = Depends(require_session)):
    from app.domain import require_roles
    require_roles(ctx, {'Business Lead', 'Branch Manager', 'Super Admin'})
    return await _build_summary(ctx['db'], ctx, 'business_lead')


@router.get('/api/dashboard/director')
async def director(ctx: dict = Depends(require_session)):
    from app.domain import require_roles
    require_roles(ctx, {'Director', 'Super Admin'})
    return await _build_summary(ctx['db'], ctx, 'director')


@router.get('/api/dashboard/operations')
async def operations(ctx: dict = Depends(require_session)):
    from app.domain import require_roles, OPERATIONS
    require_roles(ctx, OPERATIONS)
    return await _build_summary(ctx['db'], ctx, 'operations')
