from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from backend.services.secret_migration_connectors import SecretMigrationValidationError, SourceSecretValue, TargetWriteReceipt
from backend.services.secret_migration_service import (
    SecretMigrationConnectorSpec,
    SecretMigrationPlan,
    SecretMigrationTargetSpec,
    _process_transactions,
)


@dataclass
class _Tx:
    id: str
    source_ref: str
    target_ref: str
    status: str = "pending"
    attempt_count: int = 0
    rollback_supported: bool = True
    rollback_token: dict | None = None
    target_version: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = datetime.now(timezone.utc)
    updated_at: datetime = datetime.now(timezone.utc)


class _FakeSourceConnector:
    def read_secret(self, secret_ref: str) -> SourceSecretValue:
        return SourceSecretValue(value=f"value-for-{secret_ref}", metadata={})


class _FlakyTargetConnector:
    def __init__(self) -> None:
        self._fail_first = True
        self.rollback_calls: list[str] = []

    def upsert_secret(self, target_ref: str, value: str, *, dry_run: bool) -> TargetWriteReceipt:
        if dry_run:
            return TargetWriteReceipt(
                rollback_supported=True,
                rollback_token={"target_ref": target_ref},
                target_version=None,
                message="dry_run_no_write",
            )
        if target_ref == "target/b" and self._fail_first:
            self._fail_first = False
            raise SecretMigrationValidationError(
                "target_write_failed",
                "connector error: attempted to write secret value=super-secret",
            )
        return TargetWriteReceipt(
            rollback_supported=True,
            rollback_token={"target_ref": target_ref},
            target_version="v1",
            message="applied",
        )

    def rollback_secret(self, target_ref: str, rollback_token: dict | None) -> None:
        del rollback_token
        self.rollback_calls.append(target_ref)


def _plan(*, dry_run: bool = False, rollback_on_failure: bool = True) -> SecretMigrationPlan:
    return SecretMigrationPlan(
        source=SecretMigrationConnectorSpec(connector="aws_secrets_manager", account_id="029037611564"),
        target=SecretMigrationConnectorSpec(connector="aws_ssm_parameter_store", account_id="029037611564"),
        targets=[
            SecretMigrationTargetSpec(source_ref="source/a", target_ref="target/a"),
            SecretMigrationTargetSpec(source_ref="source/b", target_ref="target/b"),
        ],
        dry_run=dry_run,
        rollback_on_failure=rollback_on_failure,
    )


def _run(*, dry_run: bool = False, rollback_on_failure: bool = True) -> Any:
    return SimpleNamespace(
        dry_run=dry_run,
        rollback_on_failure=rollback_on_failure,
        status="queued",
        error_code=None,
        error_message=None,
        completed_at=None,
        total_targets=2,
        succeeded_targets=0,
        failed_targets=0,
        rolled_back_targets=0,
        transactions=[
            _Tx(id="1", source_ref="source/a", target_ref="target/a"),
            _Tx(id="2", source_ref="source/b", target_ref="target/b"),
        ],
    )


async def _execute(run: Any, plan: SecretMigrationPlan, target_filter: set[str] | None = None) -> _FlakyTargetConnector:
    source = _FakeSourceConnector()
    target = _FlakyTargetConnector()
    await _process_transactions(
        run=run,
        plan=plan,
        source_connector=source,
        target_connector=target,
        target_filter=target_filter,
    )
    return target


def test_partial_failure_rolls_back_then_retry_succeeds() -> None:
    run = _run(dry_run=False, rollback_on_failure=True)
    plan = _plan(dry_run=False, rollback_on_failure=True)

    # First attempt: target/b fails, target/a gets rolled back.
    target = _run_async(_execute(run, plan))
    assert run.status == "rolled_back"
    tx_a, tx_b = run.transactions
    assert tx_a.status == "rolled_back"
    assert tx_b.status == "failed"
    assert tx_b.error_message == "<REDACTED>"
    assert target.rollback_calls == ["target/a"]

    # Retry only non-success states should converge to success.
    retry_filter = {tx.target_ref for tx in run.transactions if tx.status in {"failed", "rolled_back", "rollback_failed"}}
    _run_async(
        _process_transactions(
            run=run,
            plan=plan,
            source_connector=_FakeSourceConnector(),
            target_connector=target,
            target_filter=retry_filter,
        )
    )
    assert run.status == "success"
    assert all(tx.status in {"success", "skipped"} for tx in run.transactions)


def test_dry_run_records_skipped_without_writes() -> None:
    run = _run(dry_run=True, rollback_on_failure=True)
    plan = _plan(dry_run=True, rollback_on_failure=True)
    target = _run_async(_execute(run, plan))
    assert run.status == "success"
    assert all(tx.status == "skipped" for tx in run.transactions)
    assert target.rollback_calls == []


def _run_async(coro):
    import asyncio

    return asyncio.run(coro)
