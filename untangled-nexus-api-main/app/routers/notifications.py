from fastapi import APIRouter, Depends, Body, HTTPException
from app.security import require_session, serialize_id
from app.domain import PEOPLE_OVERSIGHT, role, require_roles, refs, id_filter, employee_by_reference, notify, notify_roles, now
import uuid

router = APIRouter(prefix='/api/notifications', tags=['notifications'])


def recipient(ctx):
    return {'$or': [{'employee_id': {'$in': refs(ctx['employee'])}}, {'user_id': {'$in': [ctx['user']['_id'], str(ctx['user']['_id'])]}}]}


@router.get('')
async def list_notifications(unread: bool = False, ctx: dict = Depends(require_session)):
    query = recipient(ctx)
    if unread:
        query['read'] = {'$ne': True}
    rows = await ctx['db']['notifications'].find(query).sort('created_at', -1).limit(200).to_list(200)
    return {'success': True, 'notifications': serialize_id(rows), 'items': serialize_id(rows)}


@router.get('/unread-count')
async def unread_count(ctx: dict = Depends(require_session)):
    count = await ctx['db']['notifications'].count_documents({**recipient(ctx), 'read': {'$ne': True}})
    return {'success': True, 'count': count, 'unread': count}


@router.post('/read-all')
@router.post('/mark-all-read')
async def mark_all(ctx: dict = Depends(require_session)):
    result = await ctx['db']['notifications'].update_many({**recipient(ctx), 'read': {'$ne': True}}, {'$set': {'read': True, 'is_read': True, 'read_at': now()}})
    return {'success': True, 'count': result.modified_count, 'matched': result.matched_count}


@router.post('/{notification_id}/read')
async def mark_read(notification_id: str, ctx: dict = Depends(require_session)):
    result = await ctx['db']['notifications'].update_one({**id_filter(notification_id), **recipient(ctx)}, {'$set': {'read': True, 'is_read': True, 'read_at': now()}})
    if not result.matched_count:
        raise HTTPException(404, 'Notification not found.')
    return {'success': True, 'matched': result.matched_count, 'modified': result.modified_count}


@router.post('')
async def create_notification(body: dict = Body(...), ctx: dict = Depends(require_session)):
    require_roles(ctx, PEOPLE_OVERSIGHT)
    title = body.get('title') or 'Notification'
    message = body.get('message') or ''
    if not isinstance(title, str) or not isinstance(message, str) or len(title) > 300 or len(message) > 20000:
        raise HTTPException(422, 'Invalid notification content.')
    # Server workflow notifications use deterministic event keys. Manual messages are distinct.
    key = 'manual:' + uuid.uuid4().hex
    if body.get('recipient_role'):
        recipient_role = body['recipient_role']
        from app.domain import ROLES
        if recipient_role not in ROLES:
            raise HTTPException(422, 'Invalid recipient role.')
        await notify_roles(ctx['db'], key, {recipient_role}, title, message, body.get('reference_type') or '', body.get('reference_id') or '')
    else:
        target = body.get('employee_id') or body.get('user_name') or body.get('username') or body.get('recipient_username')
        employee = await employee_by_reference(ctx['db'], target)
        await notify(ctx['db'], key, employee['_id'], title, message, body.get('reference_type') or '', body.get('reference_id') or '')
    return {'success': True}
