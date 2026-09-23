from calendar import monthrange
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from app.security import require_session, serialize_id
from app.domain import PEOPLE_OVERSIGHT, BUSINESS_WORK, role, own, now, as_datetime, id_filter, change, audit, SAST

router = APIRouter(prefix='/api/calendar/events', tags=['calendar'])


class Event(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    event_type: str = 'Meeting'
    start_date: str
    end_date: str = ''
    department: str = ''
    details: str = Field(default='', max_length=20000)
    recurrence: str = 'None'


def dates(body):
    try:
        start = as_datetime(body.start_date)
        end = as_datetime(body.end_date or body.start_date)
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid calendar date.')
    if end < start or end - start > timedelta(days=366):
        raise HTTPException(422, 'Invalid calendar duration.')
    if body.recurrence not in {'None', 'Daily', 'Weekly', 'Monthly', 'Yearly'}:
        raise HTTPException(422, 'Unsupported recurrence.')
    return start, end


def visible(ctx, item):
    return role(ctx) in PEOPLE_OVERSIGHT or own(ctx, item.get('employee_id')) or (item.get('visibility') == 'team' and item.get('department', '') in {'', 'General', ctx['employee'].get('department')})


async def events_between(ctx, start, end):
    rows = await ctx['db']['calendar_events'].find({}).to_list(None)
    result = []
    for row in rows:
        if not visible(ctx, row):
            continue
        first = as_datetime(row['start_date'])
        duration = as_datetime(row.get('end_date') or row['start_date']) - first
        recurrence = row.get('recurrence', 'None')
        if recurrence not in {'None', 'Daily', 'Weekly', 'Monthly', 'Yearly'}:
            raise HTTPException(422, 'An existing event has an unsupported recurrence.')
        occurrence = first
        index = 0
        if recurrence in {'Daily', 'Weekly'}:
            step = 1 if recurrence == 'Daily' else 7
            index = max(0, ((start - duration - first).days // step))
            occurrence = first + timedelta(days=step * index)
        elif recurrence in {'Monthly', 'Yearly'}:
            months = (start.year - first.year)*12 + start.month - first.month
            index = max(0, months // (12 if recurrence == 'Yearly' else 1) - 13)
        while occurrence < end:
            if recurrence in {'Monthly', 'Yearly'}:
                month_index = first.year*12 + first.month - 1 + index*(12 if recurrence == 'Yearly' else 1)
                year, month = divmod(month_index, 12)
                month += 1
                occurrence = first.replace(year=year, month=month, day=min(first.day, monthrange(year, month)[1]))
            if occurrence >= end:
                break
            if occurrence + duration >= start:
                item = {**row, 'start_date': occurrence.isoformat(), 'end_date': (occurrence + duration).isoformat(), 'occurrence_index': index}
                result.append(serialize_id(item))
            if recurrence == 'None':
                break
            index += 1
            if recurrence in {'Daily', 'Weekly'}:
                occurrence = first + timedelta(days=index*(1 if recurrence == 'Daily' else 7))
            if len(result) >= 2000:
                raise HTTPException(422, 'Too many calendar occurrences; narrow the date range.')
    return sorted(result, key=lambda item: item['start_date'])


@router.get('')
async def list_events(year: int = Query(..., ge=1970, le=2200), month: int = Query(..., ge=1, le=12), ctx: dict = Depends(require_session)):
    start = datetime(year, month, 1, tzinfo=SAST)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=SAST)
    return {'success': True, 'events': await events_between(ctx, start, end)}


@router.get('/upcoming')
async def upcoming(days: int = Query(7, ge=1, le=366), ctx: dict = Depends(require_session)):
    return {'success': True, 'events': await events_between(ctx, now(), now() + timedelta(days=days))}


@router.post('')
async def create_event(body: Event, ctx: dict = Depends(require_session)):
    start, end = dates(body)
    doc = {**body.model_dump(), 'start_date': start.isoformat(), 'end_date': end.isoformat(), 'employee_id': ctx['employee']['_id'],
        'visibility': 'team' if role(ctx) in PEOPLE_OVERSIGHT | BUSINESS_WORK else 'personal', 'revision': 0, 'created_at': now(), 'history': [audit(ctx, 'create-event')]}
    result = await ctx['db']['calendar_events'].insert_one(doc)
    doc['_id'] = result.inserted_id
    return {'success': True, 'event': serialize_id(doc)}


async def editable(ctx, event_id):
    row = await ctx['db']['calendar_events'].find_one(id_filter(event_id))
    if not row:
        raise HTTPException(404, 'Event not found.')
    if role(ctx) not in PEOPLE_OVERSIGHT and not own(ctx, row.get('employee_id')):
        raise HTTPException(403, 'You cannot change this event.')
    return row


@router.patch('/{event_id}')
async def update_event(event_id: str, body: Event, ctx: dict = Depends(require_session)):
    row = await editable(ctx, event_id)
    start, end = dates(body)
    result = await change(ctx['db']['calendar_events'], row, {**body.model_dump(), 'start_date': start.isoformat(), 'end_date': end.isoformat()}, audit(ctx, 'update-event'))
    return {'success': True, 'event': serialize_id(result)}


@router.delete('/{event_id}')
async def delete_event(event_id: str, ctx: dict = Depends(require_session)):
    row = await editable(ctx, event_id)
    result = await ctx['db']['calendar_events'].delete_one({'_id': row['_id'], 'revision': row.get('revision')})
    if not result.deleted_count:
        raise HTTPException(409, 'Event changed; reload and retry.')
    return {'success': True}
