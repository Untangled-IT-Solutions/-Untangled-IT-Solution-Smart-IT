from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from app.security import require_session, serialize_id
from app.domain import PEOPLE_OVERSIGHT, OPERATIONS, role, require_roles, refs, own, now, name, id_filter, change, audit, notify, notify_roles

router = APIRouter(prefix='/api/office-requests', tags=['office-requests'])
ITEMS = ['Stationery', 'Toner / Ink', 'Keyboard', 'Mouse', 'Monitor', 'Headset', 'Other']


@router.get('/items')
async def items(ctx: dict = Depends(require_session)):
    return {'success': True, 'items': ITEMS}


@router.get('')
async def list_requests(ctx: dict = Depends(require_session)):
    query = {} if role(ctx) in PEOPLE_OVERSIGHT else {'employee_id': {'$in': refs(ctx['employee'])}}
    rows = await ctx['db']['office_requests'].find(query).sort('created_at', -1).to_list(None)
    return {'success': True, 'requests': serialize_id(rows)}


class OfficeRequest(BaseModel):
    item: str = ''
    item_name: str = ''
    quantity: int = Field(ge=1, le=10000)
    requested_by: str = ''
    department: str = ''
    notes: str = Field(default='', max_length=20000)
    requires_director: bool = False


@router.post('')
async def create_request(body: OfficeRequest, ctx: dict = Depends(require_session)):
    item = (body.item_name or body.item).strip()
    if not item or len(item) > 300:
        raise HTTPException(422, 'Item is required.')
    doc = {**body.model_dump(), 'item_name': item, 'employee_id': ctx['employee']['_id'], 'requested_by': name(ctx['employee']),
        'department': ctx['employee'].get('department', ''), 'status': 'Pending', 'approval_status': 'Pending', 'current_stage': 'Manager',
        'revision': 0, 'created_at': now(), 'history': [audit(ctx, 'office-request')]}
    result = await ctx['db']['office_requests'].insert_one(doc)
    doc['_id'] = result.inserted_id
    await notify_roles(ctx['db'], f"office:{doc['_id']}:new", OPERATIONS, 'Office request', item, 'Office Request', doc['_id'])
    return {'success': True, 'request': serialize_id(doc)}


@router.patch('/{request_id}')
async def review(request_id: str, body: dict = Body(...), ctx: dict = Depends(require_session)):
    row = await ctx['db']['office_requests'].find_one(id_filter(request_id))
    if not row:
        raise HTTPException(404, 'Office request not found.')
    require_roles(ctx, {'Director', 'Super Admin'} if row.get('current_stage') == 'Director' else OPERATIONS)
    if own(ctx, row.get('employee_id')):
        raise HTTPException(403, 'You cannot review your own request.')
    if row.get('status') != 'Pending':
        raise HTTPException(409, 'Request already decided.')
    status = body.get('status')
    if status not in {'Approved', 'Rejected'}:
        raise HTTPException(422, 'Status must be Approved or Rejected.')
    note = body.get('reason') or body.get('note') or ''
    if not isinstance(note, str) or (status == 'Rejected' and not note.strip()):
        raise HTTPException(422, 'A rejection reason is required.')
    stage = 'Complete'
    if status == 'Approved' and row.get('requires_director') and row.get('current_stage') != 'Director':
        status, stage = 'Pending', 'Director'
    result = await change(ctx['db']['office_requests'], row, {'status': status, 'approval_status': status, 'current_stage': stage, 'review_note': note}, audit(ctx, 'review-office-request', note))
    await notify(ctx['db'], f"office:{row['_id']}:{result['revision']}", row['employee_id'], 'Office request updated', status, 'Office Request', row['_id'])
    if stage == 'Director':
        await notify_roles(ctx['db'], f"office:{row['_id']}:director", {'Director'}, 'Office request approval', row['item_name'], 'Office Request', row['_id'])
    return {'success': True, 'request': serialize_id(result)}
