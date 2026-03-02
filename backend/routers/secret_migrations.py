from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth import get_current_user
from backend.config import settings
from backend.database import get_db
from backend.models.secret_migration_run import SecretMigrationRun
from backend.models.secret_migration_transaction import SecretMigrationTransaction
from backend.models.user import User
from backend.services.secret_migration_connectors import (
    SecretMigrationConnectorError,
    SecretMigrationValidationError,
)
from backend.services.secret_migration_service import (
    SecretMigrationConnectorSpec,
    SecretMigrationPlan,
    SecretMigrationTargetSpec,
    create_secret_migration_run_idempotent,
    execute_secret_migration_run,
    get_secret_migration_run,
    retry_secret_migration_run,
)

router = APIRouter(prefix="/secret-migrations", tags=["secret-migrations"])

SECRET_MIGRATION_CONTRACT_VERSION = "2026-03-02"
_MAX_IDEMPOTENCY_KEY_LEN = 128


class SecretMigrationError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class SecretMigrationErrorResponse(BaseModel):
    correlation_id: str
    contract_version: str
    error: SecretMigrationError


class SecretMigrationConnectorRequest(BaseModel):
    connector: str = Field(..., description="Connector identifier.")
    account_id: str | None = Field(default=None, description="Tenant-scoped AWS account ID.")
    region: str | None = Field(default=None, description="AWS region for connector operations.")
    repository: str | None = Field(default=None, description="Repository for CI secret backends.")
    parameter_type: str | None = Field(default=None, description="Optional SSM target parameter type.")


class SecretMigrationTargetRequest(BaseModel):
    source_ref: str = Field(..., min_length=1, max_length=1024)
    target_ref: str = Field(..., min_length=1, max_length=1024)


class SecretMigrationCreateRequest(BaseModel):
    source: SecretMigrationConnectorRequest
    target: SecretMigrationConnectorRequest
    targets: list[SecretMigrationTargetRequest] = Field(..., min_length=1, max_length=200)
    dry_run: bool = Field(default=False)
    rollback_on_failure: bool = Field(default=True)


class SecretMigrationTransactionResponse(BaseModel):
    id: str
    source_ref: str
    target_ref: str
    status: str
    attempt_count: int
    rollback_supported: bool
    target_version: str | None
    message: str | None
    error_code: str | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class SecretMigrationRunResponseBody(BaseModel):
    id: str
    status: str
    source_connector: str
    target_connector: str
    dry_run: bool
    rollback_on_failure: bool
    total_targets: int
    succeeded_targets: int
    failed_targets: int
    rolled_back_targets: int
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    transactions: list[SecretMigrationTransactionResponse]
    transaction_count: int


class SecretMigrationRunResponse(BaseModel):
    correlation_id: str
    contract_version: str
    idempotency_replayed: bool
    run: SecretMigrationRunResponseBody


def _is_enabled() -> bool:
    return bool(settings.SECRET_MIGRATION_CONNECTORS_ENABLED)


def _new_correlation_id(header_value: str | None) -> str:
    value = (header_value or "").strip()
    return value or uuid.uuid4().hex


def _iso(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _to_tx_response(tx: SecretMigrationTransaction) -> SecretMigrationTransactionResponse:
    return SecretMigrationTransactionResponse(
        id=str(tx.id),
        source_ref=tx.source_ref,
        target_ref=tx.target_ref,
        status=tx.status,
        attempt_count=int(tx.attempt_count),
        rollback_supported=bool(tx.rollback_supported),
        target_version=tx.target_version,
        message=tx.message,
        error_code=tx.error_code,
        error_message=tx.error_message,
        started_at=_iso(tx.started_at),
        completed_at=_iso(tx.completed_at),
        created_at=_iso(tx.created_at) or "",
        updated_at=_iso(tx.updated_at) or "",
    )


def _to_run_response_body(run: SecretMigrationRun) -> SecretMigrationRunResponseBody:
    transactions = sorted(run.transactions, key=lambda row: str(row.id))
    tx_response = [_to_tx_response(row) for row in transactions]
    return SecretMigrationRunResponseBody(
        id=str(run.id),
        status=run.status,
        source_connector=run.source_connector,
        target_connector=run.target_connector,
        dry_run=bool(run.dry_run),
        rollback_on_failure=bool(run.rollback_on_failure),
        total_targets=int(run.total_targets),
        succeeded_targets=int(run.succeeded_targets),
        failed_targets=int(run.failed_targets),
        rolled_back_targets=int(run.rolled_back_targets),
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=_iso(run.created_at) or "",
        updated_at=_iso(run.updated_at) or "",
        completed_at=_iso(run.completed_at),
        transactions=tx_response,
        transaction_count=len(tx_response),
    )


def _set_common_headers(response: Response, *, correlation_id: str) -> None:
    response.headers["X-Correlation-Id"] = correlation_id
    response.headers["X-Secret-Migration-Contract-Version"] = SECRET_MIGRATION_CONTRACT_VERSION


def _error_response(
    *,
    correlation_id: str,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = SecretMigrationErrorResponse(
        correlation_id=correlation_id,
        contract_version=SECRET_MIGRATION_CONTRACT_VERSION,
        error=SecretMigrationError(
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
            "X-Secret-Migration-Contract-Version": SECRET_MIGRATION_CONTRACT_VERSION,
        },
    )


def _to_plan(request: SecretMigrationCreateRequest) -> SecretMigrationPlan:
    if len(request.targets) > settings.SECRET_MIGRATION_MAX_TARGETS:
        raise SecretMigrationValidationError(
            "too_many_targets",
            f"targets cannot exceed {settings.SECRET_MIGRATION_MAX_TARGETS}.",
        )
    target_keys = [item.target_ref for item in request.targets]
    if len(set(target_keys)) != len(target_keys):
        raise SecretMigrationValidationError(
            "duplicate_target_ref",
            "target_ref values must be unique per run.",
        )
    return SecretMigrationPlan(
        source=SecretMigrationConnectorSpec(
            connector=request.source.connector,
            account_id=request.source.account_id,
            region=request.source.region,
            repository=request.source.repository,
            parameter_type=request.source.parameter_type,
        ),
        target=SecretMigrationConnectorSpec(
            connector=request.target.connector,
            account_id=request.target.account_id,
            region=request.target.region,
            repository=request.target.repository,
            parameter_type=request.target.parameter_type,
        ),
        targets=[
            SecretMigrationTargetSpec(source_ref=item.source_ref, target_ref=item.target_ref)
            for item in request.targets
        ],
        dry_run=bool(request.dry_run),
        rollback_on_failure=bool(request.rollback_on_failure),
    )


def _require_admin_or_403(current_user: User) -> None:
    role = getattr(current_user.role, "value", current_user.role)
    if role != "admin":
        raise SecretMigrationValidationError(
            "admin_required",
            "Only admins can execute secret migration runs.",
        )


def _require_idempotency_key(idempotency_key: str | None) -> str:
    normalized = (idempotency_key or "").strip()
    if not normalized:
        raise SecretMigrationValidationError(
            "idempotency_key_required",
            "Idempotency-Key header is required.",
        )
    if len(normalized) > _MAX_IDEMPOTENCY_KEY_LEN:
        raise SecretMigrationValidationError(
            "idempotency_key_too_long",
            f"Idempotency-Key must be <= {_MAX_IDEMPOTENCY_KEY_LEN} characters.",
        )
    return normalized


@router.post("/runs", response_model=SecretMigrationRunResponse)
async def create_secret_migration_run(
    request: SecretMigrationCreateRequest,
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> SecretMigrationRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    _set_common_headers(response, correlation_id=correlation_id)
    if not _is_enabled():
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Secret migration connectors are disabled.",
        )
    try:
        _require_admin_or_403(current_user)
        normalized_idempotency_key = _require_idempotency_key(idempotency_key)
        plan = _to_plan(request)
        run, created = await create_secret_migration_run_idempotent(
            db,
            tenant_id=current_user.tenant_id,
            created_by_user_id=current_user.id,
            correlation_id=correlation_id,
            idempotency_key=normalized_idempotency_key,
            plan=plan,
        )
        if created:
            await execute_secret_migration_run(
                db,
                tenant_id=current_user.tenant_id,
                run=run,
                plan=plan,
            )
        await db.commit()
        persisted = await get_secret_migration_run(db, tenant_id=current_user.tenant_id, run_id=run.id)
        if persisted is None:
            await db.rollback()
            return _error_response(
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="run_persisted_lookup_failed",
                message="Secret migration run could not be loaded after commit.",
            )
        if not created:
            response.status_code = status.HTTP_200_OK
        else:
            response.status_code = status.HTTP_201_CREATED
        return SecretMigrationRunResponse(
            correlation_id=correlation_id,
            contract_version=SECRET_MIGRATION_CONTRACT_VERSION,
            idempotency_replayed=(not created),
            run=_to_run_response_body(persisted),
        )
    except SecretMigrationValidationError as error:
        await db.rollback()
        code = error.code
        if code == "admin_required":
            status_code = status.HTTP_403_FORBIDDEN
        elif code == "idempotency_payload_mismatch":
            status_code = status.HTTP_409_CONFLICT
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        return _error_response(
            correlation_id=correlation_id,
            status_code=status_code,
            code=code,
            message=str(error),
        )
    except SecretMigrationConnectorError as error:
        await db.rollback()
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE if error.retryable else status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
            retryable=error.retryable,
        )
    except Exception:
        await db.rollback()
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="unhandled_secret_migration_error",
            message="Unhandled secret migration error.",
        )


@router.get("/runs/{run_id}", response_model=SecretMigrationRunResponse)
async def get_secret_migration_run_details(
    run_id: Annotated[str, Path()],
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> SecretMigrationRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    _set_common_headers(response, correlation_id=correlation_id)
    if not _is_enabled():
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Secret migration connectors are disabled.",
        )
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_run_id",
            message="run_id must be a valid UUID.",
        )
    run = await get_secret_migration_run(db, tenant_id=current_user.tenant_id, run_id=run_uuid)
    if run is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Secret migration run not found for tenant scope.",
        )
    return SecretMigrationRunResponse(
        correlation_id=correlation_id,
        contract_version=SECRET_MIGRATION_CONTRACT_VERSION,
        idempotency_replayed=False,
        run=_to_run_response_body(run),
    )


@router.post("/runs/{run_id}/retry", response_model=SecretMigrationRunResponse)
async def retry_secret_migration_run_endpoint(
    run_id: Annotated[str, Path()],
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    correlation_id_header: Annotated[str | None, Header(alias="X-Correlation-Id")] = None,
) -> SecretMigrationRunResponse | JSONResponse:
    correlation_id = _new_correlation_id(correlation_id_header)
    _set_common_headers(response, correlation_id=correlation_id)
    if not _is_enabled():
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="feature_disabled",
            message="Secret migration connectors are disabled.",
        )
    try:
        _require_admin_or_403(current_user)
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_run_id",
            message="run_id must be a valid UUID.",
        )
    except SecretMigrationValidationError as error:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_403_FORBIDDEN,
            code=error.code,
            message=str(error),
        )

    run = await get_secret_migration_run(db, tenant_id=current_user.tenant_id, run_id=run_uuid)
    if run is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            code="run_not_found",
            message="Secret migration run not found for tenant scope.",
        )
    try:
        await retry_secret_migration_run(
            db,
            tenant_id=current_user.tenant_id,
            run=run,
        )
        await db.commit()
    except SecretMigrationValidationError as error:
        await db.rollback()
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
        )
    except SecretMigrationConnectorError as error:
        await db.rollback()
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE if error.retryable else status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
            retryable=error.retryable,
        )
    except Exception:
        await db.rollback()
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="unhandled_secret_migration_retry_error",
            message="Unhandled secret migration retry error.",
        )
    persisted = await get_secret_migration_run(db, tenant_id=current_user.tenant_id, run_id=run_uuid)
    if persisted is None:
        return _error_response(
            correlation_id=correlation_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="run_persisted_lookup_failed",
            message="Secret migration run could not be loaded after retry commit.",
        )
    return SecretMigrationRunResponse(
        correlation_id=correlation_id,
        contract_version=SECRET_MIGRATION_CONTRACT_VERSION,
        idempotency_replayed=False,
        run=_to_run_response_body(persisted),
    )
