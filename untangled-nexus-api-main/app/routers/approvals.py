from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.security import require_session, serialize_id
from app.domain import PEOPLE_OVERSIGHT, BUSINESS_WORK, OPERATIONS, role, require_roles, refs, own, now, name, id_filter, change, audit, notify, notify_roles

router = APIRouter(tags=['approvals'])
STAGE_ROLES = {'Manager': OPERATIONS, 'Business': {'Business Lead', 'Branch Manager', 'Super Admin'}, 'Director': {'Director', 'Super Admin'}}


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    title: str = Field(min_length=1, max_length=300)
    request_type: str = 'General'
    description: str = Field(default='', max_length=20000)
    requested_by: str = ''  # legacy input; authenticated identity is authoritative
    department: str = ''
    amount: float = Field(default=0, ge=0)
    requires_director: bool = False


    @field_validator("amount", mode="before")
    @classmethod
    def blank_amount(cls, value):
        return 0 if value == "" else value


async def create_record(ctx, values):
    doc = {**values, 'employee_id': ctx['employee']['_id'], 'requested_by': name(ctx['employee']),
        'department': ctx['employee'].get('department', ''), 'status': 'Pending', 'current_stage': 'Manager',
        'revision': 0, 'submitted_at': now(), 'created_at': now(), 'updated_at': now(), 'history': [audit(ctx, 'submit')]}
    result = await ctx['db']['approvals'].insert_one(doc)
    doc['_id'] = result.inserted_id
    await notify_roles(ctx['db'], f"approval:{doc['_id']}:new", OPERATIONS, 'Approval requested', doc['title'], 'Approval', doc['_id'])
    return doc


@router.get('/api/approvals')
async def list_approvals(status: str | None = None, ctx: dict = Depends(require_session)):
    if role(ctx) in PEOPLE_OVERSIGHT:
        query = {}
    elif role(ctx) in BUSINESS_WORK:
        query = {'$or': [
            {'employee_id': {'$in': refs(ctx['employee'])}},
            {'current_stage': 'Business'},
        ]}
    else:
        query = {'employee_id': {'$in': refs(ctx['employee'])}}
    if status and status.lower() != 'all':
        query['status'] = status.capitalize()
    rows = await ctx['db']['approvals'].find(query).sort('created_at', -1).to_list(None)
    return {'success': True, 'approvals': serialize_id(rows), 'items': serialize_id(rows)}


@router.post('/api/approvals')
async def create_approval(body: ApprovalCreate, ctx: dict = Depends(require_session)):
    if body.request_type == 'Leave':
        raise HTTPException(422, 'Submit dated leave through /api/leave with supporting document IDs.')
    return {'success': True, 'approval': serialize_id(await create_record(ctx, body.model_dump()))}


async def decide(ctx, approval_id, approve, body):
    record = await ctx['db']['approvals'].find_one(id_filter(approval_id))
    if not record:
        raise HTTPException(404, 'Approval not found.')
    stage = record.get('current_stage') or 'Manager'
    require_roles(ctx, STAGE_ROLES.get(stage, set()))
    if own(ctx, record.get('employee_id')):
        raise HTTPException(403, 'You cannot approve your own request.')
    if record.get('status', '').lower() != 'pending':
        raise HTTPException(409, 'Request has already been decided.')
    reason = body.get('reason') or body.get('note') or ''
    if not isinstance(reason, str) or len(reason) > 20000:
        raise HTTPException(422, 'Invalid review note.')
    if not approve and not reason.strip():
        raise HTTPException(422, 'A rejection reason is required.')
    updates = {}
    if approve:
        updates[{'Manager': 'manager_approved_by', 'Business': 'business_approved_by', 'Director': 'director_approved_by'}[stage]] = name(ctx['employee'])
        next_stage = 'Business' if stage == 'Manager' else 'Director' if stage == 'Business' and record.get('requires_director') else 'Complete'
        updates.update(current_stage=next_stage, status='Approved' if next_stage == 'Complete' else 'Pending')
    else:
        updates.update(status='Rejected', rejection_reason=reason)
    result = await change(ctx['db']['approvals'], record, updates, audit(ctx, 'approve' if approve else 'reject', reason))
    key = f"approval:{record['_id']}:{result['revision']}"
    await notify(ctx['db'], key, record.get('employee_id'), 'Approval updated', f"{record['title']}: {result['status']}", 'Approval', record['_id'])
    if result['status'] == 'Pending':
        await notify_roles(ctx['db'], key, STAGE_ROLES[result['current_stage']], 'Approval requires review', record['title'], 'Approval', record['_id'])
    return result


@router.post('/api/approvals/{approval_id}/approve')
async def approve(approval_id: str, body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    return {'success': True, 'approval': serialize_id(await decide(ctx, approval_id, True, body))}


@router.post('/api/approvals/{approval_id}/reject')
async def reject(approval_id: str, body: dict = Body(default={}), ctx: dict = Depends(require_session)):
    return {'success': True, 'approval': serialize_id(await decide(ctx, approval_id, False, body))}
