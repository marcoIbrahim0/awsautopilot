# backend/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import AsyncSessionLocal
from backend.routers.actions import router as actions_router
from backend.routers.action_groups import router as action_groups_router
from backend.routers.audit_log import router as audit_log_router
from backend.routers.auth import router as auth_router
from backend.routers.aws_accounts import router as aws_accounts_router
from backend.routers.baseline_report import router as baseline_report_router
from backend.routers.control_mappings import router as control_mappings_router
from backend.routers.control_plane import router as control_plane_router
from backend.routers.exceptions import router as exceptions_router
from backend.routers.exports import router as exports_router
from backend.routers.findings import router as findings_router
from backend.routers.governance import router as governance_router
from backend.routers.help import router as help_router, saas_router as saas_help_router
from backend.routers.integrations import router as integrations_router
from backend.routers.internal import router as internal_router
from backend.routers.meta import router as meta_router
from backend.routers.notifications import router as notifications_router
from backend.routers.reconciliation import router as reconciliation_router
from backend.routers.remediation_runs import router as remediation_runs_router
from backend.routers.root_key_remediation_runs import router as root_key_remediation_runs_router
from backend.routers.saas_admin import router as saas_admin_router
from backend.routers.secret_migrations import router as secret_migrations_router
from backend.routers.support_files import router as support_files_router
from backend.routers.users import router as users_router
from backend.services.health_checks import build_readiness_report
from backend.services.help_center import ensure_help_articles_synced
from backend.services.migration_guard import assert_database_revision_at_head
from backend.services.account_trust import log_external_id_mismatch_audit_async


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: startup and shutdown. Replaces deprecated on_event."""
    assert_database_revision_at_head(component="api")
    async with AsyncSessionLocal() as session:
        await log_external_id_mismatch_audit_async(session)
        await ensure_help_articles_synced(session)
        await session.commit()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

_KNOWN_BROWSER_ORIGINS = {
    "https://dev.ocypheris.com",
    "https://ocypheris.com",
    "https://www.ocypheris.com",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}
_ALLOWED_CORS_ORIGINS = {
    *(origin.rstrip("/") for origin in settings.cors_origins_list),
    *(_KNOWN_BROWSER_ORIGINS),
}


def _set_explicit_cors_headers(request: Request, response: Response) -> Response:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin not in _ALLOWED_CORS_ORIGINS:
        return response

    vary = response.headers.get("Vary")
    if not vary:
        response.headers["Vary"] = "Origin"
    elif "Origin" not in {token.strip() for token in vary.split(",")}:
        response.headers["Vary"] = f"{vary}, Origin"

    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = request.headers.get(
        "access-control-request-method",
        "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
    )
    response.headers["Access-Control-Allow-Headers"] = request.headers.get(
        "access-control-request-headers",
        "*",
    )
    return response


@app.middleware("http")
async def explicit_cors_middleware(request: Request, call_next):
    if request.method == "OPTIONS" and request.headers.get("access-control-request-method"):
        response = Response(status_code=200)
    else:
        response = await call_next(request)
    return _set_explicit_cors_headers(request, response)

# Mount routers
app.include_router(auth_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(action_groups_router, prefix="/api")
app.include_router(audit_log_router, prefix="/api")
app.include_router(aws_accounts_router, prefix="/api")
app.include_router(baseline_report_router, prefix="/api")
app.include_router(control_mappings_router, prefix="/api")
app.include_router(exceptions_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(governance_router, prefix="/api")
app.include_router(help_router, prefix="/api")
app.include_router(integrations_router, prefix="/api")
app.include_router(control_plane_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(meta_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(reconciliation_router, prefix="/api")
app.include_router(remediation_runs_router, prefix="/api")
app.include_router(root_key_remediation_runs_router, prefix="/api")
app.include_router(saas_admin_router, prefix="/api")
app.include_router(saas_help_router, prefix="/api")
app.include_router(secret_migrations_router, prefix="/api")
app.include_router(support_files_router, prefix="/api")
app.include_router(users_router, prefix="/api")


# Root
@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "docs": "/docs", "health": "/health", "ready": "/ready"}


# Basic health check
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/ready")
@app.get("/health/ready")
async def ready():
    report = await build_readiness_report()
    status_code = 200 if report.get("ready") else 503
    return JSONResponse(status_code=status_code, content=report)
