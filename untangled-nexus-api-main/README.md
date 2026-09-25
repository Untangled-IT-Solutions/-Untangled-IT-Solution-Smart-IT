# Untangled Nexus API (FastAPI)

Dedicated **FastAPI** backend for the Nexus desktop application. This project
comes from the supplied `untangled-nexus-api-main.zip` and is the canonical
Nexus backend. The Website continues to use the separate Node backend in
`../Backend`. See `../ARCHITECTURE.md` for routing and deployment boundaries.

The listed routes are the current implementation, not a declaration of staff
readiness. Missing workflows and authorization fixes identified in Phase 1
remain for subsequent implementation phases.

## Stack

- FastAPI + Uvicorn
- Motor (async MongoDB)
- Same MongoDB Atlas database as before
- Compatible password hashes (`pbkdf2_sha256$…` and SHA-256 hex)

## Endpoints (desktop-critical)

| Area | Paths |
|------|--------|
| Health | `GET /api/health`, `GET /ready` |
| Auth | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout` |
| Dashboard | `GET /api/dashboard/summary`, `/director`, `/business-lead`, `/operations` |
| Attendance | `GET /api/attendance/today`, team/history aliases, clock-in/out, break |
| Notifications | `GET /api/notifications`, unread-count, mark read |
| Tasks | `GET /api/tasks`, get/update/start/assign |
| Approvals | `GET /api/approvals` |
| Quotes/Orders | authenticated list, assignment, status, reply, director review |

Dashboard returns `present_count`, `late_count`, `absent_count` and nested `attendance` (Present = people working).

## Render

**Build command**

```text
pip install -r requirements.txt
```

**Start command**

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Health check path:** `/api/ready`

**Env**

- `MONGODB_URI` (required) — same Atlas URI as the Node app
- `FRONTEND_URL` (optional, default `*`)
- `SESSION_EXPIRY_HOURS` (default `8`)
- `MAX_DOCUMENT_BYTES` (default and maximum `8388608`)
- `SICK_LEAVE_DOCUMENT_REQUIRED` (default `false`; configure your approved policy)

## Local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export MONGODB_URI="mongodb+srv://..."
uvicorn app.main:app --reload --port 10000
```

## Separate deployment

Deploy this directory as the Nexus Python service using the build/start
commands above. Keep the Website Node service running separately; do not
replace its runtime or route the Website to this service.

If deploying from this combined repository, set the Nexus service root
directory to `untangled-nexus-api-main`. If deploying this directory as its
own repository, use that repository root. `render.yaml` describes the Nexus
service only. Set `MONGODB_URI` in server secrets, never in desktop configuration.

The authenticated Nexus workflow routes do not move public commerce ownership
from Node. Public Website submissions and customer tracking remain in Node.

## Required management accounts

The canonical roles are `Director`, `Branch Manager`, `Business Lead`,
`Operations Manager`, `Staff`, and `Intern`. `Business Lead` and `Branch
Manager` are distinct. The management provisioning command preserves Benny
Moremi's existing one of those two roles and refuses to guess when the employee
record is unclear.

First preview the plan against the configured server database:

```text
python scripts/provision_management_accounts.py
```

To apply it, provide three temporary passwords through process environment
variables and add `--apply`:

```text
NEXUS_ZANDILE_TEMP_PASSWORD
NEXUS_BENNY_TEMP_PASSWORD
NEXUS_UBUNTU_TEMP_PASSWORD
```

Optional username overrides are `NEXUS_ZANDILE_USERNAME`,
`NEXUS_BENNY_USERNAME`, and `NEXUS_UBUNTU_USERNAME`; otherwise each existing
account username or employee email is retained. Do not put temporary passwords
in source, command arguments, or committed environment files. The command
creates no employees, refuses ambiguous matches and duplicate accounts, stores
only PBKDF2-SHA256 hashes, revokes existing sessions, activates the accounts,
and requires password change on first login.

Authorization is enforced by FastAPI using the authenticated session. Business
Leads receive scoped task-dump and team-work visibility without HR or assignment
permissions. Operations Managers own work assignment and operational queues.
Directors own Director-stage approvals and executive views. Staff and Interns
receive personal records only. Client-supplied reviewer names or roles never
grant authority.


## API validation

Use Python 3.12 and install `requirements.txt` plus `requirements-dev.txt`, then
run `python -m pytest -q`. Tests exercise the real HTTP handlers with an isolated,
test-only MongoDB adapter. Runtime storage always uses Motor/MongoDB; there is no
in-memory production fallback. Live database integration still needs validation.

Startup creates additive Nexus indexes for account identity, normalized usernames,
login-attempt expiration, session lookup and document expiry. Existing employee
records are never recreated. Documents contain actual private BSON bytes (up to
8 MiB); downloads require a bearer session and authorization.

New sessions store hashed tokens and expire after the configured duration.
Password resets revoke sessions and require `/api/auth/change-password` before
business endpoints can be used. The desktop enforces this change before opening
the main window.

See `../PHASE7_STATUS.md` and `API_ROUTES.md` for scope, routes and remaining work.
