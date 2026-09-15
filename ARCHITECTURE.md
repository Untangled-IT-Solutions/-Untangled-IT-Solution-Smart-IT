# Nexus and Website separation

## Application ownership

| Component | Source | Backend | Database access |
| --- | --- | --- | --- |
| Internal Nexus desktop | `App/` | `untangled-nexus-api-main/` (FastAPI) | Server only |
| Public Website | `Website/` | `Backend/` (Node/TypeScript) | Server only |

The FastAPI source was extracted from the supplied
`untangled-nexus-api-main.zip`. It is not a third backend. Both services can
use existing MongoDB collections where necessary, but public commerce routes
belong to Node and internal operations belong to FastAPI.

Do not package either backend or the Website into the Nexus EXE. The existing
App-only release workflow and PyInstaller specification remain in place.

## Local configuration

Run each process from its own directory so Python's `app` package and local
environment files resolve to the correct application.

1. Website backend: in `Backend/`, configure its existing environment and run
   `npm ci`, then `npm run dev`. The default Node port is 5001.
2. Website frontend: in `Website/`, run `npm ci`, then `npm run dev`.
   Browser requests use `/api`; Vite proxies them to `http://localhost:5001`.
   Set `WEBSITE_API_PROXY_TARGET` to another Node origin when needed. Do not
   append `/api` to this proxy target; the request path already contains it.
3. Nexus API: in `untangled-nexus-api-main/`, use a separate Python 3.12 virtual
   environment, install `requirements.txt`, configure server-side `MONGODB_URI`,
   and run `python -m uvicorn app.main:app --reload --port 10000`.
4. Nexus desktop: in `App/`, install its own `requirements.txt`. For local API
   development set `API_BASE_URL=http://localhost:10000`; for production use
   the dedicated Nexus API URL. Run `python main.py`.

The desktop's existing production default remains
`https://untangled-nexus-api.onrender.com`. `API_BASE_URL` remains supported.
MongoDB credentials must never be placed in the desktop environment or EXE.

## Production routing

- Deploy `Backend/` as the Website Node service with its existing start command.
- Deploy `untangled-nexus-api-main/` as a separate Python service. Use the
  commands in that project's README; set that directory as the service root
  when deploying from this combined repository.
- The production Website Node URL was not supplied. Confirm it before changing
  deployed routing. No production URL or deployment has been changed here.
- A production Website build with `VITE_API_URL=/api` requires the Website host
  to forward `/api` to Node. Vite's development proxy is not part of the static
  build. Alternatively, set `VITE_API_URL` to the confirmed Node origin plus
  `/api` at build time and allow the Website origin in Node's `CORS_ORIGINS`.
- `WEBSITE_API_PROXY_TARGET` affects development only and is not exposed as a
  `VITE_` client variable. It must point to Node, not the Nexus API.

## Desktop data boundary

The desktop runtime has no SQLite dependency and imports no MongoDB driver or
`bson` type. Quote and order reads, assignments, status changes, replies, and
director reviews all pass through authenticated FastAPI routes. A static test
guards this boundary against future database imports, connection calls, and
MongoDB credential keys.

The only in-memory data retained by the desktop is bounded UI/session state and
short-lived caches of successful API responses. Cached attendance is explicitly
marked stale after a refresh failure; business writes never fall back to a local
store.

## Compatibility during the staged migration

Node's existing routes, schemas, and alternative entry scripts are retained.
Their presence does not make Node the canonical Nexus backend. Do not switch
the desktop to Node to hide missing FastAPI endpoints.

FastAPI owns authenticated Nexus quote/order reads and internal workflow writes.
Preserve Node's public quote submission, tracking, orders, payment, product,
service, and catalogue functionality.

Phase 2 establishes the source and configuration boundary. It does not claim
that missing Nexus endpoints, role enforcement, UI freezes, leave/documents,
or staff rollout issues from Phase 1 are fixed. No legacy route is removed
until its callers and replacement behavior are verified.

## Verification

- Website: `npm run build` from `Website/`; verify the development proxy reaches
  the configured Node endpoint. There is no Website test script in this snapshot.
- Node: `npm test` and `npm run typecheck` from `Backend/`. Existing tests cover
  isolated quote rules, not production MongoDB or complete public routes.
- Desktop: `python -m pytest tests -q` from `App/` in its configured environment.
- Before rollout: verify real Website customer flows, authenticated Nexus
  operations, and the existing EXE installation/update workflow separately.
