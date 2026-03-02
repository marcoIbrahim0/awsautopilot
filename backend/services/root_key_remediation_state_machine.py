from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.enums import (
    RootKeyArtifactStatus,
    RootKeyRemediationMode,
    RootKeyRemediationRunStatus,
    RootKeyRemediationState,
)
from backend.models.root_key_remediation_run import RootKeyRemediationRun
from backend.services.root_key_remediation_store import (
    create_root_key_remediation_artifact_idempotent,
    create_root_key_remediation_event_idempotent,
    create_root_key_remediation_run_idempotent,
    get_root_key_remediation_run,
    transition_root_key_remediation_run_state,
)

CancellationHook = Callable[
    [RootKeyRemediationRun, RootKeyRemediationState],
    bool | Awaitable[bool],
]

_TERMINAL_STATES = {
    RootKeyRemediationState.completed,
    RootKeyRemediationState.rolled_back,
    RootKeyRemediationState.failed,
}

_ALLOWED_TRANSITIONS: dict[RootKeyRemediationState, set[RootKeyRemediationState]] = {
    RootKeyRemediationState.discovery: {
        RootKeyRemediationState.migration,
        RootKeyRemediationState.needs_attention,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.migration: {
        RootKeyRemediationState.validation,
        RootKeyRemediationState.needs_attention,
        RootKeyRemediationState.rolled_back,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.validation: {
        RootKeyRemediationState.disable_window,
        RootKeyRemediationState.needs_attention,
        RootKeyRemediationState.rolled_back,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.disable_window: {
        RootKeyRemediationState.delete_window,
        RootKeyRemediationState.needs_attention,
        RootKeyRemediationState.rolled_back,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.delete_window: {
        RootKeyRemediationState.completed,
        RootKeyRemediationState.needs_attention,
        RootKeyRemediationState.rolled_back,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.needs_attention: {
        RootKeyRemediationState.migration,
        RootKeyRemediationState.disable_window,
        RootKeyRemediationState.rolled_back,
        RootKeyRemediationState.failed,
    },
    RootKeyRemediationState.completed: set(),
    RootKeyRemediationState.rolled_back: set(),
    RootKeyRemediationState.failed: set(),
}


class RootKeyErrorDisposition(str, Enum):
    retryable = "retryable"
    terminal = "terminal"


@dataclass(frozen=True)
class RootKeyErrorClassification:
    code: str
    message: str
    disposition: RootKeyErrorDisposition

    @property
    def is_retryable(self) -> bool:
        return self.disposition == RootKeyErrorDisposition.retryable


class RootKeyStateMachineError(RuntimeError):
    def __init__(self, classification: RootKeyErrorClassification) -> None:
        super().__init__(classification.message)
        self.classification = classification

    @property
    def is_retryable(self) -> bool:
        return self.classification.is_retryable


@dataclass(frozen=True)
class RootKeyTransitionRetryPolicy:
    max_attempts: int = 3
    base_backoff_seconds: float = 0.2
    max_backoff_seconds: float = 1.5

    def delay_for_attempt(self, attempt_index: int) -> float:
        exponent = max(attempt_index - 1, 0)
        return min(self.base_backoff_seconds * (2**exponent), self.max_backoff_seconds)


@dataclass(frozen=True)
class RootKeyTransitionResult:
    run: RootKeyRemediationRun
    state_changed: bool
    event_created: bool
    evidence_created: bool
    attempts: int


class RootKeyRemediationStateMachineService:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        strict_transitions_enabled: bool | None = None,
        delete_enabled: bool | None = None,
        retry_policy: RootKeyTransitionRetryPolicy | None = None,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._enabled = settings.ROOT_KEY_SAFE_REMEDIATION_ENABLED if enabled is None else bool(enabled)
        strict_default = settings.ROOT_KEY_SAFE_REMEDIATION_STRICT_TRANSITIONS
        self._strict = strict_default if strict_transitions_enabled is None else bool(strict_transitions_enabled)
        delete_default = settings.ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED
        self._delete_enabled = delete_default if delete_enabled is None else bool(delete_enabled)
        self._retry_policy = retry_policy or RootKeyTransitionRetryPolicy()
        self._sleep = sleep_fn

    async def create_run(
        self,
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
        evidence_metadata: dict[str, Any] | None = None,
    ) -> RootKeyTransitionResult:
        self._ensure_feature_enabled()
        run, created, attempts = await self._create_run_with_retry(
            db=db,
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            control_id=control_id,
            action_id=action_id,
            finding_id=finding_id,
            strategy_id=strategy_id,
            mode=mode,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )
        event_created, evidence_created = await self._emit_transition_records(
            db=db,
            run=run,
            transition_id=idempotency_key,
            event_type="create_run",
            from_state=None,
            from_status=None,
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            transition_payload={"created": created},
        )
        return RootKeyTransitionResult(
            run=run,
            state_changed=created,
            event_created=event_created,
            evidence_created=evidence_created,
            attempts=attempts,
        )

    async def advance_to_migration(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.migration,
            to_status=RootKeyRemediationRunStatus.running,
            event_type="advance_to_migration",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            cancellation_hook=cancellation_hook,
        )

    async def advance_to_validation(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.validation,
            to_status=RootKeyRemediationRunStatus.running,
            event_type="advance_to_validation",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            cancellation_hook=cancellation_hook,
        )

    async def start_disable_window(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.disable_window,
            to_status=RootKeyRemediationRunStatus.running,
            event_type="start_disable_window",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            cancellation_hook=cancellation_hook,
        )

    async def finalize_delete(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        self._ensure_feature_enabled()
        if not self._delete_enabled:
            raise self._terminal_error("delete_window_disabled", "Delete window transitions are feature-flagged off.")

        run = await self._get_tenant_run(db=db, tenant_id=tenant_id, run_id=run_id)
        if run.state == RootKeyRemediationState.disable_window:
            await self._transition_with_retry(
                db=db,
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id=f"{transition_id}:delete_window",
                to_state=RootKeyRemediationState.delete_window,
                to_status=RootKeyRemediationRunStatus.running,
                event_type="enter_delete_window",
                actor_metadata=actor_metadata,
                evidence_metadata=evidence_metadata,
                cancellation_hook=cancellation_hook,
            )
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=f"{transition_id}:completed",
            to_state=RootKeyRemediationState.completed,
            to_status=RootKeyRemediationRunStatus.completed,
            event_type="finalize_delete",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            cancellation_hook=cancellation_hook,
        )

    async def mark_needs_attention(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.needs_attention,
            to_status=RootKeyRemediationRunStatus.waiting_for_user,
            event_type="mark_needs_attention",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            cancellation_hook=cancellation_hook,
        )

    async def rollback(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        rollback_reason: str,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.rolled_back,
            to_status=RootKeyRemediationRunStatus.failed,
            event_type="rollback",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            rollback_reason=rollback_reason,
            cancellation_hook=cancellation_hook,
        )

    async def fail_run(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        failure_reason: str,
        retry_increment: int = 0,
        actor_metadata: dict[str, Any] | None = None,
        evidence_metadata: dict[str, Any] | None = None,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        return await self._transition_with_retry(
            db=db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            to_state=RootKeyRemediationState.failed,
            to_status=RootKeyRemediationRunStatus.failed,
            event_type="fail_run",
            actor_metadata=actor_metadata,
            evidence_metadata=evidence_metadata,
            rollback_reason=failure_reason,
            retry_increment=retry_increment,
            cancellation_hook=cancellation_hook,
        )

    def classify_error(self, exc: Exception) -> RootKeyErrorClassification:
        if isinstance(exc, RootKeyStateMachineError):
            return exc.classification
        if isinstance(exc, IntegrityError):
            return RootKeyErrorClassification(
                code="idempotency_conflict",
                message="Write conflict while persisting transition.",
                disposition=RootKeyErrorDisposition.retryable,
            )
        if isinstance(exc, ValueError) and "not found" in str(exc).lower():
            return RootKeyErrorClassification(
                code="tenant_scope_violation",
                message="Run was not found in tenant scope.",
                disposition=RootKeyErrorDisposition.terminal,
            )
        return RootKeyErrorClassification(
            code="terminal_unexpected_error",
            message="Unexpected root-key transition failure.",
            disposition=RootKeyErrorDisposition.terminal,
        )

    async def _create_run_with_retry(
        self,
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
        actor_metadata: dict[str, Any] | None,
    ) -> tuple[RootKeyRemediationRun, bool, int]:
        attempt = 1
        while True:
            try:
                run, created = await create_root_key_remediation_run_idempotent(
                    db,
                    tenant_id=tenant_id,
                    account_id=account_id,
                    region=region,
                    control_id=control_id,
                    action_id=action_id,
                    finding_id=finding_id,
                    strategy_id=strategy_id,
                    mode=mode,
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    actor_metadata=actor_metadata,
                )
                self._validate_idempotent_run_replay(
                    run=run,
                    account_id=account_id,
                    control_id=control_id,
                    action_id=action_id,
                    finding_id=finding_id,
                    strategy_id=strategy_id,
                    mode=mode,
                    correlation_id=correlation_id,
                )
                return run, created, attempt
            except Exception as exc:
                classification = self.classify_error(exc)
                if not classification.is_retryable or attempt >= self._retry_policy.max_attempts:
                    raise RootKeyStateMachineError(classification) from exc
                await self._sleep(self._retry_policy.delay_for_attempt(attempt))
                attempt += 1

    async def _transition_with_retry(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        to_state: RootKeyRemediationState,
        to_status: RootKeyRemediationRunStatus,
        event_type: str,
        actor_metadata: dict[str, Any] | None,
        evidence_metadata: dict[str, Any] | None,
        rollback_reason: str | None = None,
        retry_increment: int = 0,
        cancellation_hook: CancellationHook | None = None,
    ) -> RootKeyTransitionResult:
        self._ensure_feature_enabled()
        attempt = 1
        while True:
            try:
                run = await self._get_tenant_run(db=db, tenant_id=tenant_id, run_id=run_id)
                await self._assert_not_cancelled(run=run, to_state=to_state, hook=cancellation_hook)
                transitioned, from_state, from_status = await self._apply_transition_guarded(
                    db=db,
                    tenant_id=tenant_id,
                    run=run,
                    to_state=to_state,
                    to_status=to_status,
                    rollback_reason=rollback_reason,
                    retry_increment=retry_increment,
                )
                event_created, evidence_created = await self._emit_transition_records(
                    db=db,
                    run=transitioned,
                    transition_id=transition_id,
                    event_type=event_type,
                    from_state=from_state,
                    from_status=from_status,
                    actor_metadata=actor_metadata,
                    evidence_metadata=evidence_metadata,
                    transition_payload={"attempt": attempt, "retry_increment": retry_increment},
                )
                changed = from_state != transitioned.state or from_status != transitioned.status
                return RootKeyTransitionResult(
                    run=transitioned,
                    state_changed=changed,
                    event_created=event_created,
                    evidence_created=evidence_created,
                    attempts=attempt,
                )
            except Exception as exc:
                classification = self.classify_error(exc)
                if not classification.is_retryable or attempt >= self._retry_policy.max_attempts:
                    raise RootKeyStateMachineError(classification) from exc
                await self._sleep(self._retry_policy.delay_for_attempt(attempt))
                attempt += 1

    async def _get_tenant_run(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> RootKeyRemediationRun:
        run = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise self._terminal_error("tenant_scope_violation", "Run was not found in tenant scope.")
        return run

    async def _apply_transition_guarded(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run: RootKeyRemediationRun,
        to_state: RootKeyRemediationState,
        to_status: RootKeyRemediationRunStatus,
        rollback_reason: str | None,
        retry_increment: int,
    ) -> tuple[RootKeyRemediationRun, RootKeyRemediationState, RootKeyRemediationRunStatus]:
        from_state = run.state
        from_status = run.status
        if from_state == to_state and from_status == to_status:
            return run, from_state, from_status
        self._ensure_legal_transition(from_state=from_state, to_state=to_state)
        completed_at = datetime.now(timezone.utc) if to_state in _TERMINAL_STATES else None
        transitioned = await transition_root_key_remediation_run_state(
            db,
            tenant_id=tenant_id,
            run_id=run.id,
            expected_lock_version=run.lock_version,
            new_state=to_state,
            new_status=to_status,
            retry_increment=retry_increment,
            rollback_reason=rollback_reason,
            completed_at=completed_at,
        )
        if transitioned is None:
            latest = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run.id)
            if latest is None:
                raise self._terminal_error("tenant_scope_violation", "Run was not found in tenant scope.")
            if latest.state == to_state and latest.status == to_status:
                return latest, from_state, from_status
            raise self._retryable_error("optimistic_lock_conflict", "Transition lock version conflict.")
        return transitioned, from_state, from_status

    async def _emit_transition_records(
        self,
        *,
        db: AsyncSession,
        run: RootKeyRemediationRun,
        transition_id: str,
        event_type: str,
        from_state: RootKeyRemediationState | None,
        from_status: RootKeyRemediationRunStatus | None,
        actor_metadata: dict[str, Any] | None,
        evidence_metadata: dict[str, Any] | None,
        transition_payload: dict[str, Any] | None = None,
    ) -> tuple[bool, bool]:
        transition_payload = transition_payload or {}
        payload = {
            "transition_id": transition_id,
            "event_type": event_type,
            "from_state": from_state.value if from_state else None,
            "from_status": from_status.value if from_status else None,
            "to_state": run.state.value,
            "to_status": run.status.value,
            **transition_payload,
        }
        event, event_created = await create_root_key_remediation_event_idempotent(
            db,
            run_id=run.id,
            tenant_id=run.tenant_id,
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
            event_type=event_type,
            actor_metadata=actor_metadata,
            payload=payload,
            idempotency_key=f"{transition_id}:event",
        )
        evidence_payload = {
            "transition_id": transition_id,
            "event_id": str(event.id),
            "event_type": event_type,
            "from_state": payload["from_state"],
            "to_state": payload["to_state"],
            "to_status": payload["to_status"],
            "metadata": evidence_metadata or {},
        }
        _, evidence_created = await create_root_key_remediation_artifact_idempotent(
            db,
            run_id=run.id,
            tenant_id=run.tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            state=run.state,
            status=RootKeyArtifactStatus.available,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            artifact_type="state_transition_evidence",
            metadata_json=evidence_payload,
            idempotency_key=f"{transition_id}:evidence",
            actor_metadata=actor_metadata,
        )
        return event_created, evidence_created

    async def _assert_not_cancelled(
        self,
        *,
        run: RootKeyRemediationRun,
        to_state: RootKeyRemediationState,
        hook: CancellationHook | None,
    ) -> None:
        if hook is None:
            return
        verdict = hook(run, to_state)
        should_cancel = await verdict if asyncio.iscoroutine(verdict) else bool(verdict)
        if should_cancel:
            raise self._terminal_error("transition_cancelled", "Transition cancelled by hook.")

    def _ensure_feature_enabled(self) -> None:
        if self._enabled and self._strict:
            return
        raise self._terminal_error(
            "feature_flag_disabled",
            "Root-key remediation state-machine is disabled by feature flags.",
        )

    def _ensure_legal_transition(
        self,
        *,
        from_state: RootKeyRemediationState,
        to_state: RootKeyRemediationState,
    ) -> None:
        if from_state in _TERMINAL_STATES:
            message = f"Illegal transition from terminal state '{from_state.value}' to '{to_state.value}'."
            raise self._terminal_error("illegal_transition", message)
        if to_state in _ALLOWED_TRANSITIONS.get(from_state, set()):
            return
        message = f"Illegal transition from '{from_state.value}' to '{to_state.value}'."
        raise self._terminal_error("illegal_transition", message)

    def _validate_idempotent_run_replay(
        self,
        *,
        run: RootKeyRemediationRun,
        account_id: str,
        control_id: str,
        action_id: uuid.UUID,
        finding_id: uuid.UUID | None,
        strategy_id: str,
        mode: RootKeyRemediationMode,
        correlation_id: str,
    ) -> None:
        if run.account_id != account_id or run.control_id != control_id:
            raise self._terminal_error("idempotency_payload_mismatch", "Idempotent replay payload mismatch.")
        if run.action_id != action_id or run.finding_id != finding_id:
            raise self._terminal_error("idempotency_payload_mismatch", "Idempotent replay payload mismatch.")
        if run.strategy_id != strategy_id or run.mode != mode:
            raise self._terminal_error("idempotency_payload_mismatch", "Idempotent replay payload mismatch.")
        if run.correlation_id != correlation_id:
            raise self._terminal_error("idempotency_payload_mismatch", "Idempotent replay payload mismatch.")

    def _retryable_error(self, code: str, message: str) -> RootKeyStateMachineError:
        return RootKeyStateMachineError(
            RootKeyErrorClassification(
                code=code,
                message=message,
                disposition=RootKeyErrorDisposition.retryable,
            )
        )

    def _terminal_error(self, code: str, message: str) -> RootKeyStateMachineError:
        return RootKeyStateMachineError(
            RootKeyErrorClassification(
                code=code,
                message=message,
                disposition=RootKeyErrorDisposition.terminal,
            )
        )
