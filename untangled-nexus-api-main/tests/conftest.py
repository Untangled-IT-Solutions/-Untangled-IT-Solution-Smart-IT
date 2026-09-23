import pytest
import pytest_asyncio
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient
from app.main import app
from app import security, db as database
from app.routers import auth
from app.domain import now
from app.security import hash_pbkdf2_sha256

PASSWORD = 'test-only-strong-password'
HASH = hash_pbkdf2_sha256(PASSWORD)


@pytest_asyncio.fixture
async def api(monkeypatch):
    db = AsyncMongoMockClient(tz_aware=True)['nexus_test']
    monkeypatch.setattr(security, 'get_db', lambda: db)
    monkeypatch.setattr(auth, 'get_db', lambda: db)
    await database.ensure_indexes(db)
    people = {}
    for i, role in enumerate(('Director', 'Business Lead', 'Operations Manager', 'Staff', 'Intern', 'Branch Manager')):
        employee = {'_id': ObjectId(), 'employee_id': str(100+i), 'full_name': role + ' Person', 'email': role.replace(' ', '').lower()+'@test.invalid', 'role': role, 'status': 'active', 'department': 'IT', 'private_note': 'must-not-leak'}
        user = {'_id': ObjectId(), 'employee_id': str(employee['_id']), 'username': employee['email'], 'email': employee['email'], 'password_hash': HASH, 'status': 'active', 'role': role}
        await db['employees'].insert_one(employee)
        await db['users'].insert_one(user)
        people[role] = {'employee': employee, 'user': user}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        headers = {}
        for role, person in people.items():
            response = await client.post('/api/auth/login', json={'username': person['user']['username'], 'password': PASSWORD})
            assert response.status_code == 200, response.text
            headers[role] = {'Authorization': 'Bearer ' + response.json()['token']}
        yield client, db, people, headers
