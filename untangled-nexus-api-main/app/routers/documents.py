"""Private, bounded document storage in MongoDB; no public file URLs."""
import base64
import hashlib
import io
from pathlib import PurePosixPath
from urllib.parse import quote
import zipfile
from datetime import date, datetime, timedelta

from bson import Binary
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Response, Body
from app.config import get_settings
from app.security import require_session, serialize_id
from app.domain import HR, role, own, refs, id_filter, employee_by_reference, now, date_string, audit, require_roles, notify, notify_roles

router = APIRouter(prefix='/api/documents', tags=['documents'])


def expiry_details(value, today=None):
    """Classify an expiry date using the Johannesburg calendar date."""
    from app.security import today_south_africa
    today = today or date.fromisoformat(today_south_africa())
    if not value:
        return {'status': 'no_expiry', 'expiry_window': 'none', 'days_until_expiry': None}
    try:
        if isinstance(value, datetime):
            expiry = value.date()
        elif isinstance(value, date):
            expiry = value
        else:
            expiry = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return {'status': 'invalid', 'expiry_window': 'invalid', 'days_until_expiry': None}
    days = (expiry - today).days
    if days < 0:
        status, window = 'expired', 'expired'
    elif days <= 7:
        status, window = 'expiring', 'within_7_days'
    elif days <= 30:
        status, window = 'expiring', 'within_30_days'
    else:
        status, window = 'valid', 'later'
    return {'status': status, 'expiry_window': window, 'days_until_expiry': days}


async def scan_document_expiry(db, query=None):
    """Persist current expiry state and create idempotent Nexus notifications."""
    query = {'expiry_date': {'$nin': [None, '']}, **(query or {})}
    rows = await db['documents'].find(query).to_list(None)
    counts = {'expired': 0, 'within_7_days': 0, 'within_30_days': 0, 'valid': 0, 'invalid': 0}
    notifications_created = 0
    checked_at = now()
    for doc in rows:
        details = expiry_details(doc.get('expiry_date'))
        bucket = details['expiry_window']
        counts[bucket if bucket in counts else details['status']] += 1
        await db['documents'].update_one(
            {'_id': doc['_id']},
            {'$set': {
                'expiry_status': details['status'],
                'expiry_window': details['expiry_window'],
                'days_until_expiry': details['days_until_expiry'],
                'expiry_checked_at': checked_at,
            }},
        )
        if bucket not in {'expired', 'within_7_days', 'within_30_days'}:
            continue
        expiry = str(doc.get('expiry_date'))[:10]
        key = f"document-expiry:{doc['_id']}:{expiry}:{bucket}"
        days = details['days_until_expiry']
        if bucket == 'expired':
            timing = f"expired {abs(days)} day(s) ago"
        elif days == 0:
            timing = 'expires today'
        else:
            timing = f"expires in {days} day(s)"
        doc_name = doc.get('name') or doc.get('document_type') or 'Document'
        notifications_created += int(await notify(
            db, key + ':owner', doc.get('employee_id'), 'Document expiry alert',
            f"{doc_name} {timing}.", 'Document', doc['_id'],
        ))
        notifications_created += await notify_roles(
            db, key + ':management', HR, 'Employee document expiry',
            f"{doc_name} {timing}.", 'Document', doc['_id'],
        )
    return {
        'scanned': len(rows),
        'notifications_created': notifications_created,
        **counts,
    }


async def document_expiry_summary(db, query=None):
    query = {'expiry_date': {'$nin': [None, '']}, **(query or {})}
    rows = await db['documents'].find(query, {'expiry_date': 1}).to_list(None)
    counts = {'expired': 0, 'within_7_days': 0, 'within_30_days': 0, 'valid': 0, 'invalid': 0}
    for doc in rows:
        details = expiry_details(doc.get('expiry_date'))
        bucket = details['expiry_window']
        counts[bucket if bucket in counts else details['status']] += 1
    return {'total': len(rows), **counts}


def validate_file(filename, content):
    filename = str(filename or '').replace('\\', '/').split('/')[-1]
    if not filename or len(filename) > 200 or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, 'Invalid filename.')
    if not content or len(content) > get_settings().max_document_bytes:
        raise HTTPException(413, 'Document is empty or exceeds the upload limit.')
    ext = PurePosixPath(filename).suffix.lower()
    mime = None
    if ext == '.pdf' and content.startswith(b'%PDF-'):
        mime = 'application/pdf'
    elif ext == '.png' and content.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif ext in {'.jpg', '.jpeg'} and content.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif ext in {'.txt', '.csv'}:
        try:
            text = content.decode('utf-8-sig')
            if '\x00' in text:
                raise ValueError()
            mime = 'text/plain' if ext == '.txt' else 'text/csv'
        except (UnicodeError, ValueError):
            pass
    elif ext in {'.docx', '.xlsx'}:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                expected = 'word/document.xml' if ext == '.docx' else 'xl/workbook.xml'
                if '[Content_Types].xml' in names and expected in names and not any('vbaproject' in n.lower() for n in names) and sum(i.file_size for i in archive.infolist()) <= 50 * 1024 * 1024:
                    mime = 'application/vnd.openxmlformats-officedocument.' + ('wordprocessingml.document' if ext == '.docx' else 'spreadsheetml.sheet')
        except zipfile.BadZipFile:
            pass
    if not mime:
        raise HTTPException(415, 'Supported files: valid PDF, PNG, JPEG, UTF-8 TXT/CSV, DOCX or XLSX without macros.')
    return filename, mime


def metadata(doc):
    data = {k: v for k, v in doc.items() if k not in {'content', 'history'}}
    data['id'] = str(doc['_id'])
    details = expiry_details(doc.get('expiry_date'))
    data.update(details)
    return serialize_id(data)


async def load_document(ctx, document_id):
    doc = await ctx['db']['documents'].find_one(id_filter(document_id))
    if not doc:
        raise HTTPException(404, 'Document not found.')
    allowed = own(ctx, doc.get('employee_id')) or role(ctx) in HR
    if not allowed and role(ctx) == 'Business Lead':
        linked_leave = await ctx['db']['approvals'].find_one({
            'request_type': 'Leave',
            'document_ids': str(doc['_id']),
            'status': 'Pending',
            'current_stage': 'Business',
        })
        allowed = linked_leave is not None
    if not allowed and doc.get('task_id') and doc.get('document_type') == 'Task Attachment':
        from app.routers.tasks import load_task
        await load_task(ctx, str(doc['task_id']))
        allowed = True
    if not allowed:
        raise HTTPException(403, 'You cannot access this document.')
    return doc


async def store(ctx, filename, content, document_type, employee, expiry_date=None, task_id=None, document_id=None):
    filename, mime = validate_file(filename, content)
    expiry = date_string(expiry_date) if expiry_date else None
    details = expiry_details(expiry)
    doc = {'name': filename, 'mime': mime, 'size': len(content), 'content': Binary(content),
        'document_type': document_type, 'employee_id': employee['_id'], 'expiry_date': expiry,
        'expiry_status': details['status'], 'expiry_window': details['expiry_window'], 'days_until_expiry': details['days_until_expiry'],
        'sha256': hashlib.sha256(content).hexdigest(), 'uploaded_by': ctx['user']['_id'], 'created_at': now(),
        'history': [audit(ctx, 'upload-document')]}
    if task_id:
        doc['task_id'] = task_id
    if document_id:
        await ctx['db']['documents'].update_one({'_id': document_id}, {'$setOnInsert': doc}, upsert=True)
        doc['_id'] = document_id
    else:
        result = await ctx['db']['documents'].insert_one(doc)
        doc['_id'] = result.inserted_id
    if expiry:
        await scan_document_expiry(ctx['db'], {'_id': doc['_id']})
    return metadata(doc)


async def store_attachments(ctx, attachments, task_id):
    if not isinstance(attachments, list) or len(attachments) > 10:
        raise HTTPException(422, 'At most ten task attachments are allowed.')
    prepared = []
    for item in attachments:
        if not isinstance(item, dict):
            raise HTTPException(422, 'Invalid attachment.')
        if item.get('id') or item.get('_id'):
            doc = await load_document(ctx, item.get('id') or item.get('_id'))
            if str(doc.get('task_id')) != str(task_id):
                raise HTTPException(422, 'Attachment belongs to another task.')
            prepared.append((doc, None))
        else:
            encoded = item.get('content_base64')
            if not isinstance(encoded, str):
                raise HTTPException(422, 'Attachment must contain actual file bytes.')
            if len(encoded) > (get_settings().max_document_bytes * 4 // 3 + 8):
                raise HTTPException(413, 'Attachment exceeds upload limit.')
            try:
                content = base64.b64decode(encoded, validate=True)
            except ValueError:
                raise HTTPException(422, 'Invalid base64 attachment.')
            filename, _ = validate_file(item.get('name'), content)
            prepared.append((filename, content))
    result = []
    for filename, content in prepared:
        if content is None:
            result.append(metadata(filename))
        else:
            key = hashlib.sha256((str(task_id) + str(ctx['employee']['_id']) + filename).encode() + content).hexdigest()
            result.append(await store(ctx, filename, content, 'Task Attachment', ctx['employee'], task_id=task_id, document_id=key))
    return result


@router.post('')
@router.post('/upload')
async def upload(file: UploadFile = File(...), document_type: str = Form('Supporting Document'), expiry_date: str | None = Form(None), employee_id: str | None = Form(None), ctx: dict = Depends(require_session)):
    employee = ctx['employee']
    if employee_id:
        employee = await employee_by_reference(ctx['db'], employee_id)
        if not own(ctx, employee['_id']) and role(ctx) not in HR:
            raise HTTPException(403, 'You can only upload your own documents.')
    if not document_type.strip() or len(document_type) > 100:
        raise HTTPException(422, 'Invalid document type.')
    content = await file.read(get_settings().max_document_bytes + 1)
    return {'success': True, 'document': await store(ctx, file.filename, content, document_type, employee, expiry_date)}


@router.get('')
async def list_documents(employee_id: str | None = None, ctx: dict = Depends(require_session)):
    query = {} if role(ctx) in HR else {'employee_id': {'$in': refs(ctx['employee'])}}
    if employee_id:
        employee = await employee_by_reference(ctx['db'], employee_id)
        if role(ctx) not in HR and not own(ctx, employee['_id']):
            raise HTTPException(403, 'You can only list your own documents.')
        query = {'employee_id': {'$in': refs(employee)}}
    rows = await ctx['db']['documents'].find(query, {'content': 0}).sort('created_at', -1).to_list(None)
    return {'success': True, 'documents': [metadata(r) for r in rows]}


@router.post('/expiry-scan')
async def expiry_scan(ctx: dict = Depends(require_session)):
    require_roles(ctx, HR)
    return {'success': True, **await scan_document_expiry(ctx['db'])}


@router.get('/expiry-summary')
async def expiry_summary(ctx: dict = Depends(require_session)):
    require_roles(ctx, HR)
    return {'success': True, **await document_expiry_summary(ctx['db'])}


@router.get('/{document_id}')
async def get_document(document_id: str, ctx: dict = Depends(require_session)):
    return {'success': True, 'document': metadata(await load_document(ctx, document_id))}


@router.get('/{document_id}/download')
async def download(document_id: str, ctx: dict = Depends(require_session)):
    doc = await load_document(ctx, document_id)
    return Response(bytes(doc['content']), media_type=doc['mime'], headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(doc['name'], safe=''), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.patch('/{document_id}')
async def update_document(document_id: str, body: dict = Body(...), ctx: dict = Depends(require_session)):
    doc = await load_document(ctx, document_id)
    if role(ctx) not in HR:
        raise HTTPException(403, 'Only authorized management may amend document metadata.')
    if set(body) - {'expiry_date', 'document_type'}:
        raise HTTPException(422, 'Only document type and expiry may be updated.')
    updates = {}
    if 'expiry_date' in body:
        updates['expiry_date'] = date_string(body['expiry_date']) if body['expiry_date'] else None
        details = expiry_details(updates['expiry_date'])
        updates.update(expiry_status=details['status'], expiry_window=details['expiry_window'], days_until_expiry=details['days_until_expiry'])
        await ctx['db']['notifications'].update_many(
            {'reference_type': 'Document', 'reference_id': str(doc['_id']), 'read': {'$ne': True}},
            {'$set': {'read': True, 'is_read': True, 'superseded': True, 'read_at': now()}},
        )
    if 'document_type' in body:
        value = body['document_type']
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise HTTPException(422, 'Invalid document type.')
        updates['document_type'] = value
    await ctx['db']['documents'].update_one({'_id': doc['_id']}, {'$set': updates, '$push': {'history': audit(ctx, 'update-document')}})
    if 'expiry_date' in updates and updates['expiry_date']:
        await scan_document_expiry(ctx['db'], {'_id': doc['_id']})
    return {'success': True, 'document': metadata({**doc, **updates})}
