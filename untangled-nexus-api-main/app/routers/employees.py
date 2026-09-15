from fastapi import APIRouter, Depends, HTTPException
from app.security import require_session
from app.domain import PEOPLE_OVERSIGHT, BUSINESS_WORK, role, own, public_employee, employee_by_reference, refs

router = APIRouter(tags=['employees'])


@router.get('/api/employees')
@router.get('/api/admin/employees')
async def list_employees(ctx: dict = Depends(require_session)):
    current_role = role(ctx)
    if current_role in PEOPLE_OVERSIGHT:
        query = {}
    elif current_role in BUSINESS_WORK and ctx['employee'].get('department'):
        query = {'department': ctx['employee']['department']}
    else:
        query = {'_id': ctx['employee']['_id']}
    rows = await ctx['db']['employees'].find(query).sort('full_name', 1).to_list(None)
    items = []
    for employee in rows:
        item = public_employee(employee)
        if current_role in PEOPLE_OVERSIGHT:
            user = await ctx['db']['users'].find_one({'employee_id': {'$in': refs(employee)}}, {'_id': 1, 'last_login_at': 1})
            item.update(has_account=bool(user), user_id=str(user['_id']) if user else None, last_login_at=str(user.get('last_login_at') or '') if user else '')
        items.append(item)
    return {'success': True, 'employees': items, 'items': items, 'count': len(items)}


@router.get('/api/employees/{employee_id}')
@router.get('/api/admin/employees/{employee_id}')
async def get_employee(employee_id: str, ctx: dict = Depends(require_session)):
    employee = await employee_by_reference(ctx['db'], employee_id)
    same_team = (
        role(ctx) in BUSINESS_WORK
        and ctx['employee'].get('department')
        and employee.get('department') == ctx['employee'].get('department')
    )
    if role(ctx) not in PEOPLE_OVERSIGHT and not same_team and not own(ctx, employee['_id']):
        raise HTTPException(403, 'You can only access your own employee details.')
    return {'success': True, 'employee': public_employee(employee)}
