# backend/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.routers.actions import router as actions_router
from backend.routers.auth import router as auth_router
from backend.routers.aws_accounts import router as aws_accounts_router
from backend.routers.baseline_report import router as baseline_report_router
from backend.routers.control_mappings import router as control_mappings_router
from backend.routers.control_plane import router as control_plane_router
from backend.routers.exceptions import router as exceptions_router
from backend.routers.exports import router as exports_router
from backend.routers.findings import router as findings_router
from backend.routers.internal import router as internal_router
from backend.routers.remediation_runs import router as remediation_runs_router
from backend.routers.saas_admin import router as saas_admin_router
from backend.routers.support_files import router as support_files_router
from backend.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan: startup and shutdown. Replaces deprecated on_event."""
    # Startup: placeholder for DB warm-up or caches if needed
    yield
    # Shutdown: cleanup if needed


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth_router, prefix="/api")
app.include_router(actions_router, prefix="/api")
app.include_router(aws_accounts_router, prefix="/api")
app.include_router(baseline_report_router, prefix="/api")
app.include_router(control_mappings_router, prefix="/api")
app.include_router(exceptions_router, prefix="/api")
app.include_router(exports_router, prefix="/api")
app.include_router(findings_router, prefix="/api")
app.include_router(control_plane_router, prefix="/api")
app.include_router(internal_router, prefix="/api")
app.include_router(remediation_runs_router, prefix="/api")
app.include_router(saas_admin_router, prefix="/api")
app.include_router(support_files_router, prefix="/api")
app.include_router(users_router, prefix="/api")


# Root
@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "docs": "/docs", "health": "/health"}


# Basic health check
@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
