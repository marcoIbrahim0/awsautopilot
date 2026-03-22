"""
AWS Lambda entrypoint for the FastAPI app via API Gateway (HTTP API).

Mangum lifespan is disabled so FastAPI's lifespan hook doesn't run per-invocation.
The FastAPI app bootstrap and DB revision guard are memoized on first invoke so
the Lambda init phase stays lean.
"""
from __future__ import annotations

from importlib import import_module
import logging
from threading import Lock
from time import perf_counter

from mangum import Mangum

logger = logging.getLogger("api.lambda")
_IMPORT_STARTED_AT = perf_counter()
_RUNTIME_LOCK = Lock()
_MANGUM_HANDLER: Mangum | None = None
_DB_GUARD_READY = False

logger.info("API Lambda module import completed in %.3fs", perf_counter() - _IMPORT_STARTED_AT)


def _build_mangum_handler() -> Mangum:
    started_at = perf_counter()
    app_module = import_module("backend.main")
    handler = Mangum(app_module.app, lifespan="off")
    logger.info("API Lambda runtime bootstrap completed in %.3fs", perf_counter() - started_at)
    return handler


def _assert_database_revision_at_head() -> None:
    migration_guard = import_module("backend.services.migration_guard")
    migration_guard.assert_database_revision_at_head(component="api")


def _ensure_runtime_ready() -> Mangum:
    global _DB_GUARD_READY, _MANGUM_HANDLER
    handler = _MANGUM_HANDLER
    if handler is not None and _DB_GUARD_READY:
        return handler

    bootstrap_started_at = perf_counter()
    with _RUNTIME_LOCK:
        handler = _MANGUM_HANDLER
        if handler is None:
            handler = _build_mangum_handler()
            _MANGUM_HANDLER = handler
        if not _DB_GUARD_READY:
            guard_started_at = perf_counter()
            _assert_database_revision_at_head()
            _DB_GUARD_READY = True
            logger.info(
                "API Lambda database guard completed in %.3fs",
                perf_counter() - guard_started_at,
            )
    logger.info(
        "API Lambda first-invoke readiness completed in %.3fs",
        perf_counter() - bootstrap_started_at,
    )
    return handler


def _ensure_database_guard_ready() -> None:
    global _DB_GUARD_READY
    if _DB_GUARD_READY:
        return
    _ensure_runtime_ready()


def handler(event, context):
    runtime_handler = _ensure_runtime_ready()
    return runtime_handler(event, context)
