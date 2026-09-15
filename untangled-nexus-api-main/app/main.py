from __future__ import annotations

import time
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from pymongo.errors import PyMongoError
from app.routers import users, documents, leave, calendar, office_requests, reports, projects
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import connect_db, close_db, get_db
from app.routers import (
    health,
    auth,
    dashboard,
    attendance,
    notifications,
    tasks,
    approvals,
    quotes,
    employees,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    async def expiry_monitor():
        while True:
            try:
                await documents.scan_document_expiry(get_db())
            except Exception as exc:
                print(f"Document expiry scan failed: {exc}")
            await asyncio.sleep(6 * 60 * 60)

    expiry_task = asyncio.create_task(expiry_monitor(), name='document-expiry-monitor')
    print("✅ MongoDB connected")
    print("🚀 Untangled Nexus API (FastAPI) ready")
    yield
    expiry_task.cancel()
    with suppress(asyncio.CancelledError):
        await expiry_task
    await close_db()


app = FastAPI(
    title="Untangled Nexus API",
    version="2.0.0",
    lifespan=lifespan,
)

settings = get_settings()
origins = [o.strip() for o in (settings.frontend_url or "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    # Log real path (not "/") so Render logs are useful
    print(
        {
            "method": request.method,
            "route": request.url.path,

            "status": response.status_code,
            "duration_ms": round(duration_ms, 1),
        }
    )
    return response


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(attendance.router)
app.include_router(notifications.router)
app.include_router(tasks.router)
app.include_router(approvals.router)
app.include_router(quotes.router)
app.include_router(employees.router)

for module in (users, documents, leave, calendar, office_requests, reports, projects):
    app.include_router(module.router)


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return JSONResponse({'success': False, 'error': str(exc.detail), 'detail': exc.detail}, status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Do not echo request bodies (passwords/documents) in validation errors.
    fields = ', '.join('.'.join(str(p) for p in e['loc']) for e in exc.errors())
    return JSONResponse({'success': False, 'error': 'Invalid request fields: ' + fields}, status_code=422)


@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    return JSONResponse({'success': False, 'error': 'Database unavailable. Please retry later.'}, status_code=503)
