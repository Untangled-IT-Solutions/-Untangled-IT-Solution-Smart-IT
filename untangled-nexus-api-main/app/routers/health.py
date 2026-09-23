from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.db import get_db
from app.observability import metrics_snapshot

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
async def health():
    return {"success": True, "status": "ok"}


@router.get("/ready")
@router.get("/api/ready")
async def ready():
    try:
        db = get_db()
        await db.command("ping")
        return {"success": True, "status": "ready", "mongo": True}
    except Exception as exc:
        return JSONResponse({"success": False, "status": "not_ready", "error": "Database unavailable."}, status_code=503)


@router.get("/api/metrics")
async def metrics(x_metrics_token: str = Header(default="")):
    expected = get_settings().metrics_token
    if expected and x_metrics_token != expected:
        raise HTTPException(401, "Invalid monitoring token.")
    return {"success": True, **metrics_snapshot()}


@router.head("/", include_in_schema=False)
@router.get("/")
async def root():
    return {
        "success": True,
        "service": "untangled-nexus-api",
        "runtime": "fastapi",
        "health": "/api/health",
    }
