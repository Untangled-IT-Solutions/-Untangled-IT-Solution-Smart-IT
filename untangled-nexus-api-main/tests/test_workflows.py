from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from bson import ObjectId
from app.domain import now, change
from fastapi import HTTPException
from conftest import PASSWORD

async def call(client, headers, method, path, role='Staff', expected=200, **kwargs):
    response = await client.request(method, path, headers=headers[role], **kwargs)
    assert response.status_code == expected, response.text
    return response.json() if response.content and response.headers.get('content-type', '').startswith('application/json') else response

async def test_task_workflow_and_permissions(api):
    c, db, people, h = api
    task = (await call(c,h,'POST','/api/tasks','Business Lead',json={'title':'Install equipment'}))['task']
    tid = task['id']; path = '/api/tasks/'+tid
    await call(c,h,'POST',path+'/assign',expected=403,json={'employee_id':str(people['Staff']['employee']['_id'])})
    await call(c,h,'POST',path+'/assign','Operations Manager',json={'assigned_to':'Staff Person'})
    await call(c,h,'GET',path,'Intern',expected=403)
    await call(c,h,'POST',path+'/start')
    await call(c,h,'POST',path+'/start',expected=409)
    await db.work_assignments.update_one({'_id':ObjectId(tid)}, {'$set':{'active_timer_started_at':now()-timedelta(hours=1)}})
    task=(await call(c,h,'POST',path+'/pause'))['task']
    assert 1 <= task['actual_hours'] < 1.01
    await call(c,h,'PATCH',path,json={'hours_logged':0.5,'note':'Additional work'})
    await call(c,h,'POST',path+'/resume')
    await call(c,h,'POST',path+'/submit-review')
    await call(c,h,'PATCH',path,expected=403,json={'status':'Completed'})
    await call(c,h,'POST',path+'/return','Operations Manager',json={'note':'Fix wiring'})
    await call(c,h,'POST',path+'/start')
    await call(c,h,'POST',path+'/submit-review')
    task=(await call(c,h,'POST',path+'/complete','Operations Manager'))['task']
    assert task['status']=='Completed' and task['actual_hours'] >= 1.5
    await call(c,h,'POST',path+'/resume',expected=409)
    assert (await call(c,h,'GET','/api/tasks','Intern'))['tasks']==[]
    assert (await call(c,h,'GET','/api/notifications/unread-count'))['count'] > 0
    await call(c,h,'POST','/api/notifications/mark-all-read')
    assert (await call(c,h,'GET','/api/notifications/unread-count'))['count']==0


async def test_task_timer_records_only_explicit_work_sessions(api):
    c, db, people, h = api
    created = await call(
        c, h, 'POST', '/api/tasks', 'Business Lead',
        json={'title': 'Phase 9 timed work', 'priority': 'Low'},
    )
    task = created['task']
    tid = task['id']
    path = '/api/tasks/' + tid
    assert task['status'] == 'Pending'
    assert task['actual_hours'] == 0
    assert task['elapsed_hours'] == 0
    assert task['active_timer_started_at'] is None

    # Merely viewing Nexus never starts or advances task work time.
    viewed = (await call(c, h, 'GET', path, 'Business Lead'))['task']
    assert viewed['elapsed_hours'] == 0

    prioritised = await call(
        c, h, 'PATCH', path, 'Operations Manager', json={'priority': 'Urgent'}
    )
    assert prioritised['task']['priority'] == 'Urgent'
    await call(
        c, h, 'POST', path + '/assign', 'Operations Manager',
        json={'employee_id': str(people['Staff']['employee']['_id'])},
    )

    await call(c, h, 'POST', path + '/resume', expected=409)
    await call(c, h, 'POST', path + '/log-time', expected=409, json={'hours': 0.25})
    await call(c, h, 'POST', path + '/start')
    await call(
        c, h, 'POST', path + '/reassign', 'Operations Manager', expected=409,
        json={'employee_id': str(people['Intern']['employee']['_id'])},
    )
    await db.work_assignments.update_one(
        {'_id': ObjectId(tid)},
        {'$set': {'active_timer_started_at': now() - timedelta(minutes=30)}},
    )
    paused = (await call(c, h, 'POST', path + '/pause'))['task']
    assert 0.5 <= paused['actual_hours'] < 0.51
    assert paused['active_timer_started_at'] is None

    await call(c, h, 'POST', path + '/start', expected=409)
    logged = (await call(c, h, 'POST', path + '/log-time', json={'hours': 0.25}))['task']
    assert 0.75 <= logged['actual_hours'] < 0.76
    await call(c, h, 'POST', path + '/resume')
    await db.work_assignments.update_one(
        {'_id': ObjectId(tid)},
        {'$set': {'active_timer_started_at': now() - timedelta(minutes=15)}},
    )
    submitted = (await call(c, h, 'POST', path + '/submit-review'))['task']
    assert submitted['status'] == 'Waiting Review'
    assert 1.0 <= submitted['actual_hours'] < 1.02
    assert submitted['active_timer_started_at'] is None

    await call(c, h, 'POST', path + '/return', 'Operations Manager', json={'note': 'Correct it'})
    await call(c, h, 'POST', path + '/submit-review', expected=409)
    await call(c, h, 'POST', path + '/start')
    await db.work_assignments.update_one(
        {'_id': ObjectId(tid)},
        {'$set': {'active_timer_started_at': now() - timedelta(minutes=10)}},
    )
    await call(c, h, 'POST', path + '/submit-review')
    completed = (await call(c, h, 'POST', path + '/complete', 'Operations Manager'))['task']
    assert completed['status'] == 'Completed'
    assert 1.16 <= completed['actual_hours'] < 1.20


async def test_operations_manager_cannot_review_own_task(api):
    c, db, people, h = api
    task = (await call(
        c, h, 'POST', '/api/tasks', 'Operations Manager',
        json={
            'title': 'Independent review required',
            'assigned_to': str(people['Operations Manager']['employee']['_id']),
        },
    ))['task']
    path = '/api/tasks/' + task['id']
    await call(c, h, 'POST', path + '/start', 'Operations Manager')
    await call(c, h, 'POST', path + '/submit-review', 'Operations Manager')
    await call(c, h, 'POST', path + '/complete', 'Operations Manager', expected=403)

async def test_attendance_transitions(api):
    c,db,p,h=api
    await call(c,h,'POST','/api/attendance/clock-out',expected=409)
    for action in ('clock-in','break-start','break-end','clock-out'):
        await call(c,h,'POST','/api/attendance/'+action)
        await call(c,h,'POST','/api/attendance/'+action,expected=409)
    await call(c,h,'GET','/api/attendance/status')
    await call(c,h,'GET','/api/attendance/history')
    await call(c,h,'GET','/api/attendance/team','Operations Manager')
    await call(c,h,'GET','/api/attendance/team',expected=403)


async def test_attendance_uses_server_time_and_calculates_net_work(api):
    c, db, people, h = api
    base = '/api/attendance/'
    fresh = await call(c, h, 'GET', base + 'status')
    assert fresh['status'] == 'not_started'
    assert fresh['attendance'] is None

    await call(c, h, 'POST', base + 'break-end', expected=409)
    await call(
        c, h, 'POST', base + 'clock-in', expected=403,
        json={'employee_id': str(people['Intern']['employee']['_id'])},
    )
    started = (await call(c, h, 'POST', base + 'clock-in'))['attendance']
    assert started['work_date'] == datetime.now(ZoneInfo('Africa/Johannesburg')).date().isoformat()
    assert datetime.fromisoformat(started['clock_in_at'].replace('Z', '+00:00')).tzinfo is not None
    await call(c, h, 'POST', base + 'clock-in', expected=409)

    working = await call(c, h, 'GET', base + 'working-now', 'Operations Manager')
    assert working['count'] == 1 and working['on_break_count'] == 0
    await call(c, h, 'GET', base + 'working-now', expected=403)

    await call(c, h, 'POST', base + 'break-start')
    paused = await call(c, h, 'GET', base + 'working-now', 'Operations Manager')
    assert paused['count'] == 0 and paused['on_break_count'] == 1
    await call(c, h, 'POST', base + 'break-start', expected=409)

    employee_id = people['Staff']['employee']['_id']
    await db.attendance.update_one(
        {'employee_id': employee_id},
        {'$set': {
            'clock_in_at': now() - timedelta(hours=2),
            'break_started_at': now() - timedelta(minutes=30),
        }},
    )
    await call(c, h, 'POST', base + 'clock-out', expected=409)
    await call(c, h, 'POST', base + 'break-end')
    completed = (await call(c, h, 'POST', base + 'clock-out'))['attendance']
    assert completed['status'] == 'clocked_out'
    assert 29.9 <= completed['break_duration_minutes'] <= 30.1
    assert 1.49 <= completed['hours_worked'] <= 1.51
    assert 5390 <= completed['work_seconds'] <= 5410

    status = await call(c, h, 'GET', base + 'status')
    assert status['state'] == 'completed' and status['clocked_in'] is False
    for action in ('clock-in', 'clock-out', 'break-start', 'break-end'):
        await call(c, h, 'POST', base + action, expected=409)
    history = await call(c, h, 'GET', base + 'history?days=1')
    assert history['records'][0]['hours_worked'] == completed['hours_worked']
    team = await call(c, h, 'GET', base + 'team', 'Operations Manager')
    assert any(row['employee_name'] == 'Staff Person' for row in team['records'])

async def test_documents_leave_and_stages(api):
    c,db,p,h=api
    data=b'%PDF-1.4\nactual-test-file'
    doc=(await call(c,h,'POST','/api/documents',files={'file':('../private/note.pdf',data,'application/pdf')},data={'document_type':'Doctor note','expiry_date':'2020-01-01'}))['document']
    assert doc['status']=='expired' and 'content' not in doc and doc['name']=='note.pdf'
    assert 'url' not in doc and 'download_url' not in doc
    stored=await db.documents.find_one({'_id':ObjectId(doc['id'])})
    assert bytes(stored['content'])==data and stored['sha256']
    path='/api/documents/'+doc['id']+'/download'
    downloaded=await call(c,h,'GET',path)
    assert downloaded.content==data
    assert downloaded.headers['cache-control']=='no-store'
    assert downloaded.headers['x-content-type-options']=='nosniff'
    await call(c,h,'GET',path,'Intern',expected=403)
    assert (await c.get(path)).status_code==401
    await call(c,h,'POST','/api/documents',expected=415,files={'file':('fake.pdf',b'not pdf')})
    ordinary=(await call(c,h,'POST','/api/documents',files={'file':('ordinary.pdf',data,'application/pdf')},data={'document_type':'Supporting Document'}))['document']
    await call(c,h,'POST','/api/leave',expected=422,json={'leave_type':'Sick','start_date':'2026-09-21','end_date':'2026-09-21','reason':'Missing note','document_ids':[]})
    await call(c,h,'POST','/api/leave',expected=422,json={'leave_type':'Sick','start_date':'2026-09-21','end_date':'2026-09-21','reason':'Wrong kind','document_ids':[ordinary['id']]})
    await call(c,h,'POST','/api/leave','Intern',expected=403,json={'leave_type':'Sick','start_date':'2026-09-21','end_date':'2026-09-21','reason':'Foreign note','document_ids':[doc['id']]})
    leave=(await call(c,h,'POST','/api/leave',json={'leave_type':'Sick','start_date':'2026-10-01','end_date':'2026-10-02','reason':'Medical','document_ids':[doc['id']],'requires_director':True}))['leave']
    assert leave['document_ids']==[doc['id']] and leave['requested_by']=='Staff Person'
    path='/api/leave/'+leave['_id']+'/approve'
    await call(c,h,'POST',path,expected=403,json={'reviewer_role':'Director'})
    await call(c,h,'POST',path,'Director',expected=403)
    await call(c,h,'GET','/api/documents/'+doc['id']+'/download','Business Lead',expected=403)
    result=await call(c,h,'POST',path,'Operations Manager')
    assert result['leave']['current_stage']=='Business'
    assert (await call(c,h,'GET','/api/documents/'+doc['id']+'/download','Business Lead')).content==data
    result=await call(c,h,'POST',path,'Business Lead')
    assert result['leave']['current_stage']=='Director'
    result=await call(c,h,'POST',path,'Director')
    assert result['leave']['status']=='Approved'
    await call(c,h,'POST',path,'Director',expected=403)

    rejected=(await call(c,h,'POST','/api/leave',json={'leave_type':'Annual','start_date':'2026-11-01','end_date':'2026-11-02','reason':'Rest'}))['leave']
    reject_path='/api/leave/'+rejected['_id']+'/reject'
    await call(c,h,'POST',reject_path,'Operations Manager',expected=422)
    final=await call(c,h,'POST',reject_path,'Operations Manager',json={'reason':'Insufficient coverage'})
    assert final['leave']['status']=='Rejected'
    assert final['leave']['rejection_reason']=='Insufficient coverage'

async def test_session_expiry_and_private_fields(api):
    c,db,p,h=api
    me=await call(c,h,'GET','/api/auth/me')
    assert 'password_hash' not in str(me) and 'must-not-leak' not in str(me)
    response=await c.post('/api/auth/login',json={'username':p['Staff']['user']['username'],'password':'wrong'})
    assert response.status_code==401
    await db.api_sessions.update_many({}, {'$set':{'expires_at':now()-timedelta(seconds=1)}})
    await call(c,h,'GET','/api/auth/me',expected=401)

async def test_administration_and_forced_password(api):
    c,db,p,h=api
    uid=str(p['Staff']['user']['_id'])
    await call(c,h,'PATCH','/api/admin/users/'+uid,expected=403,json={'role':'Director'})
    await call(c,h,'PATCH','/api/admin/users/'+uid,'Operations Manager',expected=403,json={'role':'Director'})
    await call(c,h,'POST','/api/admin/users/'+uid+'/reset-password','Operations Manager',json={'password':'new-test-only-password'})
    await call(c,h,'GET','/api/auth/me',expected=401)
    login=await c.post('/api/auth/login',json={'username':p['Staff']['user']['username'],'password':'new-test-only-password'})
    assert login.status_code==200,login.text
    h['Staff']={'Authorization':'Bearer '+login.json()['token']}
    await call(c,h,'GET','/api/tasks',expected=403)
    await call(c,h,'POST','/api/auth/change-password',json={'current_password':'new-test-only-password','new_password':'changed-test-only-password'})
    await call(c,h,'GET','/api/tasks')

@pytest.mark.parametrize('kind,signature',[('CSV',b'\xef\xbb\xbf'),('PDF',b'%PDF'),('Excel',b'PK')])
async def test_real_report_downloads(api,kind,signature):
    c,db,p,h=api
    await db.work_assignments.insert_one({'title':'=1+1','status':'Pending'})
    result=await call(c,h,'POST','/api/reports/export','Operations Manager',json={'type':'Task Workload','format':kind})
    response=await call(c,h,'GET',result['url'],'Operations Manager')
    assert response.content.startswith(signature)
    await call(c,h,'GET',result['url'],expected=403)

async def test_calendar_permissions(api):
    c,db,p,h=api
    event={'title':'Personal meeting','start_date':'2026-10-01','end_date':'2026-10-01','recurrence':'Weekly'}
    result=await call(c,h,'POST','/api/calendar/events',json=event)
    eid=result['event'].get('id') or result['event']['_id']
    await call(c,h,'DELETE','/api/calendar/events/'+eid,'Intern',expected=403)
    await call(c,h,'GET','/api/calendar/events?year=2026&month=10')
    await call(c,h,'PATCH','/api/calendar/events/'+eid,json={**event,'title':'Changed'})
    await call(c,h,'DELETE','/api/calendar/events/'+eid)

async def test_revision_conflict(api):
    c,db,p,h=api
    record={'_id':ObjectId(),'revision':0}
    await db.test_records.insert_one(record)
    await change(db.test_records,record,{'status':'first'},{'action':'test'})
    with pytest.raises(HTTPException) as exc:
        await change(db.test_records,record,{'status':'second'},{'action':'test'})
    assert exc.value.status_code==409

async def test_office_approvals_projects_and_dashboard(api):
    c,db,p,h=api
    req=(await call(c,h,'POST','/api/office-requests',json={'item':'Mouse','quantity':'2','requested_by':'Forged name','requires_director':True}))['request']
    assert req['requested_by']=='Staff Person'
    path='/api/office-requests/'+req['_id']
    await call(c,h,'PATCH',path,expected=403,json={'status':'Approved'})
    await call(c,h,'PATCH',path,'Operations Manager',json={'status':'Approved'})
    result=await call(c,h,'PATCH',path,'Director',json={'status':'Approved'})
    assert result['request']['status']=='Approved'
    approval=(await call(c,h,'POST','/api/approvals',json={'title':'Travel','amount':''}))['approval']
    await call(c,h,'POST','/api/approvals/'+approval['_id']+'/reject','Operations Manager',json={'reason':'Insufficient details','reviewer_name':'Imposter'})
    project={'_id':ObjectId(),'name':'Internal project','member_ids':[p['Staff']['employee']['_id']]}
    await db.projects.insert_one(project)
    await call(c,h,'GET','/api/projects/'+str(project['_id']))
    await call(c,h,'GET','/api/projects/'+str(project['_id']),'Intern',expected=404)
    for who,route in [('Staff','summary'),('Director','director'),('Operations Manager','operations'),('Business Lead','business-lead')]:
        result=await call(c,h,'GET','/api/dashboard/'+route,who)
        assert result['success'] is True
    await call(c,h,'GET','/api/dashboard/director',expected=403)
    await call(c,h,'GET','/api/employees')
    await call(c,h,'GET','/api/admin/users','Operations Manager')

async def test_dashboard_director_queue_before_limit_and_scoping(api):
    c,db,p,h=api
    for i in range(12):
        await db.approvals.insert_one({'title':str(i),'employee_id':p['Intern']['employee']['_id'],'status':'Pending','current_stage':'Director' if i==11 else 'Manager'})
    director=await call(c,h,'GET','/api/dashboard/director','Director')
    assert len(director['approvals_queue'])==1
    staff=await call(c,h,'GET','/api/dashboard/summary')
    assert staff['pending_approvals']==0 and staff['total_people']==1

async def test_no_unauthenticated_business_routes(api):
    c,db,p,h=api
    for path in ('/api/tasks','/api/employees','/api/leave','/api/documents','/api/quotes','/api/orders','/api/calendar/events','/api/admin/users','/api/reports/types'):
        response=await c.get(path)
        assert response.status_code==401,(path,response.text)


async def test_quote_and_order_writes_use_authenticated_backend(api):
    c, db, people, h = api
    quote = {
        "_id": ObjectId(), "reference": "Q-CENTRAL-1", "status": "received",
        "items": [{"id": "line-1", "name": "Router", "qty": 2}], "revision": 0,
    }
    order = {
        "_id": ObjectId(), "reference": "O-CENTRAL-1", "status": "pending", "revision": 0,
    }
    await db.quotes.insert_one(quote)
    await db.orders.insert_one(order)

    assert (await call(c, h, "GET", "/api/quotes"))["quotes"] == []
    await call(c, h, "POST", "/api/quotes/Q-CENTRAL-1/status", expected=403, json={"status": "accepted"})

    staff_id = str(people["Staff"]["employee"]["_id"])
    assigned = await call(
        c, h, "PUT", "/api/admin/quotes/Q-CENTRAL-1/assignment", "Operations Manager",
        json={"employee_id": staff_id},
    )
    assert assigned["quote"]["assigned_to"]["full_name"] == "Staff Person"
    await call(c, h, "POST", "/api/admin/quotes/Q-CENTRAL-1/status", json={"status": "accepted"})
    await call(c, h, "PUT", "/api/admin/quotes/Q-CENTRAL-1", json={"replyMessage": "We are checking stock."})
    await call(c, h, "POST", "/api/admin/quotes/Q-CENTRAL-1/director-review/request", json={})
    await call(
        c, h, "PUT", "/api/admin/quotes/Q-CENTRAL-1/director-review", expected=403,
        json={"general_reply": "Available", "items": []},
    )
    reviewed = await call(
        c, h, "PUT", "/api/admin/quotes/Q-CENTRAL-1/director-review", "Director",
        json={"general_reply": "Available", "items": [{"item_id": "line-1", "availability": "Available"}]},
    )
    assert reviewed["quote"]["director_review"]["status"] == "reviewed"

    await call(
        c, h, "PUT", "/api/admin/orders/O-CENTRAL-1/assignment", "Operations Manager",
        json={"employee_id": staff_id},
    )
    updated = await call(
        c, h, "PATCH", "/api/orders/status",
        json={"reference": "O-CENTRAL-1", "status": "processing"},
    )
    assert updated["order"]["status"] == "processing"
    await call(
        c, h, "PATCH", "/api/orders/O-CENTRAL-1/status", "Intern", expected=403,
        json={"status": "completed"},
    )
    await call(
        c, h, "PATCH", "/api/orders/O-CENTRAL-1/status", expected=422,
        json={"status": "not-a-real-state"},
    )

    stored_quote = await db.quotes.find_one({"reference": "Q-CENTRAL-1"})
    stored_order = await db.orders.find_one({"reference": "O-CENTRAL-1"})
    assert stored_quote["replyMessage"] == "We are checking stock."
    assert stored_quote["revision"] == 5
    assert stored_order["revision"] == 2
