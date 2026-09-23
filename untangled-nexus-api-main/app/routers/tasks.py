from __future__ import annotations

from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.security import require_session, serialize_id, is_active
from app.domain import (MANAGEMENT, OPERATIONS, TASK_OVERSIGHT, BUSINESS_WORK, SAST, now, role, require_roles, name,
    refs, own, id_filter, employee_by_reference, as_datetime, change, audit, notify, notify_roles)

router = APIRouter(tags=["tasks"])
CLOSED = {"Completed", "Cancelled"}
STATES = {"Pending", "Assigned", "In Progress", "Paused", "Waiting Review", "Returned", "Escalated", *CLOSED}


def state(value):
    aliases = {"in_progress": "In Progress", "waiting_review": "Waiting Review", "cancelled": "Cancelled", "canceled": "Cancelled", "done": "Completed"}
    raw = str(value or "Pending").strip()
    return aliases.get(raw.lower(), next((s for s in STATES if s.lower() == raw.lower()), raw))


def personal_filter(ctx):
    values = refs(ctx['employee'])
    return {'$or': [{k: {'$in': values}} for k in ('assignee_id', 'assigned_to', 'employee_id')]}


def visibility_filter(ctx):
    """Scope tasks from authenticated role and employee identity."""
    current_role = role(ctx)
    if current_role in TASK_OVERSIGHT:
        return {}
    personal = personal_filter(ctx)
    if current_role in BUSINESS_WORK:
        values = refs(ctx['employee'])
        clauses = [personal, {'created_by_employee_id': {'$in': values}}]
        department = str(ctx['employee'].get('department') or '').strip()
        if department:
            clauses.append({'department': department})
        return {'$or': clauses}
    return personal


def assigned(ctx, task):
    return any(own(ctx, task.get(k)) for k in ('assignee_id', 'assigned_to', 'employee_id'))


async def load_task(ctx, task_id):
    task = await ctx['db']['work_assignments'].find_one(id_filter(task_id))
    if not task:
        raise HTTPException(404, 'Task not found.')
    if role(ctx) not in TASK_OVERSIGHT:
        visible = await ctx['db']['work_assignments'].find_one({'$and': [id_filter(task_id), visibility_filter(ctx)]})
        if not visible:
            raise HTTPException(403, 'You do not have access to this task.')
    return task


def payload(task):
    result = dict(task)
    result['status'] = state(task.get('status'))
    result['actual_hours'] = float(task.get('actual_hours') or 0)
    active = task.get('active_timer_started_at')
    result['elapsed_hours'] = result['actual_hours'] + (max(0, (now() - as_datetime(active)).total_seconds()) / 3600 if active else 0)
    result['id'] = str(task['_id'])
    return serialize_id(result)


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default='', max_length=20000)
    assigned_employee: str = ''
    assignee: str = ''
    assigned_to: Any = None
    priority: str = 'Normal'
    status: str = 'Pending'
    due_date: str | None = None
    estimated_hours: float = Field(default=0, ge=0, le=100000)
    category: str = 'Administration'
    department: str = ''
    attachments: list[dict] = Field(default_factory=list, max_length=10)
    attachments_json: str | None = None
    checklist: str = '[]'


@router.post('/api/tasks')
async def create_task(body: TaskCreate, ctx: dict = Depends(require_session)):
    require_roles(ctx, MANAGEMENT)
    data = body.model_dump(exclude={'attachments_json'})
    data['title'] = body.title.strip()
    if not data['title']:
        raise HTTPException(422, 'Title is required.')
    target = body.assigned_to or body.assigned_employee or body.assignee
    if str(target or '').strip().lower() == 'unassigned':
        target = None
    employee = None
    if target:
        require_roles(ctx, OPERATIONS)
        employee = await employee_by_reference(ctx['db'], target)
        if not is_active(employee.get('status')):
            raise HTTPException(422, 'Cannot assign inactive employee.')
    if state(body.status) not in {'Pending', 'Assigned'}:
        raise HTTPException(422, 'New tasks must enter the assignment queue.')
    if body.due_date:
        try:
            data['due_date'] = as_datetime(body.due_date)
        except ValueError:
            raise HTTPException(422, 'Invalid due date.')
    data.update(status='Assigned' if employee else 'Pending', assignee_id=employee['_id'] if employee else None,
        assigned_to=employee['_id'] if employee else None, assigned_employee=name(employee) if employee else '',
        assignee=name(employee) if employee else '', created_by_id=ctx['user']['_id'],
        created_by_employee_id=ctx['employee']['_id'], assigned_by=name(ctx['employee']) if employee else '',
        department=(body.department if role(ctx) in TASK_OVERSIGHT and body.department else ctx['employee'].get('department', '')),
        actual_hours=0.0, active_timer_started_at=None, revision=0, created_at=now(), updated_at=now(),
        history=[audit(ctx, 'create')])
    from bson import ObjectId
    data['_id'] = ObjectId()
    from app.routers.documents import store_attachments
    data['attachments'] = await store_attachments(ctx, body.attachments, task_id=data['_id'])
    await ctx['db']['work_assignments'].insert_one(data)
    if employee:
        await notify(ctx['db'], f"task:{data['_id']}:assigned:0", employee['_id'], 'Task assigned', data['title'], 'Task', data['_id'])
    else:
        await notify_roles(ctx['db'], f"task:{data['_id']}:inbox", OPERATIONS, 'Incoming task', data['title'], 'Task', data['_id'])
    return {'success': True, 'task': payload(data)}


@router.get('/api/tasks')
async def list_tasks(scope: str = 'all', limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), ctx: dict = Depends(require_session)):
    scope = scope.lower()
    if scope not in {'all', 'personal', 'mine', 'inbox', 'reviews', 'overdue', 'department'}:
        raise HTTPException(422, 'Unknown task scope.')
    query = personal_filter(ctx) if scope in {'personal', 'mine'} else visibility_filter(ctx)
    if scope == 'inbox':
        query = {'$and': [query, {'status': {'$in': ['Pending', 'pending']}}]}
    elif scope == 'reviews':
        query = {'$and': [query, {'status': {'$in': ['Waiting Review', 'waiting_review', 'Escalated']}}]}
    elif scope == 'overdue':
        query = {'$and': [query, {'due_date': {'$lt': now()}, 'status': {'$nin': list(CLOSED)}}]}
    elif scope == 'department':
        query = {'$and': [query, {'department': ctx['employee'].get('department', '')}]}
    rows = await ctx['db']['work_assignments'].find(query).sort('updated_at', -1).skip(offset).limit(limit).to_list(limit)
    items = [payload(row) for row in rows]
    return {'success': True, 'tasks': items, 'items': items, 'total': await ctx['db']['work_assignments'].count_documents(query)}


@router.get('/api/tasks/workload')
async def workload(ctx: dict = Depends(require_session)):
    require_roles(ctx, MANAGEMENT)
    rows = await ctx['db']['work_assignments'].find({'$and': [visibility_filter(ctx), {'status': {'$nin': list(CLOSED)}}]}).to_list(None)
    grouped = {}
    for row in rows:
        key = str(row.get('assignee_id') or row.get('assigned_to') or '')
        group = grouped.setdefault(key, {'employee_id': key, 'employee': row.get('assigned_employee') or 'Unassigned', 'tasks': 0, 'actual_hours': 0.0, 'estimated_hours': 0.0})
        group['tasks'] += 1
        group['actual_hours'] += payload(row)['elapsed_hours']
        group['estimated_hours'] += float(row.get('estimated_hours') or 0)
    return {'success': True, 'workload': list(grouped.values())}


@router.get('/api/tasks/decision-queue')
async def decision_queue(ctx: dict = Depends(require_session)):
    require_roles(ctx, OPERATIONS)
    rows = await ctx['db']['work_assignments'].find({'status': {'$in': ['Pending', 'Waiting Review', 'Escalated']}}).sort('created_at', 1).to_list(None)
    return {'success': True, 'tasks': [payload(row) for row in rows], 'summary': {s: sum(state(r.get('status')) == s for r in rows) for s in ('Pending', 'Waiting Review', 'Escalated')}}


@router.get('/api/tasks/{task_id}')
async def get_task(task_id: str, ctx: dict = Depends(require_session)):
    return {'success': True, 'task': payload(await load_task(ctx, task_id))}


class Action(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    note: str = Field(default='', max_length=20000)
    assigned_to: Any = None
    employee_id: Any = None
    hours: float | None = Field(default=None, gt=0, le=24)
    hours_logged: float | None = Field(default=None, gt=0, le=24)


async def act(ctx, task, action, body):
    current = state(task.get('status'))
    updates = {}
    if action in {'assign', 'reassign'}:
        require_roles(ctx, OPERATIONS)
        if current in CLOSED or current in {'Waiting Review', 'Escalated'}:
            raise HTTPException(409, 'Task cannot be reassigned in this state.')
        if current == 'In Progress' or task.get('active_timer_started_at'):
            raise HTTPException(409, 'Pause the task timer before reassigning work.')
        target = body.assigned_to if body.assigned_to is not None else body.employee_id
        if target is None:
            target = body.note
        employee = await employee_by_reference(ctx['db'], target) if target and str(target).lower() != 'unassigned' else None
        if employee and not is_active(employee.get('status')):
            raise HTTPException(422, 'Cannot assign inactive employee.')
        updates.update(assignee_id=employee['_id'] if employee else None, assigned_to=employee['_id'] if employee else None,
            assigned_employee=name(employee) if employee else '', assignee=name(employee) if employee else '',
            assigned_by=name(ctx['employee']), status='Assigned' if employee else 'Pending')
    elif action in {'approve-review', 'review', 'complete', 'return', 'escalate', 'cancel'}:
        if action in {'approve-review', 'review', 'complete', 'return'}:
            require_roles(ctx, {'Director', 'Super Admin'} if current == 'Escalated' else OPERATIONS)
            if current not in {'Waiting Review', 'Escalated'}:
                raise HTTPException(409, 'Task must be submitted for review first.')
            if assigned(ctx, task):
                raise HTTPException(403, 'You cannot approve or review your own work.')
            if action == 'return' and not body.note.strip():
                raise HTTPException(422, 'A correction reason is required.')
            updates['status'] = 'Returned' if action == 'return' else 'Completed'
            if action == 'return':
                updates['returned_reason'] = body.note
            if current == 'Escalated':
                updates['director_approval_status'] = 'Returned' if action == 'return' else 'Approved'
        else:
            require_roles(ctx, OPERATIONS)
            if current in CLOSED:
                raise HTTPException(409, 'Task is already closed.')
            if action == 'escalate' and current != 'Waiting Review':
                raise HTTPException(409, 'Only submitted work can be escalated.')
            updates['status'] = 'Escalated' if action == 'escalate' else 'Cancelled'
        if updates['status'] == 'Completed':
            updates.update(completed_at=now(), progress=100)
    else:
        if not assigned(ctx, task):
            raise HTTPException(403, 'Only the assigned employee may record work.')
        if action in {'start', 'resume'}:
            valid_states = {'Assigned', 'Returned'} if action == 'start' else {'Paused'}
            if current not in valid_states or task.get('active_timer_started_at'):
                verb = 'start' if action == 'start' else 'resume'
                raise HTTPException(409, f'Task timer cannot {verb} in this state.')
            updates.update(status='In Progress', active_timer_started_at=now(), started_at=task.get('started_at') or now(), start_date=task.get('start_date') or now())
        elif action == 'pause':
            if current != 'In Progress' or not task.get('active_timer_started_at'):
                raise HTTPException(409, 'Task has no active timer.')
            updates['status'] = 'Paused'
        elif action == 'submit-review':
            if current not in {'In Progress', 'Paused'}:
                raise HTTPException(409, 'Task cannot be submitted in this state.')
            updates.update(status='Waiting Review', submitted_at=now())
        elif action == 'log-time':
            hours = body.hours if body.hours is not None else body.hours_logged
            if hours is None:
                raise HTTPException(422, 'hours is required.')
            if current != 'Paused' or task.get('active_timer_started_at'):
                raise HTTPException(409, 'Manual time can only be added while the task is paused.')
            updates['actual_hours'] = float(task.get('actual_hours') or 0) + hours
        else:
            raise HTTPException(404, 'Unknown task action.')
    if action not in {'start', 'resume', 'log-time'} and task.get('active_timer_started_at'):
        updates['actual_hours'] = payload(task)['elapsed_hours']
        updates['active_timer_started_at'] = None
    if body.note and action not in {'assign', 'reassign'}:
        updates['comments'] = body.note
    event = audit(ctx, action, body.note)
    if action == 'log-time':
        event['hours'] = body.hours if body.hours is not None else body.hours_logged
    result = await change(ctx['db']['work_assignments'], task, updates, event)
    key = f"task:{task['_id']}:{result['revision']}"
    if result.get('assignee_id'):
        await notify(ctx['db'], key, result['assignee_id'], f'Task: {action}', result['title'], 'Task', task['_id'])
    if action == 'submit-review':
        await notify_roles(ctx['db'], key, OPERATIONS, 'Work submitted for review', result['title'], 'Task', task['_id'])
    elif action == 'escalate':
        await notify_roles(ctx['db'], key, {'Director'}, 'Director review required', result['title'], 'Task', task['_id'])
    return {'success': True, 'task': payload(result)}


def action_endpoint(action):
    async def endpoint(task_id: str, body: Action = Body(default=Action()), ctx: dict = Depends(require_session)):
        return await act(ctx, await load_task(ctx, task_id), action, body)
    endpoint.__name__ = 'task_' + action.replace('-', '_')
    return endpoint


for action in ('assign', 'reassign', 'start', 'pause', 'resume', 'log-time', 'submit-review', 'review', 'approve-review', 'complete', 'return', 'escalate', 'cancel'):
    router.add_api_route('/api/tasks/{task_id}/' + action, action_endpoint(action), methods=['POST'])


@router.patch('/api/tasks/{task_id}')
@router.put('/api/tasks/{task_id}')
async def update_task(task_id: str, body: dict = Body(...), ctx: dict = Depends(require_session)):
    task = await load_task(ctx, task_id)
    allowed = {'title', 'description', 'priority', 'category', 'department', 'due_date', 'estimated_hours', 'status', 'progress', 'notes', 'note', 'comments', 'assigned_employee', 'assignee', 'assigned_to', 'hours_logged', 'checklist', 'attachments', 'attachments_json'}
    if set(body) - allowed:
        raise HTTPException(422, 'Unsupported task fields: ' + ', '.join(sorted(set(body) - allowed)))
    for key in ('title', 'description', 'priority', 'category', 'department', 'note', 'notes', 'comments', 'checklist'):
        if key in body and (not isinstance(body[key], str) or len(body[key]) > 20000):
            raise HTTPException(422, 'Invalid text field: ' + key)
    # Interpret old desktop PATCH writes through the same permission/state machine.
    if 'hours_logged' in body:
        if set(body) - {'hours_logged', 'note'}:
            raise HTTPException(422, 'Log time separately from task edits.')
        try:
            action_body = Action(hours_logged=body['hours_logged'], note=body.get('note') or '')
        except ValidationError:
            raise HTTPException(422, 'Invalid hours or note.')
        return await act(ctx, task, 'log-time', action_body)
    assignment = next((body[k] for k in ('assigned_to', 'assigned_employee', 'assignee') if k in body), None)
    if any(k in body for k in ('assigned_to', 'assigned_employee', 'assignee')):
        if set(body) - {'assigned_to', 'assigned_employee', 'assignee', 'status'}:
            raise HTTPException(422, 'Assign separately from task edits.')
        return await act(ctx, task, 'assign', Action(assigned_to=assignment or ''))
    if 'status' in body and state(body['status']) != state(task.get('status')):
        action = {'In Progress': 'start', 'Paused': 'pause', 'Waiting Review': 'submit-review', 'Completed': 'complete', 'Returned': 'return', 'Escalated': 'escalate', 'Cancelled': 'cancel'}.get(state(body['status']))
        if not action:
            raise HTTPException(422, 'Use assignment to move a task into the assignment queue.')
        if set(body) - {'status', 'note', 'comments'}:
            raise HTTPException(422, 'Change status separately from task edits.')
        return await act(ctx, task, action, Action(note=body.get('note') or body.get('comments') or ''))
    management_fields = {'title', 'description', 'priority', 'category', 'department', 'due_date', 'estimated_hours'}
    if set(body) & management_fields:
        require_roles(ctx, OPERATIONS)
    elif not assigned(ctx, task):
        require_roles(ctx, OPERATIONS)
    if state(task.get('status')) in CLOSED:
        raise HTTPException(409, 'Closed tasks cannot be edited.')
    updates = {k: v for k, v in body.items() if k not in {'status', 'attachments_json', 'note', 'notes'}}
    if 'progress' in updates:
        try:
            progress = float(updates['progress'])
            if not 0 <= progress <= 100:
                raise ValueError()
            updates['progress'] = progress
        except (ValueError, TypeError):
            raise HTTPException(422, 'Progress must be between 0 and 100.')
    if 'title' in updates and (not isinstance(updates['title'], str) or not updates['title'].strip()):
        raise HTTPException(422, 'Title is required.')
    if updates.get('due_date'):
        try:
            updates['due_date'] = as_datetime(updates['due_date'])
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid due date.')
    if 'estimated_hours' in updates:
        try:
            value = float(updates['estimated_hours'])
            if not 0 <= value <= 100000:
                raise ValueError()
            updates['estimated_hours'] = value
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid estimated hours.')
    if 'attachments' in updates:
        from app.routers.documents import store_attachments
        updates['attachments'] = await store_attachments(ctx, updates['attachments'], task_id=task['_id'])
    if body.get('note') or body.get('notes'):
        updates['comments'] = body.get('note') or body.get('notes')
    result = await change(ctx['db']['work_assignments'], task, updates, audit(ctx, 'update'))
    return {'success': True, 'task': payload(result)}
