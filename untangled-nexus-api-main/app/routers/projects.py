from fastapi import APIRouter, Depends, HTTPException
from app.security import require_session, serialize_id
from app.domain import TASK_OVERSIGHT, BUSINESS_WORK, role, refs, id_filter
router = APIRouter(prefix='/api/projects', tags=['projects'])


def scope(ctx):
    if role(ctx) in TASK_OVERSIGHT:
        return {}
    values = refs(ctx['employee'])
    clauses = [{'member_ids': {'$in': values}}, {'employee_id': {'$in': values}}, {'owner_id': {'$in': values}}]
    if role(ctx) in BUSINESS_WORK and ctx['employee'].get('department'):
        clauses.append({'department': ctx['employee']['department']})
    return {'$or': clauses}


@router.get('')
async def list_projects(ctx: dict = Depends(require_session)):
    rows = await ctx['db']['projects'].find(scope(ctx)).to_list(None)
    return {'success': True, 'projects': serialize_id(rows)}


@router.get('/{project_id}')
async def get_project(project_id: str, ctx: dict = Depends(require_session)):
    row = await ctx['db']['projects'].find_one({'$and': [id_filter(project_id), scope(ctx)]})
    if not row:
        raise HTTPException(404, 'Project not found.')
    return {'success': True, 'project': serialize_id(row)}
