import csv
import io
from xml.sax.saxutils import escape
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from app.security import require_session, serialize_id
from app.domain import MANAGEMENT, BUSINESS_WORK, role, refs, require_roles
from app.routers.documents import store

router = APIRouter(prefix='/api/reports', tags=['reports'])
REPORTS = {
 'Attendance Summary': ('attendance', ('employee_name', 'work_date', 'clock_in_at', 'clock_out_at', 'break_duration_minutes', 'status')),
 'Task Workload': ('work_assignments', ('title', 'assigned_employee', 'status', 'priority', 'estimated_hours', 'actual_hours', 'due_date')),
 'Quote Pipeline': ('quotes', ('reference', 'customerName', 'status', 'createdAt')),
 'Order Status': ('orders', ('reference', 'customerName', 'status', 'total', 'createdAt')),
 'Approvals Overview': ('approvals', ('title', 'requested_by', 'request_type', 'status', 'current_stage', 'submitted_at')),
}


async def rows_for(ctx, report_type):
    require_roles(ctx, MANAGEMENT)
    if report_type not in REPORTS:
        raise HTTPException(422, 'Unknown report type.')
    if role(ctx) in BUSINESS_WORK and report_type == 'Attendance Summary':
        raise HTTPException(403, 'Attendance reports require people-oversight permission.')
    collection, fields = REPORTS[report_type]
    query = {}
    if role(ctx) in BUSINESS_WORK:
        if collection == 'work_assignments':
            from app.routers.tasks import visibility_filter
            query = visibility_filter(ctx)
        elif collection == 'approvals':
            query = {'$or': [
                {'employee_id': {'$in': refs(ctx['employee'])}},
                {'current_stage': 'Business'},
            ]}
    rows = await ctx['db'][collection].find(query, {k: 1 for k in fields}).limit(10001).to_list(10001)
    if len(rows) > 10000:
        raise HTTPException(422, 'Report exceeds 10,000 records; a date-filtered export is required.')
    return [{k: serialize_id(row).get(k, '') for k in fields} for row in rows]


@router.get('/types')
async def types(ctx: dict = Depends(require_session)):
    require_roles(ctx, MANAGEMENT)
    available = [item for item in REPORTS if not (role(ctx) in BUSINESS_WORK and item == 'Attendance Summary')]
    return {'success': True, 'types': available}


@router.get('/preview')
async def preview(type: str, ctx: dict = Depends(require_session)):
    return {'success': True, 'rows': await rows_for(ctx, type)}


def render(rows, fields, kind):
    def safe(value):
        value = str(value)
        return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    # Values are data, never formulas or report markup.
    if kind == 'CSV':
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows([[safe(row[k]) for k in fields] for row in rows])
        return stream.getvalue().encode('utf-8-sig'), '.csv'
    if kind == 'Excel':
        from openpyxl import Workbook
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'Report'
        sheet.append(list(fields))
        for row in rows:
            sheet.append([safe(row[k]) for k in fields])
        stream = io.BytesIO()
        workbook.save(stream)
        return stream.getvalue(), '.xlsx'
    if kind == 'PDF':
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.pagesizes import A4, landscape
        stream = io.BytesIO()
        style = getSampleStyleSheet()['BodyText']
        style.fontSize = 7
        style.leading = 9
        data = [[Paragraph(escape(str(k)), style) for k in fields]]
        data += [[Paragraph(escape(str(row[k])), style) for k in fields] for row in rows]
        table = Table(data, repeatRows=1, colWidths=[770/len(fields)]*len(fields))
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.25,colors.grey)]))
        SimpleDocTemplate(stream, pagesize=landscape(A4), leftMargin=30, rightMargin=30).build([table])
        return stream.getvalue(), '.pdf'
    raise HTTPException(422, 'Supported formats: PDF, Excel, CSV.')


class Export(BaseModel):
    type: str
    format: str


@router.post('/export')
async def export(body: Export, ctx: dict = Depends(require_session)):
    rows = await rows_for(ctx, body.type)
    content, extension = await run_in_threadpool(render, rows, REPORTS[body.type][1], body.format)
    doc = await store(ctx, body.type.replace(' ', '-') + extension, content, 'Report', ctx['employee'])
    return {'success': True, 'document': doc, 'url': f"/api/documents/{doc['id']}/download", 'message': 'Report generated. Download requires your bearer session.'}
