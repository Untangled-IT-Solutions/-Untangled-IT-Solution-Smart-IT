from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from app.security import require_session, serialize_id
from app.domain import HR, role, refs, own, date_string, id_filter
from app.routers.approvals import create_record, decide
from app.routers.documents import load_document

router = APIRouter(prefix='/api/leave', tags=['leave'])


class LeaveCreate(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=20000)
    document_ids: list[str] = Field(default_factory=list, max_length=10)
    requires_director: bool = False


@router.post('')
async def submit(body: LeaveCreate, ctx: dict = Depends(require_session)):
    if body.leave_type not in {'Annual', 'Sick', 'Family Responsibility', 'Unpaid', 'Other'}:
        raise HTTPException(422, 'Invalid leave type.')
    if body.end_date < body.start_date or (body.end_date - body.start_date).days > 366:
        raise HTTPException(422, 'Invalid leave date range.')
    if body.leave_type == 'Sick' and not body.document_ids:
        raise HTTPException(422, 'A supporting document is required for sick leave.')
    if len(set(body.document_ids)) != len(body.document_ids):
        raise HTTPException(422, 'Supporting documents must be unique.')
    for document_id in body.document_ids:
        document = await load_document(ctx, document_id)
        if not own(ctx, document['employee_id']) or document.get('task_id'):
            raise HTTPException(422, 'Use your own supporting document, not a task attachment.')
        if body.leave_type == 'Sick':
            doc_type = str(document.get('document_type') or '').strip().lower().replace("'", '')
            medical_types = {'doctor note', 'doctors note', 'medical certificate', 'sick note'}
            medical_mimes = {'application/pdf', 'image/png', 'image/jpeg', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
            if doc_type not in medical_types or document.get('mime') not in medical_mimes:
                raise HTTPException(422, 'Sick leave requires a valid doctor note or medical certificate.')
    overlap = await ctx['db']['approvals'].find_one({'request_type': 'Leave', 'employee_id': {'$in': refs(ctx['employee'])}, 'status': {'$in': ['Pending', 'Approved']}, 'start_date': {'$lte': body.end_date.isoformat()}, 'end_date': {'$gte': body.start_date.isoformat()}})
    if overlap:
        raise HTTPException(409, 'An overlapping leave request already exists.')
    values = body.model_dump(mode='json')
    values.update(request_type='Leave', title=f'{body.leave_type} leave: {body.start_date} to {body.end_date}', description=body.reason, amount=0)
    record = await create_record(ctx, values)
    return {'success': True, 'leave': serialize_id(record)}


@router.get('')
async def list_leave(ctx: dict = Depends(require_session)):
    query = {'request_type': 'Leave'}
    if role(ctx) not in HR:
        query['$or'] = [{'employee_id': {'$in': refs(ctx['employee'])}}, {'current_stage': 'Business'}] if role(ctx) == 'Business Lead' else [{'employee_id': {'$in': refs(ctx['employee'])}}]
    rows = await ctx['db']['approvals'].find(query).sort('created_at', -1).to_list(None)
    return {'success': True, 'leave': serialize_id(rows), 'items': serialize_id(rows)}


@router.get('/{leave_id}')
async def get_leave(leave_id: str, ctx: dict = Depends(require_session)):
    record = await ctx['db']['approvals'].find_one({**id_filter(leave_id), 'request_type': 'Leave'})
    if not record:
        raise HTTPException(404, 'Leave request not found.')
    if role(ctx) not in HR and not own(ctx, record['employee_id']) and not (role(ctx) == 'Business Lead' and record.get('current_stage') == 'Business'):
        raise HTTPException(403, 'You can only access your own leave.')
    return {'success': True, 'leave': serialize_id(record)}


@router.post('/{leave_id}/approve')
async def approve_leave(leave_id: str, body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    await get_leave(leave_id, ctx)
    return {'success': True, 'leave': serialize_id(await decide(ctx, leave_id, True, body))}


@router.post('/{leave_id}/reject')
async def reject_leave(leave_id: str, body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    await get_leave(leave_id, ctx)
    return {'success': True, 'leave': serialize_id(await decide(ctx, leave_id, False, body))}
