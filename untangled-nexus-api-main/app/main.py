from __future__ import annotations

import time
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
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
from app.observability import record_request
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
logger = logging.getLogger("nexus.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")
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
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000
    route = getattr(request.scope.get("route"), "path", request.url.path)
    record_request(route, response.status_code, duration_ms, settings.slow_request_ms)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    event = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "route": route,
        "status": response.status_code,
        "duration_ms": round(duration_ms, 1),
        "slow": duration_ms >= settings.slow_request_ms,
    }
    logger.warning(json.dumps(event)) if event["slow"] else logger.info(json.dumps(event))
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and response.status_code < 500:
        audit_event = {
            "request_id": request_id,
            "method": request.method,
            "route": route,
            "status": response.status_code,
            "user_id": getattr(request.state, "user_id", None),
            "employee_id": getattr(request.state, "employee_id", None),
            "role": getattr(request.state, "role", None),
            "created_at": datetime.now(timezone.utc),
        }
        try:
            await get_db()["audit_events"].insert_one(audit_event)
        except Exception as exc:
            logger.error(json.dumps({"event": "audit_write_failed", "request_id": request_id, "error": type(exc).__name__}))
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
