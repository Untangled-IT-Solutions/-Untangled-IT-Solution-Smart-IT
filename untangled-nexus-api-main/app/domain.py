"""Shared Nexus identity, permissions and atomic record updates."""
from datetime import date, datetime, time, timezone
import re
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pymongo import ReturnDocument

from app.security import employee_reference_values, serialize_id

SAST = ZoneInfo('Africa/Johannesburg')
ROLES = ('Director', 'Branch Manager', 'Business Lead', 'Operations Manager', 'Staff', 'Intern')
MANAGEMENT = set(ROLES[:4]) | {'Super Admin'}
OPERATIONS = {'Operations Manager', 'Super Admin'}
HR = OPERATIONS | {'Director', 'Branch Manager'}
PEOPLE_OVERSIGHT = HR
TASK_OVERSIGHT = OPERATIONS | {'Director', 'Branch Manager'}
BUSINESS_WORK = {'Business Lead'}


def now():
    return datetime.now(timezone.utc)


def role(ctx):
    raw = str(ctx['user'].get('role') or 'Staff').strip().replace('_', ' ').lower()
    return next((r for r in (*ROLES, 'Super Admin') if r.lower() == raw), 'Staff')


def require_roles(ctx, allowed):
    if role(ctx) not in allowed:
        raise HTTPException(403, 'You do not have permission for this operation.')


def name(employee):
    return employee.get('full_name') or ' '.join(filter(None, [employee.get('first_name'), employee.get('surname') or employee.get('last_name')]))


def refs(employee):
    values = []
    for key in ('_id', 'employee_id', 'id'):
        values.extend(employee_reference_values(employee.get(key)))
    return values


def own(ctx, value):
    return value is not None and any(str(value) == str(v) for v in refs(ctx['employee']))


def id_filter(value):
    return {'_id': {'$in': employee_reference_values(value)}}


async def employee_by_reference(db, value):
    if value is None or isinstance(value, (dict, list, bool)):
        raise HTTPException(422, 'An employee reference is required.')
    values = employee_reference_values(value)
    rows = await db['employees'].find({'$or': [{k: {'$in': values}} for k in ('_id', 'employee_id', 'id')]}).limit(2).to_list(2)
    if not rows:
        exact = {'$regex': '^' + re.escape(str(value).strip()) + '$', '$options': 'i'}
        rows = await db['employees'].find({'$or': [{k: exact} for k in ('full_name', 'email', 'email_address')]}).limit(2).to_list(2)
    if len(rows) > 1:
        raise HTTPException(409, 'Employee reference is ambiguous; use the employee ID.')
    if not rows:
        raise HTTPException(404, 'Employee not found.')
    return rows[0]


def public_employee(employee):
    fields = ('_id', 'employee_id', 'id', 'employee_number', 'full_name', 'first_name', 'surname', 'last_name', 'department', 'position', 'job_title', 'role', 'status', 'email', 'profile_photo')
    out = {k: employee[k] for k in fields if k in employee}
    out['full_name'] = name(employee)
    out['id'] = str(employee['_id'])
    return serialize_id(out)


def as_datetime(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, date):
        return datetime.combine(value, time.min, SAST)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.replace(tzinfo=SAST) if parsed.tzinfo is None else parsed


def date_string(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        raise HTTPException(422, 'Date must be YYYY-MM-DD.')


async def change(collection, record, updates, event=None):
    """Compare-and-set prevents concurrent timers/reviews from overwriting changes."""
    query = {'_id': record['_id'], 'revision': record.get('revision')}
    update = {'$set': {**updates, 'updated_at': now()}, '$inc': {'revision': 1}}
    if event:
        update['$push'] = {'history': event}
    result = await collection.find_one_and_update(query, update, return_document=ReturnDocument.AFTER)
    if not result:
        raise HTTPException(409, 'Record changed; reload and retry.')
    return result


def audit(ctx, action, note=''):
    return {'action': action, 'note': note, 'user_id': ctx['user']['_id'], 'employee_id': ctx['employee']['_id'], 'created_by': name(ctx['employee']), 'role': role(ctx), 'created_at': now()}


async def notify(db, key, employee_id, title, message, reference_type='', reference_id=''):
    # _id supplies durable uniqueness even before optional secondary indexes exist.
    result = await db['notifications'].update_one({'_id': key}, {'$setOnInsert': {
        'employee_id': employee_id, 'title': title, 'message': message,
        'reference_type': reference_type, 'reference_id': str(reference_id),
        'category': reference_type or 'General', 'read': False,
        'delivery_status': 'created', 'created_at': now(),
    }}, upsert=True)
    created = result.upserted_id is not None
    if created:
        from app.notification_events import publish
        publish(employee_id, {
            'id': key,
            'title': title,
            'message': message,
            'reference_type': reference_type,
            'reference_id': str(reference_id),
        })
    return created


async def notify_roles(db, key, roles, title, message, reference_type='', reference_id=''):
    users = await db['users'].find({'role': {'$in': list(roles)}, 'status': {'$nin': ['inactive', 'disabled', 'suspended']}}).to_list(None)
    created = 0
    for user in users:
        if user.get('employee_id') is not None:
            created += int(await notify(db, f'{key}:{user["_id"]}', user['employee_id'], title, message, reference_type, reference_id))
    return created
