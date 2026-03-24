"""Worker job for refreshing materialized shared attack paths."""
from __future__ import annotations

import asyncio
import logging
import uuid

from backend.database import build_async_session_factory
from backend.services.attack_path_materialized import materialize_attack_paths

logger = logging.getLogger("worker.jobs.attack_path_materialization")


def execute_attack_path_materialization_job(job: dict) -> None:
    tenant_id_str = job.get("tenant_id")
    if not tenant_id_str:
        raise ValueError("job missing tenant_id")
    try:
        tenant_id = uuid.UUID(str(tenant_id_str))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid tenant_id: {tenant_id_str}") from exc

    account_id = str(job.get("account_id") or "").strip() or None
    region = str(job.get("region") or "").strip() or None
    result = asyncio.run(_run_refresh(tenant_id=tenant_id, account_id=account_id, region=region))
    logger.info(
        "attack_path_materialization complete tenant_id=%s account_id=%s region=%s paths=%s actions=%s latency_ms=%s",
        tenant_id,
        account_id,
        region,
        result.get("paths_materialized"),
        result.get("actions_scanned"),
        result.get("latency_ms"),
    )


async def _run_refresh(*, tenant_id: uuid.UUID, account_id: str | None, region: str | None) -> dict:
    engine, session_factory = build_async_session_factory(isolated=True)
    try:
        async with session_factory() as session:
            result = await materialize_attack_paths(session, tenant_id=tenant_id, account_id=account_id, region=region)
            await session.commit()
            return result
    finally:
        await engine.dispose()
