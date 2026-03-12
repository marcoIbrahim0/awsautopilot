from __future__ import annotations

import logging
import uuid

from backend.services.integration_adapters import IntegrationAdapterError, ProviderSyncResult, sync_provider_item
from backend.services.integration_sync import (
    complete_sync_task,
    fail_sync_task,
    get_sync_runtime,
    get_sync_task,
    mark_sync_task_running,
)
from backend.workers.database import get_session

logger = logging.getLogger("worker.jobs.integration_sync")


def execute_integration_sync_job(job: dict) -> None:
    task_id = _parse_uuid(job.get("task_id"), field_name="task_id")
    tenant_id = _parse_uuid(job.get("tenant_id"), field_name="tenant_id")
    session = get_session()
    try:
        task = _require_task(session=session, tenant_id=tenant_id, task_id=task_id)
        if task.status == "success":
            logger.info("integration_sync idempotent skip task_id=%s", task_id)
            return
        setting, _link = get_sync_runtime(session, task=task)
        mark_sync_task_running(session, task)
        session.commit()
        result = sync_provider_item(
            provider=task.provider,
            config=_dict(setting.config_json),
            secret=_dict(setting.secret_json),
            payload=_dict(task.payload_json),
        )
        task = _require_task(session=session, tenant_id=tenant_id, task_id=task_id)
        link = complete_sync_task(session, task=task, result=_result_dict(result))
        session.commit()
        logger.info("integration_sync completed task_id=%s provider=%s external_id=%s", task_id, task.provider, link.external_id)
    except IntegrationAdapterError as exc:
        _persist_failure(session=session, tenant_id=tenant_id, task_id=task_id, message=str(exc))
        if exc.retryable:
            raise RuntimeError(str(exc)) from exc
    except ValueError as exc:
        _persist_failure(session=session, tenant_id=tenant_id, task_id=task_id, message=str(exc))
    except Exception as exc:
        _persist_failure(session=session, tenant_id=tenant_id, task_id=task_id, message=str(exc))
        raise
    finally:
        session.close()


def _parse_uuid(value: object, *, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValueError(f"invalid {field_name}: {value}") from exc


def _require_task(*, session, tenant_id: uuid.UUID, task_id: uuid.UUID):
    task = get_sync_task(session, tenant_id=tenant_id, task_id=task_id)
    if task is None:
        raise ValueError(f"integration sync task not found: {task_id}")
    return task


def _persist_failure(*, session, tenant_id: uuid.UUID, task_id: uuid.UUID, message: str) -> None:
    session.rollback()
    task = get_sync_task(session, tenant_id=tenant_id, task_id=task_id)
    if task is None:
        return
    fail_sync_task(session, task=task, message=message)
    session.commit()


def _result_dict(result: ProviderSyncResult) -> dict[str, object]:
    return {
        "external_id": result.external_id,
        "external_key": result.external_key,
        "external_url": result.external_url,
        "external_status": result.external_status,
        "external_assignee_key": result.external_assignee_key,
        "external_assignee_label": result.external_assignee_label,
        "metadata": result.metadata or {},
    }


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}
