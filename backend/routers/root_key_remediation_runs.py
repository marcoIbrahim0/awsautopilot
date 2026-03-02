from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.auth import get_optional_user
from backend.config import settings
from backend.database import get_db
from backend.models.action import Action
from backend.models.finding import Finding
from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_external_task import RootKeyExternalTask
from backend.models.root_key_remediation_run import RootKeyRemediationRun
from backend.models.user import User
from backend.models.enums import RootKeyExternalTaskStatus, RootKeyRemediationMode
from backend.services.root_key_remediation_state_machine import (
    RootKeyRemediationStateMachineService,
    RootKeyStateMachineError,
)
from backend.services.root_key_remediation_executor_worker import (
    RootKeyRemediationExecutorWorker,
)
from backend.services.root_key_remediation_store import (
    create_root_key_remediation_event_idempotent,
)

router = APIRouter(prefix="/root-key-remediation-runs", tags=["root-key-remediation-runs"])

ROOT_KEY_ACTION_TYPE = "iam_root_access_key_absent"
ROOT_KEY_CONTRACT_VERSION = "2026-03-02"
_IDEMPOTENCY_MAX_LEN = 128
_SUPPORTED_STRATEGIES = {"iam_root_key_disable", "iam_root_key_delete"}
_SECRET_TOKENS = (
    "password",
    "secret",
    "token",
    "authorization",
    "access_key",
    "session_key",
)


class RootKeyError(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable failure message.")
    retryable: bool = Field(False, description="Whether retrying the same request can succeed.")
    details: dict[str, Any] | None = Field(None, description="Optional non-secret diagnostics.")


class RootKeyErrorResponse(BaseModel):
    correlation_id: str = Field(..., description="Request correlation identifier.")
    contract_version: str = Field(..., description="Root-key API contract version.")
    error: RootKeyError


class RootKeyCreateRunRequest(BaseModel):
    action_id: str = Field(..., description="Tenant-scoped action UUID for iam_root_access_key_absent.")
    finding_id: str | None = Field(default=None, description="Optional tenant-scoped finding UUID.")
    strategy_id: str = Field(default="iam_root_key_disable", description="Root-key strategy identifier.")
    mode: str = Field(default="manual", description="Execution mode: auto or manual.")
    actor_metadata: dict[str, Any] | None = Field(default=None, description="Optional non-secret actor metadata.")


class RootKeyRollbackRequest(BaseModel):
    reason: str | None = Field(default=None, description="Optional rollback reason.")
    actor_metadata: dict[str, Any] | None = Field(default=None, description="Optional non-secret actor metadata.")


class RootKeyExternalTaskCompleteRequest(BaseModel):
    result: dict[str, Any] | list[Any] | None = Field(default=None, description="Optional completion result payload.")
    actor_metadata: dict[str, Any] | None = Field(default=None, description="Optional non-secret actor metadata.")


class RootKeyRunSnapshot(BaseModel):
    id: str
    account_id: str
    region: str | None
    control_id: str
    action_id: str
    finding_id: str | None
    state: str
    status: str
    strategy_id: str
    mode: str
    run_correlation_id: str
    retry_count: int
    lock_version: int
    rollback_reason: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class RootKeyExternalTaskSnapshot(BaseModel):
    id: str
    run_id: str
    task_type: str
    status: str
    due_at: str | None
    completed_at: str | None
    assigned_to_user_id: str | None
    retry_count: int
    rollback_reason: str | None
    created_at: str
    updated_at: str


class RootKeyDependencySnapshot(BaseModel):
    id: str
    run_id: str
    fingerprint_type: str
    fingerprint_hash: str
    status: str
    unknown_dependency: bool
    unknown_reason: str | None
    fingerprint_payload: dict[str, Any] | list[Any] | None
    created_at: str
    updated_at: str


class RootKeyEventSnapshot(BaseModel):
    id: str
    run_id: str
    event_type: str
    state: str
    status: str
    rollback_reason: str | None
    created_at: str
    completed_at: str | None


class RootKeyArtifactSnapshot(BaseModel):
    id: str
    run_id: str
    artifact_type: str
    state: str
    status: str
    artifact_ref: str | None
    artifact_sha256: str | None
    redaction_applied: bool
    created_at: str
    completed_at: str | None


class RootKeyRunResponse(BaseModel):
    correlation_id: str
    contract_version: str
    idempotency_replayed: bool
    run: RootKeyRunSnapshot


class RootKeyRunDetailResponse(BaseModel):
    correlation_id: str
    contract_version: str
    run: RootKeyRunSnapshot
    external_tasks: list[RootKeyExternalTaskSnapshot]
    dependencies: list[RootKeyDependencySnapshot]
    events: list[RootKeyEventSnapshot]
    artifacts: list[RootKeyArtifactSnapshot]
    event_count: int
    dependency_count: int
    artifact_count: int


class RootKeyExternalTaskCompleteResponse(BaseModel):
    correlation_id: str
    contract_version: str
    idempotency_replayed: bool
    run: RootKeyRunSnapshot
    task: RootKeyExternalTaskSnapshot


def _new_correlation_id(correlation_header: str | None) -> str:
    value = (correlation_header or "").strip()
    return value or uuid.uuid4().hex


def _set_common_headers(response: Response, *, correlation_id: str) -> None:
    response.headers["X-Correlation-Id"] = correlation_id
    response.headers["X-Root-Key-Contract-Version"] = ROOT_KEY_CONTRACT_VERSION


def _is_api_enabled() -> bool:
    return bool(
        settings.ROOT_KEY_SAFE_REMEDIATION_ENABLED
        and settings.ROOT_KEY_SAFE_REMEDIATION_API_ENABLED
        and settings.ROOT_KEY_SAFE_REMEDIATION_STRICT_TRANSITIONS
    )


def _use_executor_worker() -> bool:
    return bool(getattr(settings, "ROOT_KEY_SAFE_REMEDIATION_EXECUTOR_ENABLED", False))


def _error_response(
    *,
    correlation_id: str,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = RootKeyErrorResponse(
        correlation_id=correlation_id,
        contract_version=ROOT_KEY_CONTRACT_VERSION,
        error=RootKeyError(
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
        headers={
            "X-Correlation-Id": correlation_id,
            "X-Root-Key-Contract-Version": ROOT_KEY_CONTRACT_VERSION,
        },
    )


def _validate_contract_header(
    *,
    contract_version_header: str | None,
    correlation_id: str,
) -> JSONResponse | None:
    normalized = (contract_version_header or "").strip()
    if not normalized or normalized == ROOT_KEY_CONTRACT_VERSION:
        return None
    return _error_response(
        correlation_id=correlation_id,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="unsupported_contract_version",
        message=(
            "Unsupported root-key contract version. "
            f"Expected {ROOT_KEY_CONTRACT_VERSION}."
        ),
        details={"requested_version": normalized},
    )


def _require_idempotency_key(
    *,
    idempotency_key_header: str | None,
    correlation_id: str,
) -> tuple[str | None, JSONResponse | None]:
    normalized = (idempotency_key_header or "").strip()
    if not normalized:
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="idempotency_key_required",
            message="Idempotency-Key header is required for this endpoint.",
        )
    if len(normalized) > _IDEMPOTENCY_MAX_LEN:
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="idempotency_key_too_long",
            message=f"Idempotency-Key must be <= {_IDEMPOTENCY_MAX_LEN} characters.",
        )
    return normalized, None


def _transition_id(prefix: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}"


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _run_snapshot(run: RootKeyRemediationRun) -> RootKeyRunSnapshot:
    return RootKeyRunSnapshot(
        id=str(run.id),
        account_id=run.account_id,
        region=run.region,
        control_id=run.control_id,
        action_id=str(run.action_id),
        finding_id=str(run.finding_id) if run.finding_id else None,
        state=_enum_value(run.state),
        status=_enum_value(run.status),
        strategy_id=run.strategy_id,
        mode=_enum_value(run.mode),
        run_correlation_id=run.correlation_id,
        retry_count=int(run.retry_count),
        lock_version=int(run.lock_version),
        rollback_reason=run.rollback_reason,
        started_at=_iso(run.started_at),
        completed_at=_iso(run.completed_at),
        created_at=_iso(run.created_at) or "",
        updated_at=_iso(run.updated_at) or "",
    )


def _task_snapshot(task: RootKeyExternalTask) -> RootKeyExternalTaskSnapshot:
    return RootKeyExternalTaskSnapshot(
        id=str(task.id),
        run_id=str(task.run_id),
        task_type=task.task_type,
        status=_enum_value(task.status),
        due_at=_iso(task.due_at),
        completed_at=_iso(task.completed_at),
        assigned_to_user_id=str(task.assigned_to_user_id) if task.assigned_to_user_id else None,
        retry_count=int(task.retry_count),
        rollback_reason=task.rollback_reason,
        created_at=_iso(task.created_at) or "",
        updated_at=_iso(task.updated_at) or "",
    )


def _dependency_snapshot(
    dependency: RootKeyDependencyFingerprint,
) -> RootKeyDependencySnapshot:
    return RootKeyDependencySnapshot(
        id=str(dependency.id),
        run_id=str(dependency.run_id),
        fingerprint_type=dependency.fingerprint_type,
        fingerprint_hash=dependency.fingerprint_hash,
        status=_enum_value(dependency.status),
        unknown_dependency=bool(dependency.unknown_dependency),
        unknown_reason=dependency.unknown_reason,
        fingerprint_payload=dependency.fingerprint_payload,
        created_at=_iso(dependency.created_at) or "",
        updated_at=_iso(dependency.updated_at) or "",
    )


def _event_snapshot(event: Any) -> RootKeyEventSnapshot:
    return RootKeyEventSnapshot(
        id=str(event.id),
        run_id=str(event.run_id),
        event_type=event.event_type,
        state=_enum_value(event.state),
        status=_enum_value(event.status),
        rollback_reason=event.rollback_reason,
        created_at=_iso(event.created_at) or "",
        completed_at=_iso(event.completed_at),
    )


def _artifact_snapshot(artifact: Any) -> RootKeyArtifactSnapshot:
    return RootKeyArtifactSnapshot(
        id=str(artifact.id),
        run_id=str(artifact.run_id),
        artifact_type=artifact.artifact_type,
        state=_enum_value(artifact.state),
        status=_enum_value(artifact.status),
        artifact_ref=artifact.artifact_ref,
        artifact_sha256=artifact.artifact_sha256,
        redaction_applied=bool(artifact.redaction_applied),
        created_at=_iso(artifact.created_at) or "",
        completed_at=_iso(artifact.completed_at),
    )


def _parse_uuid(
    value: str,
    *,
    field_name: str,
    correlation_id: str,
) -> tuple[uuid.UUID | None, JSONResponse | None]:
    try:
        return uuid.UUID(value), None
    except ValueError:
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code=f"invalid_{field_name}",
            message=f"{field_name} must be a valid UUID.",
        )


def _parse_mode(
    mode: str,
    *,
    correlation_id: str,
) -> tuple[RootKeyRemediationMode | None, JSONResponse | None]:
    normalized = (mode or "").strip().lower()
    if normalized == RootKeyRemediationMode.auto.value:
        return RootKeyRemediationMode.auto, None
    if normalized == RootKeyRemediationMode.manual.value:
        return RootKeyRemediationMode.manual, None
    return None, _error_response(
        correlation_id=correlation_id,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_mode",
        message="mode must be one of: auto, manual.",
    )


def _normalize_strategy_id(
    strategy_id: str,
    *,
    correlation_id: str,
) -> tuple[str | None, JSONResponse | None]:
    normalized = (strategy_id or "").strip()
    if normalized in _SUPPORTED_STRATEGIES:
        return normalized, None
    return None, _error_response(
        correlation_id=correlation_id,
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_strategy_id",
        message=f"strategy_id must be one of: {', '.join(sorted(_SUPPORTED_STRATEGIES))}.",
    )


def _actor_metadata_from_user(user: User, provided: dict[str, Any] | None) -> dict[str, Any]:
    role = getattr(getattr(user, "role", None), "value", getattr(user, "role", "member"))
    metadata = {
        "actor_type": "user",
        "actor_user_id": str(user.id),
        "actor_role": str(role),
    }
    if provided:
        metadata["request_metadata"] = _sanitize_json(provided)
    return metadata


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


async def _safe_rollback(db: AsyncSession) -> None:
    try:
        await db.rollback()
    except Exception:
        return


def _status_code_for_state_machine_error(exc: RootKeyStateMachineError) -> int:
    code = exc.classification.code
    if code in {"feature_flag_disabled", "tenant_scope_violation"}:
        return status.HTTP_404_NOT_FOUND
    if code in {"illegal_transition", "idempotency_payload_mismatch"}:
        return status.HTTP_409_CONFLICT
    if code in {"delete_window_disabled", "transition_cancelled"}:
        return status.HTTP_409_CONFLICT
    if exc.classification.is_retryable:
        return status.HTTP_409_CONFLICT
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _state_machine_error_response(
    *,
    correlation_id: str,
    exc: RootKeyStateMachineError,
) -> JSONResponse:
    return _error_response(
        correlation_id=correlation_id,
        status_code=_status_code_for_state_machine_error(exc),
        code=exc.classification.code,
        message=exc.classification.message,
        retryable=exc.classification.is_retryable,
    )


async def _load_tenant_run_with_children(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> RootKeyRemediationRun | None:
    result = await db.execute(
        select(RootKeyRemediationRun)
        .options(
            selectinload(RootKeyRemediationRun.external_tasks),
            selectinload(RootKeyRemediationRun.dependency_fingerprints),
            selectinload(RootKeyRemediationRun.events),
            selectinload(RootKeyRemediationRun.artifacts),
        )
        .where(
            RootKeyRemediationRun.tenant_id == tenant_id,
            RootKeyRemediationRun.id == run_id,
        )
    )
    return result.scalar_one_or_none()


async def _load_tenant_external_task(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    task_id: uuid.UUID,
) -> RootKeyExternalTask | None:
    result = await db.execute(
        select(RootKeyExternalTask).where(
            RootKeyExternalTask.tenant_id == tenant_id,
            RootKeyExternalTask.run_id == run_id,
            RootKeyExternalTask.id == task_id,
        )
    )
    return result.scalar_one_or_none()


def _mutating_preflight(
    *,
    correlation_id: str,
    current_user: User | None,
    idempotency_key_header: str | None,
) -> tuple[uuid.UUID | None, str | None, JSONResponse | None]:
    if not _is_api_enabled():
        return None, None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Root-key remediation API is disabled.",
        )
    if current_user is None:
        return None, None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="not_authenticated",
            message="Authentication is required.",
        )
    idempotency_key, idempotency_err = _require_idempotency_key(
        idempotency_key_header=idempotency_key_header,
        correlation_id=correlation_id,
    )
    if idempotency_err is not None:
        return None, None, idempotency_err
    return current_user.tenant_id, idempotency_key, None


def _readonly_preflight(
    *,
    correlation_id: str,
    current_user: User | None,
) -> tuple[uuid.UUID | None, JSONResponse | None]:
    if not _is_api_enabled():
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Root-key remediation API is disabled.",
        )
    if current_user is None:
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="not_authenticated",
            message="Authentication is required.",
        )
    return current_user.tenant_id, None


@router.post(
    "",
    response_model=RootKeyRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create root-key remediation run",
    responses={
        200: {"model": RootKeyRunResponse, "description": "Idempotent replay"},
        400: {"model": RootKeyErrorResponse},
        401: {"model": RootKeyErrorResponse},
        404: {"model": RootKeyErrorResponse},
        409: {"model": RootKeyErrorResponse},
        500: {"model": RootKeyErrorResponse},
    },
)
async def create_root_key_remediation_run(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    body: RootKeyCreateRunRequest = Body(...),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(
        contract_version_header=contract_version_header,
        correlation_id=correlation_id,
    )
    if contract_err is not None:
        return contract_err
    tenant_id, idempotency_key, preflight_err = _mutating_preflight(
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert idempotency_key is not None
    action_uuid, action_uuid_err = _parse_uuid(
        body.action_id,
        field_name="action_id",
        correlation_id=correlation_id,
    )
    if action_uuid_err is not None:
        return action_uuid_err
    action_result = await db.execute(
        select(Action).where(
            Action.id == action_uuid,
            Action.tenant_id == tenant_id,
            Action.action_type == ROOT_KEY_ACTION_TYPE,
        )
    )
    action = action_result.scalar_one_or_none()
    if action is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="action_not_found",
            message="Root-key remediation action not found in tenant scope.",
        )
    mode, mode_err = _parse_mode(body.mode, correlation_id=correlation_id)
    if mode_err is not None:
        return mode_err
    if mode == RootKeyRemediationMode.auto and not settings.ROOT_KEY_SAFE_REMEDIATION_AUTO_ENABLED:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_409_CONFLICT,
            code="auto_mode_disabled",
            message="Auto mode is disabled by feature flags.",
        )
    strategy_id, strategy_err = _normalize_strategy_id(
        body.strategy_id,
        correlation_id=correlation_id,
    )
    if strategy_err is not None:
        return strategy_err
    finding_uuid: uuid.UUID | None = None
    if body.finding_id:
        finding_uuid, finding_uuid_err = _parse_uuid(
            body.finding_id,
            field_name="finding_id",
            correlation_id=correlation_id,
        )
        if finding_uuid_err is not None:
            return finding_uuid_err
        finding_result = await db.execute(
            select(Finding).where(
                Finding.id == finding_uuid,
                Finding.tenant_id == tenant_id,
                Finding.account_id == action.account_id,
            )
        )
        if finding_result.scalar_one_or_none() is None:
            return _error_response(
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND,
                code="finding_not_found",
                message="Finding not found in tenant/account scope.",
            )
    service = RootKeyRemediationStateMachineService()
    actor_metadata = _actor_metadata_from_user(current_user, body.actor_metadata)
    try:
        create_result = await service.create_run(
            db,
            tenant_id=tenant_id,
            account_id=action.account_id,
            region=action.region,
            control_id=action.control_id or "IAM.4",
            action_id=action.id,
            finding_id=finding_uuid,
            strategy_id=strategy_id,
            mode=mode,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )
        run = create_result.run
        if _enum_value(run.state) in {"discovery", "needs_attention"}:
            migration_id = _transition_id("create_migration", idempotency_key)
            migration_result = await service.advance_to_migration(
                db,
                tenant_id=tenant_id,
                run_id=run.id,
                transition_id=migration_id,
                actor_metadata=actor_metadata,
            )
            run = migration_result.run
        await db.commit()
    except RootKeyStateMachineError as exc:
        await _safe_rollback(db)
        return _state_machine_error_response(correlation_id=correlation_id, exc=exc)
    except Exception:
        await _safe_rollback(db)
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Unexpected server error while creating root-key remediation run.",
        )
    _set_common_headers(response, correlation_id=correlation_id)
    payload = RootKeyRunResponse(
        correlation_id=correlation_id,
        contract_version=ROOT_KEY_CONTRACT_VERSION,
        idempotency_replayed=not create_result.state_changed,
        run=_run_snapshot(run),
    )
    if create_result.state_changed:
        return payload
    response.status_code = status.HTTP_200_OK
    return payload


@router.get(
    "/{run_id}",
    response_model=RootKeyRunDetailResponse,
    summary="Get root-key remediation run",
    responses={
        400: {"model": RootKeyErrorResponse},
        401: {"model": RootKeyErrorResponse},
        404: {"model": RootKeyErrorResponse},
    },
)
async def get_root_key_remediation_run(
    run_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunDetailResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(
        contract_version_header=contract_version_header,
        correlation_id=correlation_id,
    )
    if contract_err is not None:
        return contract_err
    tenant_id, preflight_err = _readonly_preflight(
        correlation_id=correlation_id,
        current_user=current_user,
    )
    if preflight_err is not None:
        return preflight_err
    run_uuid, run_uuid_err = _parse_uuid(run_id, field_name="run_id", correlation_id=correlation_id)
    if run_uuid_err is not None:
        return run_uuid_err
    assert tenant_id is not None
    assert run_uuid is not None
    run = await _load_tenant_run_with_children(db, tenant_id=tenant_id, run_id=run_uuid)
    if run is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Root-key remediation run not found in tenant scope.",
        )
    tasks = sorted(run.external_tasks, key=lambda task: str(task.created_at))
    dependencies = sorted(
        run.dependency_fingerprints,
        key=lambda dependency: (
            str(dependency.created_at),
            dependency.fingerprint_type,
            dependency.fingerprint_hash,
        ),
    )
    events = sorted(
        run.events,
        key=lambda event: (
            str(event.created_at),
            event.event_type,
            str(event.id),
        ),
    )
    artifacts = sorted(
        run.artifacts,
        key=lambda artifact: (
            str(artifact.created_at),
            artifact.artifact_type,
            str(artifact.id),
        ),
    )
    _set_common_headers(response, correlation_id=correlation_id)
    return RootKeyRunDetailResponse(
        correlation_id=correlation_id,
        contract_version=ROOT_KEY_CONTRACT_VERSION,
        run=_run_snapshot(run),
        external_tasks=[_task_snapshot(task) for task in tasks],
        dependencies=[_dependency_snapshot(dependency) for dependency in dependencies],
        events=[_event_snapshot(event) for event in events],
        artifacts=[_artifact_snapshot(artifact) for artifact in artifacts],
        event_count=len(events),
        dependency_count=len(dependencies),
        artifact_count=len(artifacts),
    )


async def _run_transition_operation(
    *,
    db: AsyncSession,
    correlation_id: str,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    idempotency_key: str,
    operation: str,
    operation_call: Any,
) -> tuple[RootKeyRunResponse | None, JSONResponse | None]:
    service = RootKeyRemediationStateMachineService()
    transition_id = _transition_id(operation, idempotency_key)
    try:
        transition_result = await operation_call(service, transition_id)
        await db.commit()
    except RootKeyStateMachineError as exc:
        await _safe_rollback(db)
        return None, _state_machine_error_response(correlation_id=correlation_id, exc=exc)
    except Exception:
        await _safe_rollback(db)
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Unexpected server error while mutating root-key remediation run.",
        )
    latest_run = await _load_tenant_run_with_children(db, tenant_id=tenant_id, run_id=run_id)
    if latest_run is None:
        return None, _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Root-key remediation run not found in tenant scope.",
        )
    return RootKeyRunResponse(
        correlation_id=correlation_id,
        contract_version=ROOT_KEY_CONTRACT_VERSION,
        idempotency_replayed=not transition_result.state_changed,
        run=_run_snapshot(latest_run),
    ), None


def _build_transition_metadata(user: User) -> dict[str, Any]:
    role = getattr(getattr(user, "role", None), "value", getattr(user, "role", "member"))
    return {"actor_type": "user", "actor_user_id": str(user.id), "actor_role": str(role)}


async def _transition_preflight(
    *,
    run_id: str,
    correlation_id: str,
    current_user: User | None,
    idempotency_key_header: str | None,
) -> tuple[uuid.UUID | None, uuid.UUID | None, str | None, JSONResponse | None]:
    tenant_id, idempotency_key, preflight_err = _mutating_preflight(
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return None, None, None, preflight_err
    run_uuid, run_uuid_err = _parse_uuid(run_id, field_name="run_id", correlation_id=correlation_id)
    if run_uuid_err is not None:
        return None, None, None, run_uuid_err
    return tenant_id, run_uuid, idempotency_key, None


@router.post(
    "/{run_id}/validate",
    response_model=RootKeyRunResponse,
    summary="Transition run to validation",
    responses={400: {"model": RootKeyErrorResponse}, 401: {"model": RootKeyErrorResponse}, 404: {"model": RootKeyErrorResponse}, 409: {"model": RootKeyErrorResponse}, 500: {"model": RootKeyErrorResponse}},
)
async def validate_root_key_remediation_run(
    run_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(contract_version_header=contract_version_header, correlation_id=correlation_id)
    if contract_err is not None:
        return contract_err
    tenant_id, run_uuid, idempotency_key, preflight_err = await _transition_preflight(
        run_id=run_id,
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert run_uuid is not None
    assert idempotency_key is not None
    payload, err = await _run_transition_operation(
        db=db,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        run_id=run_uuid,
        idempotency_key=idempotency_key,
        operation="validate",
        operation_call=lambda service, transition_id: service.advance_to_validation(
            db,
            tenant_id=tenant_id,
            run_id=run_uuid,
            transition_id=transition_id,
            actor_metadata=_build_transition_metadata(current_user),
        ),
    )
    if err is not None:
        return err
    _set_common_headers(response, correlation_id=correlation_id)
    return payload


@router.post(
    "/{run_id}/disable",
    response_model=RootKeyRunResponse,
    summary="Transition run to disable window",
    responses={400: {"model": RootKeyErrorResponse}, 401: {"model": RootKeyErrorResponse}, 404: {"model": RootKeyErrorResponse}, 409: {"model": RootKeyErrorResponse}, 500: {"model": RootKeyErrorResponse}},
)
async def disable_root_key_remediation_run(
    run_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(contract_version_header=contract_version_header, correlation_id=correlation_id)
    if contract_err is not None:
        return contract_err
    tenant_id, run_uuid, idempotency_key, preflight_err = await _transition_preflight(
        run_id=run_id,
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert run_uuid is not None
    assert idempotency_key is not None
    executor_worker = RootKeyRemediationExecutorWorker() if _use_executor_worker() else None
    payload, err = await _run_transition_operation(
        db=db,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        run_id=run_uuid,
        idempotency_key=idempotency_key,
        operation="disable",
        operation_call=lambda service, transition_id: (
            executor_worker.execute_disable(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                state_machine=service,
                actor_metadata=_build_transition_metadata(current_user),
            )
            if executor_worker is not None
            else service.start_disable_window(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                actor_metadata=_build_transition_metadata(current_user),
            )
        ),
    )
    if err is not None:
        return err
    _set_common_headers(response, correlation_id=correlation_id)
    return payload


@router.post(
    "/{run_id}/rollback",
    response_model=RootKeyRunResponse,
    summary="Rollback root-key remediation run",
    responses={400: {"model": RootKeyErrorResponse}, 401: {"model": RootKeyErrorResponse}, 404: {"model": RootKeyErrorResponse}, 409: {"model": RootKeyErrorResponse}, 500: {"model": RootKeyErrorResponse}},
)
async def rollback_root_key_remediation_run(
    run_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    body: RootKeyRollbackRequest = Body(default=RootKeyRollbackRequest()),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(contract_version_header=contract_version_header, correlation_id=correlation_id)
    if contract_err is not None:
        return contract_err
    tenant_id, run_uuid, idempotency_key, preflight_err = await _transition_preflight(
        run_id=run_id,
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert run_uuid is not None
    assert idempotency_key is not None
    reason = (body.reason or "").strip() or "operator_requested_rollback"
    executor_worker = RootKeyRemediationExecutorWorker() if _use_executor_worker() else None
    payload, err = await _run_transition_operation(
        db=db,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        run_id=run_uuid,
        idempotency_key=idempotency_key,
        operation="rollback",
        operation_call=lambda service, transition_id: (
            executor_worker.execute_rollback(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                rollback_reason=reason,
                state_machine=service,
                actor_metadata=_actor_metadata_from_user(current_user, body.actor_metadata),
            )
            if executor_worker is not None
            else service.rollback(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                rollback_reason=reason,
                actor_metadata=_actor_metadata_from_user(current_user, body.actor_metadata),
            )
        ),
    )
    if err is not None:
        return err
    _set_common_headers(response, correlation_id=correlation_id)
    return payload


@router.post(
    "/{run_id}/delete",
    response_model=RootKeyRunResponse,
    summary="Finalize delete window and complete run",
    responses={400: {"model": RootKeyErrorResponse}, 401: {"model": RootKeyErrorResponse}, 404: {"model": RootKeyErrorResponse}, 409: {"model": RootKeyErrorResponse}, 500: {"model": RootKeyErrorResponse}},
)
async def delete_root_key_remediation_run(
    run_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(contract_version_header=contract_version_header, correlation_id=correlation_id)
    if contract_err is not None:
        return contract_err
    tenant_id, run_uuid, idempotency_key, preflight_err = await _transition_preflight(
        run_id=run_id,
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert run_uuid is not None
    assert idempotency_key is not None
    executor_worker = RootKeyRemediationExecutorWorker() if _use_executor_worker() else None
    payload, err = await _run_transition_operation(
        db=db,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        run_id=run_uuid,
        idempotency_key=idempotency_key,
        operation="delete",
        operation_call=lambda service, transition_id: (
            executor_worker.execute_delete(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                state_machine=service,
                actor_metadata=_build_transition_metadata(current_user),
            )
            if executor_worker is not None
            else service.finalize_delete(
                db,
                tenant_id=tenant_id,
                run_id=run_uuid,
                transition_id=transition_id,
                actor_metadata=_build_transition_metadata(current_user),
            )
        ),
    )
    if err is not None:
        return err
    _set_common_headers(response, correlation_id=correlation_id)
    return payload


@router.post(
    "/{run_id}/external-tasks/{task_id}/complete",
    response_model=RootKeyExternalTaskCompleteResponse,
    summary="Complete a root-key external task",
    responses={400: {"model": RootKeyErrorResponse}, 401: {"model": RootKeyErrorResponse}, 404: {"model": RootKeyErrorResponse}, 409: {"model": RootKeyErrorResponse}, 500: {"model": RootKeyErrorResponse}},
)
async def complete_root_key_external_task(
    run_id: str,
    task_id: str,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
    body: RootKeyExternalTaskCompleteRequest = Body(default=RootKeyExternalTaskCompleteRequest()),
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
    contract_version_header: Annotated[str | None, Header(alias="X-Root-Key-Contract-Version")] = None,
) -> RootKeyExternalTaskCompleteResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    contract_err = _validate_contract_header(contract_version_header=contract_version_header, correlation_id=correlation_id)
    if contract_err is not None:
        return contract_err
    tenant_id, idempotency_key, preflight_err = _mutating_preflight(
        correlation_id=correlation_id,
        current_user=current_user,
        idempotency_key_header=idempotency_key_header,
    )
    if preflight_err is not None:
        return preflight_err
    assert tenant_id is not None
    assert idempotency_key is not None
    run_uuid, run_uuid_err = _parse_uuid(run_id, field_name="run_id", correlation_id=correlation_id)
    if run_uuid_err is not None:
        return run_uuid_err
    task_uuid, task_uuid_err = _parse_uuid(task_id, field_name="task_id", correlation_id=correlation_id)
    if task_uuid_err is not None:
        return task_uuid_err
    assert run_uuid is not None
    assert task_uuid is not None
    run = await _load_tenant_run_with_children(db, tenant_id=tenant_id, run_id=run_uuid)
    if run is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Root-key remediation run not found in tenant scope.",
        )
    task = await _load_tenant_external_task(
        db,
        tenant_id=tenant_id,
        run_id=run_uuid,
        task_id=task_uuid,
    )
    if task is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="external_task_not_found",
            message="Root-key external task not found in tenant scope.",
        )
    transition_id = _transition_id(f"external_complete:{task_id}", idempotency_key)
    pre_completed = task.status == RootKeyExternalTaskStatus.completed
    try:
        _, created = await create_root_key_remediation_event_idempotent(
            db,
            run_id=run.id,
            tenant_id=tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            state=run.state,
            status=run.status,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            event_type="external_task_completed",
            actor_metadata=_actor_metadata_from_user(current_user, body.actor_metadata),
            payload={
                "task_id": str(task.id),
                "task_type": task.task_type,
                "task_result": _sanitize_json(body.result),
            },
            idempotency_key=f"{transition_id}:event",
        )
        if task.status != RootKeyExternalTaskStatus.completed:
            now = datetime.now(timezone.utc)
            task.status = RootKeyExternalTaskStatus.completed
            task.task_result = _sanitize_json(body.result)
            task.completed_at = now
            task.actor_metadata = _actor_metadata_from_user(current_user, body.actor_metadata)
            task.updated_at = now
        await db.commit()
    except Exception:
        await _safe_rollback(db)
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Unexpected server error while completing external task.",
        )
    await db.refresh(task)
    latest_run = await _load_tenant_run_with_children(db, tenant_id=tenant_id, run_id=run_uuid)
    if latest_run is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Root-key remediation run not found in tenant scope.",
        )
    _set_common_headers(response, correlation_id=correlation_id)
    return RootKeyExternalTaskCompleteResponse(
        correlation_id=correlation_id,
        contract_version=ROOT_KEY_CONTRACT_VERSION,
        idempotency_replayed=(not created) and pre_completed,
        run=_run_snapshot(latest_run),
        task=_task_snapshot(task),
    )
