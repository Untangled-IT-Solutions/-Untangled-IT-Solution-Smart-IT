import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Body, HTTPException, Query
from fastapi import Request
from fastapi.responses import StreamingResponse
from app.security import require_session, serialize_id
from app.domain import PEOPLE_OVERSIGHT, role, require_roles, refs, id_filter, employee_by_reference, notify, notify_roles, now
import uuid
from app.notification_events import subscribe

router = APIRouter(prefix='/api/notifications', tags=['notifications'])


def recipient(ctx):
    return {'$or': [{'employee_id': {'$in': refs(ctx['employee'])}}, {'user_id': {'$in': [ctx['user']['_id'], str(ctx['user']['_id'])]}}]}


@router.get('')
async def list_notifications(
    unread: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    before: datetime | None = None,
    ctx: dict = Depends(require_session),
):
    query = recipient(ctx)
    if unread:
        query['read'] = {'$ne': True}
    if before is not None:
        query['created_at'] = {'$lt': before}
    rows = await ctx['db']['notifications'].find(query).sort('created_at', -1).limit(limit + 1).to_list(limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    if rows:
        ids = [row['_id'] for row in rows]
        await ctx['db']['notifications'].update_many(
            {'_id': {'$in': ids}, 'delivered_at': {'$exists': False}},
            {'$set': {'delivery_status': 'delivered', 'delivered_at': now()}},
        )
        for row in rows:
            row.setdefault('delivery_status', 'delivered')
    serialized = serialize_id(rows)
    next_before = rows[-1].get('created_at').isoformat() if has_more and rows and isinstance(rows[-1].get('created_at'), datetime) else None
    return {
        'success': True,
        'notifications': serialized,
        'items': serialized,
        'has_more': has_more,
        'next_before': next_before,
    }


@router.get('/unread-count')
async def unread_count(ctx: dict = Depends(require_session)):
    count = await ctx['db']['notifications'].count_documents({**recipient(ctx), 'read': {'$ne': True}})
    return {'success': True, 'count': count, 'unread': count}


@router.get('/stream')
async def notification_stream(request: Request, ctx: dict = Depends(require_session)):
    recipient_keys = {str(value) for value in refs(ctx['employee'])}

    async def events():
        async with subscribe(recipient_keys) as queue:
            yield 'retry: 5000\nevent: ready\ndata: {"connected":true}\n\n'
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield 'event: notification\ndata: ' + json.dumps(event, default=str) + '\n\n'
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'

    return StreamingResponse(
        events(),
        media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@router.post('/read-all')
@router.post('/mark-all-read')
async def mark_all(ctx: dict = Depends(require_session)):
    read_at = now()
    result = await ctx['db']['notifications'].update_many(
        {**recipient(ctx), 'read': {'$ne': True}},
        {'$set': {'read': True, 'is_read': True, 'delivery_status': 'read', 'read_at': read_at}},
    )
    return {'success': True, 'count': result.modified_count, 'matched': result.matched_count}


@router.post('/{notification_id}/read')
async def mark_read(notification_id: str, ctx: dict = Depends(require_session)):
    read_at = now()
    result = await ctx['db']['notifications'].update_one(
        {**id_filter(notification_id), **recipient(ctx)},
        {'$set': {'read': True, 'is_read': True, 'delivery_status': 'read', 'read_at': read_at}},
    )
    if not result.matched_count:
        raise HTTPException(404, 'Notification not found.')
    return {'success': True, 'matched': result.matched_count, 'modified': result.modified_count, 'read_at': read_at}


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
