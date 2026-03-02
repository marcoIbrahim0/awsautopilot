from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.action import Action
from backend.models.finding import Finding
from backend.models.enums import (
    RootKeyArtifactStatus,
    RootKeyDependencyStatus,
    RootKeyExternalTaskStatus,
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_external_task import RootKeyExternalTask
from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
from backend.models.root_key_remediation_event import RootKeyRemediationEvent
from backend.models.root_key_remediation_run import RootKeyRemediationRun

_SECRET_TOKENS = (
    "password",
    "secret",
    "token",
    "authorization",
    "access_key",
    "session_key",
)


def _require_non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _is_secret_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_secret_key(str(key)):
                redacted[str(key)] = "<REDACTED>"
            else:
                redacted[str(key)] = _sanitize_json(nested)
        return redacted
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


async def _get_run_by_idempotency_key(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    idempotency_key: str,
) -> RootKeyRemediationRun | None:
    result = await db.execute(
        select(RootKeyRemediationRun).where(
            RootKeyRemediationRun.tenant_id == tenant_id,
            RootKeyRemediationRun.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _require_tenant_scoped_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> RootKeyRemediationRun:
    run = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)
    if run is None:
        raise ValueError("root-key remediation run not found for tenant")
    return run


async def _require_tenant_scoped_action(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
) -> None:
    result = await db.execute(
        select(Action.id).where(
            Action.tenant_id == tenant_id,
            Action.id == action_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("root-key remediation action not found for tenant")


async def _require_tenant_scoped_finding(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    finding_id: uuid.UUID | None,
) -> None:
    if finding_id is None:
        return
    result = await db.execute(
        select(Finding.id).where(
            Finding.tenant_id == tenant_id,
            Finding.id == finding_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise ValueError("root-key remediation finding not found for tenant")


async def get_root_key_remediation_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> RootKeyRemediationRun | None:
    result = await db.execute(
        select(RootKeyRemediationRun).where(
            RootKeyRemediationRun.tenant_id == tenant_id,
            RootKeyRemediationRun.id == run_id,
        )
    )
    return result.scalar_one_or_none()


async def create_root_key_remediation_run_idempotent(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str | None,
    control_id: str,
    action_id: uuid.UUID,
    finding_id: uuid.UUID | None,
    strategy_id: str,
    mode: RootKeyRemediationMode,
    correlation_id: str,
    idempotency_key: str,
    actor_metadata: dict[str, Any] | None = None,
    state: RootKeyRemediationState = RootKeyRemediationState.discovery,
    status: RootKeyRemediationRunStatus = RootKeyRemediationRunStatus.queued,
    exception_expiry: datetime | None = None,
) -> tuple[RootKeyRemediationRun, bool]:
    normalized_idempotency_key = _require_non_empty(idempotency_key, field_name="idempotency_key")
    existing = await _get_run_by_idempotency_key(
        db,
        tenant_id=tenant_id,
        idempotency_key=normalized_idempotency_key,
    )
    if existing is not None:
        return existing, False

    await _require_tenant_scoped_action(db, tenant_id=tenant_id, action_id=action_id)
    await _require_tenant_scoped_finding(db, tenant_id=tenant_id, finding_id=finding_id)

    run = RootKeyRemediationRun(
        tenant_id=tenant_id,
        account_id=_require_non_empty(account_id, field_name="account_id"),
        region=_normalize_optional_text(region),
        control_id=_require_non_empty(control_id, field_name="control_id"),
        action_id=action_id,
        finding_id=finding_id,
        state=state,
        status=status,
        strategy_id=_require_non_empty(strategy_id, field_name="strategy_id"),
        mode=mode,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        idempotency_key=normalized_idempotency_key,
        actor_metadata=_sanitize_json(actor_metadata or {}),
        exception_expiry=exception_expiry,
        started_at=datetime.now(timezone.utc),
    )
    try:
        async with db.begin_nested():
            db.add(run)
            await db.flush()
    except IntegrityError:
        existing = await _get_run_by_idempotency_key(
            db,
            tenant_id=tenant_id,
            idempotency_key=normalized_idempotency_key,
        )
        if existing is None:
            raise
        return existing, False
    return run, True


async def transition_root_key_remediation_run_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    expected_lock_version: int,
    new_state: RootKeyRemediationState,
    new_status: RootKeyRemediationRunStatus,
    retry_increment: int = 0,
    rollback_reason: str | None = None,
    completed_at: datetime | None = None,
    exception_expiry: datetime | None = None,
) -> RootKeyRemediationRun | None:
    if retry_increment < 0:
        raise ValueError("retry_increment must be >= 0")

    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "state": new_state,
        "status": new_status,
        "updated_at": now,
        "rollback_reason": rollback_reason,
        "exception_expiry": exception_expiry,
        "lock_version": RootKeyRemediationRun.lock_version + 1,
    }
    if retry_increment > 0:
        values["retry_count"] = RootKeyRemediationRun.retry_count + retry_increment
    if completed_at is not None:
        values["completed_at"] = completed_at

    result = await db.execute(
        update(RootKeyRemediationRun)
        .where(
            RootKeyRemediationRun.tenant_id == tenant_id,
            RootKeyRemediationRun.id == run_id,
            RootKeyRemediationRun.lock_version == expected_lock_version,
        )
        .values(**values)
    )
    if int(result.rowcount or 0) == 0:
        return None
    return await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)


async def create_root_key_remediation_event_idempotent(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str | None,
    control_id: str,
    action_id: uuid.UUID | None,
    finding_id: uuid.UUID | None,
    state: RootKeyRemediationState,
    status: RootKeyRemediationRunStatus,
    strategy_id: str,
    mode: RootKeyRemediationMode,
    correlation_id: str,
    event_type: str,
    actor_metadata: dict[str, Any] | None = None,
    payload: dict[str, Any] | list[Any] | None = None,
    idempotency_key: str | None = None,
) -> tuple[RootKeyRemediationEvent, bool]:
    await _require_tenant_scoped_run(db, tenant_id=tenant_id, run_id=run_id)
    normalized_idempotency_key = _normalize_optional_text(idempotency_key)
    if normalized_idempotency_key:
        existing_result = await db.execute(
            select(RootKeyRemediationEvent).where(
                RootKeyRemediationEvent.tenant_id == tenant_id,
                RootKeyRemediationEvent.run_id == run_id,
                RootKeyRemediationEvent.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing, False

    event = RootKeyRemediationEvent(
        run_id=run_id,
        tenant_id=tenant_id,
        account_id=_require_non_empty(account_id, field_name="account_id"),
        region=_normalize_optional_text(region),
        control_id=_require_non_empty(control_id, field_name="control_id"),
        action_id=action_id,
        finding_id=finding_id,
        state=state,
        status=status,
        strategy_id=_require_non_empty(strategy_id, field_name="strategy_id"),
        mode=mode,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        event_type=_require_non_empty(event_type, field_name="event_type"),
        idempotency_key=normalized_idempotency_key,
        actor_metadata=_sanitize_json(actor_metadata or {}),
        payload=_sanitize_json(payload),
        started_at=datetime.now(timezone.utc),
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        if not normalized_idempotency_key:
            raise
        existing_result = await db.execute(
            select(RootKeyRemediationEvent).where(
                RootKeyRemediationEvent.tenant_id == tenant_id,
                RootKeyRemediationEvent.run_id == run_id,
                RootKeyRemediationEvent.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    return event, True


async def upsert_root_key_dependency_fingerprint(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str | None,
    control_id: str,
    action_id: uuid.UUID | None,
    finding_id: uuid.UUID | None,
    state: RootKeyRemediationState,
    status: RootKeyDependencyStatus,
    strategy_id: str,
    mode: RootKeyRemediationMode,
    correlation_id: str,
    fingerprint_type: str,
    fingerprint_hash: str,
    fingerprint_payload: dict[str, Any] | list[Any] | None = None,
    unknown_dependency: bool = False,
    unknown_reason: str | None = None,
    actor_metadata: dict[str, Any] | None = None,
) -> tuple[RootKeyDependencyFingerprint, bool]:
    await _require_tenant_scoped_run(db, tenant_id=tenant_id, run_id=run_id)
    normalized_fingerprint_type = _require_non_empty(fingerprint_type, field_name="fingerprint_type")
    normalized_fingerprint_hash = _require_non_empty(fingerprint_hash, field_name="fingerprint_hash")

    existing_result = await db.execute(
        select(RootKeyDependencyFingerprint).where(
            RootKeyDependencyFingerprint.tenant_id == tenant_id,
            RootKeyDependencyFingerprint.run_id == run_id,
            RootKeyDependencyFingerprint.fingerprint_type == normalized_fingerprint_type,
            RootKeyDependencyFingerprint.fingerprint_hash == normalized_fingerprint_hash,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        existing.state = state
        existing.status = status
        existing.unknown_dependency = bool(unknown_dependency)
        existing.unknown_reason = unknown_reason
        existing.fingerprint_payload = _sanitize_json(fingerprint_payload)
        existing.actor_metadata = _sanitize_json(actor_metadata or {})
        return existing, False

    fingerprint = RootKeyDependencyFingerprint(
        run_id=run_id,
        tenant_id=tenant_id,
        account_id=_require_non_empty(account_id, field_name="account_id"),
        region=_normalize_optional_text(region),
        control_id=_require_non_empty(control_id, field_name="control_id"),
        action_id=action_id,
        finding_id=finding_id,
        state=state,
        status=status,
        strategy_id=_require_non_empty(strategy_id, field_name="strategy_id"),
        mode=mode,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        fingerprint_type=normalized_fingerprint_type,
        fingerprint_hash=normalized_fingerprint_hash,
        fingerprint_payload=_sanitize_json(fingerprint_payload),
        unknown_dependency=bool(unknown_dependency),
        unknown_reason=unknown_reason,
        actor_metadata=_sanitize_json(actor_metadata or {}),
    )
    try:
        async with db.begin_nested():
            db.add(fingerprint)
            await db.flush()
    except IntegrityError:
        existing_result = await db.execute(
            select(RootKeyDependencyFingerprint).where(
                RootKeyDependencyFingerprint.tenant_id == tenant_id,
                RootKeyDependencyFingerprint.run_id == run_id,
                RootKeyDependencyFingerprint.fingerprint_type == normalized_fingerprint_type,
                RootKeyDependencyFingerprint.fingerprint_hash == normalized_fingerprint_hash,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is None:
            raise
        existing.state = state
        existing.status = status
        existing.unknown_dependency = bool(unknown_dependency)
        existing.unknown_reason = unknown_reason
        existing.fingerprint_payload = _sanitize_json(fingerprint_payload)
        existing.actor_metadata = _sanitize_json(actor_metadata or {})
        return existing, False
    return fingerprint, True


async def create_root_key_remediation_artifact_idempotent(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str | None,
    control_id: str,
    action_id: uuid.UUID | None,
    finding_id: uuid.UUID | None,
    state: RootKeyRemediationState,
    status: RootKeyArtifactStatus,
    strategy_id: str,
    mode: RootKeyRemediationMode,
    correlation_id: str,
    artifact_type: str,
    metadata_json: dict[str, Any] | list[Any] | None = None,
    artifact_ref: str | None = None,
    artifact_sha256: str | None = None,
    idempotency_key: str | None = None,
    redaction_applied: bool = True,
    actor_metadata: dict[str, Any] | None = None,
) -> tuple[RootKeyRemediationArtifact, bool]:
    await _require_tenant_scoped_run(db, tenant_id=tenant_id, run_id=run_id)
    normalized_idempotency_key = _normalize_optional_text(idempotency_key)
    if normalized_idempotency_key:
        existing_result = await db.execute(
            select(RootKeyRemediationArtifact).where(
                RootKeyRemediationArtifact.tenant_id == tenant_id,
                RootKeyRemediationArtifact.run_id == run_id,
                RootKeyRemediationArtifact.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing, False

    artifact = RootKeyRemediationArtifact(
        run_id=run_id,
        tenant_id=tenant_id,
        account_id=_require_non_empty(account_id, field_name="account_id"),
        region=_normalize_optional_text(region),
        control_id=_require_non_empty(control_id, field_name="control_id"),
        action_id=action_id,
        finding_id=finding_id,
        state=state,
        status=status,
        strategy_id=_require_non_empty(strategy_id, field_name="strategy_id"),
        mode=mode,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        artifact_type=_require_non_empty(artifact_type, field_name="artifact_type"),
        artifact_ref=_normalize_optional_text(artifact_ref),
        artifact_sha256=_normalize_optional_text(artifact_sha256),
        metadata_json=_sanitize_json(metadata_json),
        idempotency_key=normalized_idempotency_key,
        redaction_applied=bool(redaction_applied),
        actor_metadata=_sanitize_json(actor_metadata or {}),
        started_at=datetime.now(timezone.utc),
    )
    try:
        async with db.begin_nested():
            db.add(artifact)
            await db.flush()
    except IntegrityError:
        if not normalized_idempotency_key:
            raise
        existing_result = await db.execute(
            select(RootKeyRemediationArtifact).where(
                RootKeyRemediationArtifact.tenant_id == tenant_id,
                RootKeyRemediationArtifact.run_id == run_id,
                RootKeyRemediationArtifact.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    return artifact, True


async def create_root_key_external_task_idempotent(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    account_id: str,
    region: str | None,
    control_id: str,
    action_id: uuid.UUID | None,
    finding_id: uuid.UUID | None,
    state: RootKeyRemediationState,
    status: RootKeyExternalTaskStatus,
    strategy_id: str,
    mode: RootKeyRemediationMode,
    correlation_id: str,
    task_type: str,
    task_payload: dict[str, Any] | list[Any] | None = None,
    idempotency_key: str | None = None,
    due_at: datetime | None = None,
    assigned_to_user_id: uuid.UUID | None = None,
    actor_metadata: dict[str, Any] | None = None,
) -> tuple[RootKeyExternalTask, bool]:
    await _require_tenant_scoped_run(db, tenant_id=tenant_id, run_id=run_id)
    normalized_idempotency_key = _normalize_optional_text(idempotency_key)
    if normalized_idempotency_key:
        existing_result = await db.execute(
            select(RootKeyExternalTask).where(
                RootKeyExternalTask.tenant_id == tenant_id,
                RootKeyExternalTask.run_id == run_id,
                RootKeyExternalTask.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing, False

    task = RootKeyExternalTask(
        run_id=run_id,
        tenant_id=tenant_id,
        account_id=_require_non_empty(account_id, field_name="account_id"),
        region=_normalize_optional_text(region),
        control_id=_require_non_empty(control_id, field_name="control_id"),
        action_id=action_id,
        finding_id=finding_id,
        state=state,
        status=status,
        strategy_id=_require_non_empty(strategy_id, field_name="strategy_id"),
        mode=mode,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        task_type=_require_non_empty(task_type, field_name="task_type"),
        task_payload=_sanitize_json(task_payload),
        idempotency_key=normalized_idempotency_key,
        due_at=due_at,
        assigned_to_user_id=assigned_to_user_id,
        actor_metadata=_sanitize_json(actor_metadata or {}),
        started_at=datetime.now(timezone.utc),
    )
    try:
        async with db.begin_nested():
            db.add(task)
            await db.flush()
    except IntegrityError:
        if not normalized_idempotency_key:
            raise
        existing_result = await db.execute(
            select(RootKeyExternalTask).where(
                RootKeyExternalTask.tenant_id == tenant_id,
                RootKeyExternalTask.run_id == run_id,
                RootKeyExternalTask.idempotency_key == normalized_idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is None:
            raise
        return existing, False
    return task, True
