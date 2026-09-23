from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool
from app.security import require_session, hash_pbkdf2_sha256, normalise_login, serialize_id, is_active
from app.domain import ROLES, HR, role, require_roles, employee_by_reference, id_filter, refs, now, name, audit

router = APIRouter(prefix='/api/admin', tags=['users'])
RANK = {'Intern': 0, 'Staff': 10, 'Business Lead': 30, 'Operations Manager': 40, 'Branch Manager': 50, 'Director': 80, 'Super Admin': 100}


def can_change(ctx, target_role, target_id=None):
    require_roles(ctx, HR)
    actor = role(ctx)
    canonical = next((r for r in RANK if r.lower() == str(target_role).lower()), None)
    if canonical is None or (actor != 'Super Admin' and RANK[canonical] >= RANK[actor]):
        raise HTTPException(403, 'You cannot administer an account at this privilege level.')
    if target_id is not None and str(target_id) == str(ctx['user']['_id']):
        raise HTTPException(403, 'Use your profile/password endpoint to change your own account.')


def safe_user(user, employee=None):
    fields = ('_id', 'employee_id', 'username', 'email', 'full_name', 'role', 'status', 'require_password_change', 'created_at', 'updated_at', 'last_login_at')
    data = {k: user[k] for k in fields if k in user}
    data['id'] = str(user['_id'])
    data['active'] = is_active(user.get('status'))
    if employee:
        data['full_name'] = name(employee)
        data['department'] = employee.get('department', '')
    return serialize_id(data)


async def target(ctx, user_id):
    user = await ctx['db']['users'].find_one(id_filter(user_id))
    if not user:
        raise HTTPException(404, 'User not found.')
    return user


@router.get('/roles')
async def roles(ctx: dict = Depends(require_session)):
    require_roles(ctx, HR)
    return {'success': True, 'roles': [r for r in ROLES if RANK[r] < RANK[role(ctx)]]}


@router.get('/users')
async def list_users(include_inactive: bool = False, ctx: dict = Depends(require_session)):
    require_roles(ctx, HR)
    rows = await ctx['db']['users'].find({}).to_list(None)
    result = []
    for user in rows:
        if not include_inactive and not is_active(user.get('status')):
            continue
        try:
            employee = await employee_by_reference(ctx['db'], user.get('employee_id'))
        except HTTPException:
            employee = None
        result.append(safe_user(user, employee))
    return {'success': True, 'users': result}


class NewUser(BaseModel):
    model_config = ConfigDict(extra='forbid')
    employee_id: str | int
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=1024)
    role: str = 'Staff'
    active: bool = True
    status: str | None = None
    require_password_change: bool = True


@router.post('/users')
async def create_user(body: NewUser, ctx: dict = Depends(require_session)):
    can_change(ctx, body.role)
    if body.role not in ROLES:
        raise HTTPException(422, 'Use a canonical role name.')
    db = ctx['db']
    employee = await employee_by_reference(db, body.employee_id)
    username = normalise_login(body.username)
    if not username:
        raise HTTPException(422, 'Username is required.')
    import re
    existing = await db['users'].find_one({'$or': [
        {'employee_id': {'$in': refs(employee)}},
        {'username': {'$regex': '^' + re.escape(username) + '$', '$options': 'i'}},
        {'email': {'$regex': '^' + re.escape(employee.get('email') or employee.get('email_address') or username) + '$', '$options': 'i'}},
    ]})
    if existing:
        raise HTTPException(409, 'This employee or username already has an account. Update the existing account.')
    hashed = await run_in_threadpool(hash_pbkdf2_sha256, body.password)
    doc = {'employee_id': employee['_id'], 'nexus_employee_id': str(employee['_id']), 'username': username, 'username_normalized': username,
        'email': employee.get('email') or employee.get('email_address') or username, 'full_name': name(employee), 'role': body.role,
        'status': 'active' if body.active and body.status not in {'inactive', 'disabled'} else 'inactive',
        'password_hash': hashed, 'require_password_change': body.require_password_change,
        'created_at': now(), 'updated_at': now(), 'history': [audit(ctx, 'create-account')]}
    try:
        result = await db['users'].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, 'This employee or username already has an account.')
    doc['_id'] = result.inserted_id
    return {'success': True, 'user': safe_user(doc, employee)}


@router.get('/users/{user_id}')
async def get_user(user_id: str, ctx: dict = Depends(require_session)):
    require_roles(ctx, HR)
    return {'success': True, 'user': safe_user(await target(ctx, user_id))}


@router.patch('/users/{user_id}')
@router.put('/users/{user_id}')
async def update_user(user_id: str, body: dict = Body(...), ctx: dict = Depends(require_session)):
    user = await target(ctx, user_id)
    can_change(ctx, user.get('role'), user['_id'])
    if set(body) - {'role', 'active', 'status', 'username', 'email', 'full_name'}:
        raise HTTPException(422, 'Unsupported account update fields.')
    updates = {}
    if 'role' in body:
        if body['role'] not in ROLES:
            raise HTTPException(422, 'Use a canonical role name.')
        can_change(ctx, body['role'])
        updates['role'] = body['role']
    if 'active' in body:
        if not isinstance(body['active'], bool):
            raise HTTPException(422, 'active must be boolean.')
        updates['status'] = 'active' if body['active'] else 'inactive'
    if 'status' in body:
        if body['status'] not in {'active', 'inactive', 'disabled', 'suspended'}:
            raise HTTPException(422, 'Invalid account status.')
        updates['status'] = body['status']
    for key in ('username', 'email', 'full_name'):
        if key in body:
            if not isinstance(body[key], str) or not body[key].strip() or len(body[key]) > 200:
                raise HTTPException(422, f'Invalid {key}.')
            updates[key] = body[key].strip()
    if 'username' in updates:
        import re
        updates['username'] = normalise_login(updates['username'])
        updates['username_normalized'] = updates['username']
        duplicate = await ctx['db']['users'].find_one({'_id': {'$ne': user['_id']}, 'username': {'$regex': '^'+re.escape(updates['username'])+'$', '$options': 'i'}})
        if duplicate:
            raise HTTPException(409, 'Username already exists.')
    try:
        await ctx['db']['users'].update_one({'_id': user['_id']}, {'$set': {**updates, 'updated_at': now()}, '$push': {'history': audit(ctx, 'update-account')}})
    except DuplicateKeyError:
        raise HTTPException(409, 'Username already exists.')
    if 'role' in updates or 'status' in updates:
        await ctx['db']['api_sessions'].update_many({'user_id': user['_id']}, {'$set': {'status': 'revoked'}})
    return {'success': True, 'user': safe_user(await target(ctx, user_id))}


class ResetPassword(BaseModel):
    password: str = Field(min_length=8, max_length=1024)


@router.post('/users/{user_id}/reset-password')
async def reset_password(user_id: str, body: ResetPassword, ctx: dict = Depends(require_session)):
    user = await target(ctx, user_id)
    can_change(ctx, user.get('role'), user['_id'])
    hashed = await run_in_threadpool(hash_pbkdf2_sha256, body.password)
    await ctx['db']['users'].update_one({'_id': user['_id']}, {'$set': {'password_hash': hashed, 'require_password_change': True, 'updated_at': now()}, '$unset': {'password': '', 'hashed_password': ''}, '$push': {'history': audit(ctx, 'reset-password')}})
    await ctx['db']['api_sessions'].update_many({'user_id': user['_id']}, {'$set': {'status': 'revoked'}})
    return {'success': True}


@router.delete('/users/{user_id}')
async def delete_user(user_id: str, ctx: dict = Depends(require_session)):
    user = await target(ctx, user_id)
    can_change(ctx, user.get('role'), user['_id'])
    await ctx['db']['users'].update_one({'_id': user['_id']}, {'$set': {'status': 'inactive', 'archived': True, 'updated_at': now()}, '$push': {'history': audit(ctx, 'archive-account')}})
    await ctx['db']['api_sessions'].update_many({'user_id': user['_id']}, {'$set': {'status': 'revoked'}})
    return {'success': True, 'message': 'Account disabled; employee and audit records retained.'}
