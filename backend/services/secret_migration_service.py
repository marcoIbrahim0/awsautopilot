from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.models.aws_account import AwsAccount
from backend.models.enums import SecretMigrationRunStatus, SecretMigrationTransactionStatus
from backend.models.secret_migration_run import SecretMigrationRun
from backend.models.secret_migration_transaction import SecretMigrationTransaction
from backend.services.aws import assume_role
from backend.services.secret_migration_connectors import (
    AwsSecretsManagerConnector,
    AwsSsmParameterStoreConnector,
    GithubActionsConnector,
    SecretMigrationConnectorError,
    SecretMigrationUnavailableError,
    SecretMigrationValidationError,
)

AssumeRoleFn = Callable[..., Any]

_SECRET_TOKENS = (
    "secret",
    "password",
    "token",
    "authorization",
    "access_key",
    "session_key",
    "value",
)

_TX_FAILED_STATES = {
    SecretMigrationTransactionStatus.failed.value,
    SecretMigrationTransactionStatus.rollback_failed.value,
}
_TX_RETRY_STATES = _TX_FAILED_STATES | {SecretMigrationTransactionStatus.rolled_back.value}
_TX_SUCCESS_STATES = {
    SecretMigrationTransactionStatus.success.value,
    SecretMigrationTransactionStatus.skipped.value,
}


@dataclass(frozen=True)
class SecretMigrationConnectorSpec:
    connector: str
    account_id: str | None = None
    region: str | None = None
    repository: str | None = None
    parameter_type: str | None = None


@dataclass(frozen=True)
class SecretMigrationTargetSpec:
    source_ref: str
    target_ref: str


@dataclass(frozen=True)
class SecretMigrationPlan:
    source: SecretMigrationConnectorSpec
    target: SecretMigrationConnectorSpec
    targets: list[SecretMigrationTargetSpec]
    dry_run: bool
    rollback_on_failure: bool


def _is_secret_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_secret_key(str(key)):
                out[str(key)] = "<REDACTED>"
            else:
                out[str(key)] = sanitize_json(nested)
        return out
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    return value


def _safe_error_message(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in _SECRET_TOKENS):
        return "<REDACTED>"
    return message[:500]


def _require_non_empty(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise SecretMigrationValidationError(
            f"{field_name}_required",
            f"{field_name} is required.",
        )
    return normalized


def _normalized_connector_dict(spec: SecretMigrationConnectorSpec) -> dict[str, Any]:
    return {
        "connector": spec.connector.strip().lower(),
        "account_id": (spec.account_id or "").strip() or None,
        "region": (spec.region or "").strip() or None,
        "repository": (spec.repository or "").strip() or None,
        "parameter_type": (spec.parameter_type or "").strip() or None,
    }


def migration_request_signature(plan: SecretMigrationPlan) -> str:
    payload = {
        "source": _normalized_connector_dict(plan.source),
        "target": _normalized_connector_dict(plan.target),
        "targets": [{"source_ref": t.source_ref, "target_ref": t.target_ref} for t in plan.targets],
        "dry_run": bool(plan.dry_run),
        "rollback_on_failure": bool(plan.rollback_on_failure),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _approved_ci_backends() -> set[str]:
    raw = (settings.SECRET_MIGRATION_APPROVED_CI_BACKENDS or "").strip().lower()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


async def get_secret_migration_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
) -> SecretMigrationRun | None:
    result = await db.execute(
        select(SecretMigrationRun)
        .options(selectinload(SecretMigrationRun.transactions))
        .where(
            SecretMigrationRun.tenant_id == tenant_id,
            SecretMigrationRun.id == run_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_run_by_idempotency_key(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    idempotency_key: str,
) -> SecretMigrationRun | None:
    result = await db.execute(
        select(SecretMigrationRun)
        .options(selectinload(SecretMigrationRun.transactions))
        .where(
            SecretMigrationRun.tenant_id == tenant_id,
            SecretMigrationRun.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def create_secret_migration_run_idempotent(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    correlation_id: str,
    idempotency_key: str,
    plan: SecretMigrationPlan,
) -> tuple[SecretMigrationRun, bool]:
    normalized_idempotency_key = _require_non_empty(idempotency_key, field_name="idempotency_key")
    signature = migration_request_signature(plan)
    existing = await _get_run_by_idempotency_key(
        db,
        tenant_id=tenant_id,
        idempotency_key=normalized_idempotency_key,
    )
    if existing is not None:
        if existing.request_signature != signature:
            raise SecretMigrationValidationError(
                "idempotency_payload_mismatch",
                "Idempotent replay payload mismatch.",
            )
        return existing, False

    run = SecretMigrationRun(
        tenant_id=tenant_id,
        created_by_user_id=created_by_user_id,
        source_connector=plan.source.connector,
        source_config=sanitize_json(_normalized_connector_dict(plan.source)),
        target_connector=plan.target.connector,
        target_config=sanitize_json(_normalized_connector_dict(plan.target)),
        dry_run=bool(plan.dry_run),
        rollback_on_failure=bool(plan.rollback_on_failure),
        status=SecretMigrationRunStatus.queued.value,
        request_signature=signature,
        idempotency_key=normalized_idempotency_key,
        correlation_id=_require_non_empty(correlation_id, field_name="correlation_id"),
        total_targets=len(plan.targets),
    )
    for target in plan.targets:
        run.transactions.append(
            SecretMigrationTransaction(
                tenant_id=tenant_id,
                source_ref=target.source_ref,
                target_ref=target.target_ref,
                status=SecretMigrationTransactionStatus.pending.value,
            )
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
        if existing.request_signature != signature:
            raise SecretMigrationValidationError(
                "idempotency_payload_mismatch",
                "Idempotent replay payload mismatch.",
            )
        return existing, False

    return run, True


async def _tenant_aws_account(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str,
) -> AwsAccount:
    result = await db.execute(
        select(AwsAccount).where(
            AwsAccount.tenant_id == tenant_id,
            AwsAccount.account_id == account_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        raise SecretMigrationValidationError(
            "aws_account_not_found_for_tenant",
            "AWS account is not registered for tenant scope.",
        )
    return account


async def _assumed_session_for_connector(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector: SecretMigrationConnectorSpec,
    for_write: bool,
    assume_role_fn: AssumeRoleFn,
) -> Any:
    account_id = _require_non_empty(connector.account_id or "", field_name="account_id")
    account = await _tenant_aws_account(db, tenant_id=tenant_id, account_id=account_id)
    role_arn = account.role_write_arn if for_write else account.role_read_arn
    if for_write and not role_arn:
        raise SecretMigrationValidationError(
            "aws_write_role_required",
            "Target connector requires role_write_arn for tenant-scoped AWS account.",
        )
    if not role_arn:
        raise SecretMigrationValidationError(
            "aws_read_role_required",
            "Source connector requires role_read_arn for tenant-scoped AWS account.",
        )
    try:
        return assume_role_fn(role_arn=role_arn, external_id=account.external_id)
    except (ClientError, ValueError) as error:
        message = type(error).__name__
        raise SecretMigrationUnavailableError(
            "aws_assume_role_failed",
            f"AWS role assumption failed for connector ({message}).",
        ) from error


async def _build_source_connector(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector: SecretMigrationConnectorSpec,
    assume_role_fn: AssumeRoleFn,
) -> Any:
    name = connector.connector.strip().lower()
    region = (connector.region or "").strip() or settings.AWS_REGION
    if name == AwsSecretsManagerConnector.connector_name:
        session = await _assumed_session_for_connector(
            db,
            tenant_id=tenant_id,
            connector=connector,
            for_write=False,
            assume_role_fn=assume_role_fn,
        )
        return AwsSecretsManagerConnector(session=session, region=region)
    if name == AwsSsmParameterStoreConnector.connector_name:
        session = await _assumed_session_for_connector(
            db,
            tenant_id=tenant_id,
            connector=connector,
            for_write=False,
            assume_role_fn=assume_role_fn,
        )
        return AwsSsmParameterStoreConnector(session=session, region=region)
    raise SecretMigrationValidationError(
        "unsupported_source_connector",
        f"Unsupported source connector: {name}.",
    )


async def _build_target_connector(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    connector: SecretMigrationConnectorSpec,
    assume_role_fn: AssumeRoleFn,
) -> Any:
    name = connector.connector.strip().lower()
    region = (connector.region or "").strip() or settings.AWS_REGION
    if name == AwsSecretsManagerConnector.connector_name:
        session = await _assumed_session_for_connector(
            db,
            tenant_id=tenant_id,
            connector=connector,
            for_write=True,
            assume_role_fn=assume_role_fn,
        )
        return AwsSecretsManagerConnector(session=session, region=region)
    if name == AwsSsmParameterStoreConnector.connector_name:
        session = await _assumed_session_for_connector(
            db,
            tenant_id=tenant_id,
            connector=connector,
            for_write=True,
            assume_role_fn=assume_role_fn,
        )
        return AwsSsmParameterStoreConnector(
            session=session,
            region=region,
            default_parameter_type=(connector.parameter_type or "SecureString"),
        )
    if name == GithubActionsConnector.connector_name:
        if name not in _approved_ci_backends():
            raise SecretMigrationValidationError(
                "ci_backend_not_approved",
                "Requested CI backend is not in the approved connector allowlist.",
            )
        repository = _require_non_empty(connector.repository or "", field_name="repository")
        return GithubActionsConnector(
            repo=repository,
            gh_bin=settings.SECRET_MIGRATION_GITHUB_CLI_BIN,
        )
    raise SecretMigrationValidationError(
        "unsupported_target_connector",
        f"Unsupported target connector: {name}.",
    )


def _mapping_by_target(plan: SecretMigrationPlan) -> dict[str, SecretMigrationTargetSpec]:
    return {item.target_ref: item for item in plan.targets}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _recalculate_run_counters(run: SecretMigrationRun) -> None:
    run.total_targets = len(run.transactions)
    run.succeeded_targets = sum(1 for tx in run.transactions if tx.status in _TX_SUCCESS_STATES)
    run.failed_targets = sum(1 for tx in run.transactions if tx.status in _TX_FAILED_STATES)
    run.rolled_back_targets = sum(1 for tx in run.transactions if tx.status == SecretMigrationTransactionStatus.rolled_back.value)


def _finalize_run_status(run: SecretMigrationRun) -> None:
    _recalculate_run_counters(run)
    if run.failed_targets == 0:
        if run.rolled_back_targets > 0 and run.succeeded_targets == 0:
            run.status = SecretMigrationRunStatus.rolled_back.value
        else:
            run.status = SecretMigrationRunStatus.success.value
        run.error_code = None
        run.error_message = None
        return
    if run.succeeded_targets > 0:
        run.status = SecretMigrationRunStatus.partial_failed.value
    elif run.rolled_back_targets > 0:
        run.status = SecretMigrationRunStatus.rolled_back.value
    else:
        run.status = SecretMigrationRunStatus.failed.value
    first_failed = next((tx for tx in run.transactions if tx.status in _TX_FAILED_STATES), None)
    run.error_code = first_failed.error_code if first_failed else "migration_failed"
    run.error_message = first_failed.error_message if first_failed else "Secret migration failed."


async def _process_transactions(
    *,
    run: SecretMigrationRun,
    plan: SecretMigrationPlan,
    source_connector: Any,
    target_connector: Any,
    target_filter: set[str] | None = None,
) -> None:
    mappings = _mapping_by_target(plan)
    applied_transactions: list[SecretMigrationTransaction] = []
    failures_found = False
    run.status = SecretMigrationRunStatus.running.value
    run.error_code = None
    run.error_message = None
    for tx in run.transactions:
        if target_filter is not None and tx.target_ref not in target_filter:
            continue
        mapping = mappings.get(tx.target_ref)
        if mapping is None:
            tx.status = SecretMigrationTransactionStatus.failed.value
            tx.error_code = "target_mapping_missing"
            tx.error_message = "Target mapping missing for transaction row."
            tx.completed_at = _now()
            failures_found = True
            continue
        tx.status = SecretMigrationTransactionStatus.pending.value
        tx.started_at = _now()
        tx.completed_at = None
        tx.error_code = None
        tx.error_message = None
        tx.message = None
        tx.attempt_count = int(tx.attempt_count or 0) + 1
        try:
            source_value = source_connector.read_secret(mapping.source_ref)
            if isinstance(target_connector, AwsSsmParameterStoreConnector):
                receipt = target_connector.upsert_secret(
                    mapping.target_ref,
                    source_value.value,
                    dry_run=bool(run.dry_run),
                    parameter_type=plan.target.parameter_type,
                )
            else:
                receipt = target_connector.upsert_secret(
                    mapping.target_ref,
                    source_value.value,
                    dry_run=bool(run.dry_run),
                )
            tx.rollback_supported = bool(receipt.rollback_supported)
            tx.rollback_token = sanitize_json(receipt.rollback_token) if receipt.rollback_token is not None else None
            tx.target_version = receipt.target_version
            tx.message = receipt.message
            tx.status = (
                SecretMigrationTransactionStatus.skipped.value
                if run.dry_run
                else SecretMigrationTransactionStatus.success.value
            )
            tx.completed_at = _now()
            if (not run.dry_run) and tx.rollback_supported and tx.rollback_token:
                applied_transactions.append(tx)
        except SecretMigrationConnectorError as error:
            tx.status = SecretMigrationTransactionStatus.failed.value
            tx.error_code = error.code
            tx.error_message = _safe_error_message(str(error))
            tx.completed_at = _now()
            failures_found = True
        except Exception as error:  # pragma: no cover - defensive fail-closed branch
            tx.status = SecretMigrationTransactionStatus.failed.value
            tx.error_code = "unexpected_connector_error"
            tx.error_message = _safe_error_message(type(error).__name__)
            tx.completed_at = _now()
            failures_found = True

    if failures_found and (not run.dry_run) and bool(run.rollback_on_failure):
        for tx in reversed(applied_transactions):
            try:
                target_connector.rollback_secret(tx.target_ref, tx.rollback_token)
                tx.status = SecretMigrationTransactionStatus.rolled_back.value
                tx.message = "rolled_back_after_partial_failure"
                tx.completed_at = _now()
            except SecretMigrationConnectorError as error:
                tx.status = SecretMigrationTransactionStatus.rollback_failed.value
                tx.error_code = error.code
                tx.error_message = _safe_error_message(str(error))
                tx.completed_at = _now()
            except Exception as error:  # pragma: no cover - defensive fail-closed branch
                tx.status = SecretMigrationTransactionStatus.rollback_failed.value
                tx.error_code = "rollback_unexpected_error"
                tx.error_message = _safe_error_message(type(error).__name__)
                tx.completed_at = _now()

    run.completed_at = _now()
    _finalize_run_status(run)


def plan_from_run(run: SecretMigrationRun) -> SecretMigrationPlan:
    source_config = run.source_config or {}
    target_config = run.target_config or {}
    targets = [
        SecretMigrationTargetSpec(source_ref=tx.source_ref, target_ref=tx.target_ref)
        for tx in sorted(run.transactions, key=lambda row: str(row.id))
    ]
    return SecretMigrationPlan(
        source=SecretMigrationConnectorSpec(
            connector=run.source_connector,
            account_id=source_config.get("account_id"),
            region=source_config.get("region"),
            repository=source_config.get("repository"),
            parameter_type=source_config.get("parameter_type"),
        ),
        target=SecretMigrationConnectorSpec(
            connector=run.target_connector,
            account_id=target_config.get("account_id"),
            region=target_config.get("region"),
            repository=target_config.get("repository"),
            parameter_type=target_config.get("parameter_type"),
        ),
        targets=targets,
        dry_run=bool(run.dry_run),
        rollback_on_failure=bool(run.rollback_on_failure),
    )


async def execute_secret_migration_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run: SecretMigrationRun,
    plan: SecretMigrationPlan,
    assume_role_fn: AssumeRoleFn = assume_role,
) -> SecretMigrationRun:
    source_connector = await _build_source_connector(
        db,
        tenant_id=tenant_id,
        connector=plan.source,
        assume_role_fn=assume_role_fn,
    )
    target_connector = await _build_target_connector(
        db,
        tenant_id=tenant_id,
        connector=plan.target,
        assume_role_fn=assume_role_fn,
    )
    await _process_transactions(
        run=run,
        plan=plan,
        source_connector=source_connector,
        target_connector=target_connector,
        target_filter=None,
    )
    return run


async def retry_secret_migration_run(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run: SecretMigrationRun,
    assume_role_fn: AssumeRoleFn = assume_role,
) -> SecretMigrationRun:
    if run.status == SecretMigrationRunStatus.success.value:
        return run
    plan = plan_from_run(run)
    target_filter = {tx.target_ref for tx in run.transactions if tx.status in _TX_RETRY_STATES}
    if not target_filter:
        return run
    source_connector = await _build_source_connector(
        db,
        tenant_id=tenant_id,
        connector=plan.source,
        assume_role_fn=assume_role_fn,
    )
    target_connector = await _build_target_connector(
        db,
        tenant_id=tenant_id,
        connector=plan.target,
        assume_role_fn=assume_role_fn,
    )
    await _process_transactions(
        run=run,
        plan=plan,
        source_connector=source_connector,
        target_connector=target_connector,
        target_filter=target_filter,
    )
    return run
