"""
AWS Lambda entrypoint for the FastAPI app via API Gateway (HTTP API).

We run the DB revision guard at import time so it executes once per cold start.
Mangum lifespan is disabled so FastAPI's lifespan hook doesn't run per-invocation.
"""
from __future__ import annotations

from mangum import Mangum

from backend.main import app
from backend.services.migration_guard import assert_database_revision_at_head

# Fail fast on cold start if migrations are not applied.
assert_database_revision_at_head(component="api")

handler = Mangum(app, lifespan="off")

