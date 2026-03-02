from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.enums import RootKeyArtifactStatus, RootKeyRemediationState
from backend.services.root_key_remediation_state_machine import (
    RootKeyErrorClassification,
    RootKeyErrorDisposition,
    RootKeyRemediationStateMachineService,
    RootKeyStateMachineError,
    RootKeyTransitionResult,
)
from backend.services.root_key_remediation_store import (
    create_root_key_remediation_artifact_idempotent,
    get_root_key_remediation_run,
)

ClosureTrigger = Callable[..., Awaitable[dict[str, Any] | None]]
ClosurePoller = Callable[..., Awaitable["RootKeyClosureSnapshot"]]
SleepFn = Callable[[float], Awaitable[None]]

_SECRET_TOKENS = (
    "password",
    "secret",
    "token",
    "authorization",
    "access_key",
    "session_key",
)


@dataclass(frozen=True)
class RootKeyClosureSnapshot:
    action_resolved: bool
    finding_resolved: bool
    policy_preservation_passed: bool
    unresolved_external_tasks: int
    payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class RootKeyClosureResult:
    transition_result: RootKeyTransitionResult
    closure_completed: bool
    idempotency_replayed: bool
    polls_used: int
    final_snapshot: RootKeyClosureSnapshot | None


class RootKeyRemediationClosureService:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        max_polls: int | None = None,
        poll_interval_seconds: float | None = None,
        ingest_trigger: ClosureTrigger | None = None,
        compute_trigger: ClosureTrigger | None = None,
        reconcile_trigger: ClosureTrigger | None = None,
        poller: ClosurePoller | None = None,
        sleep_fn: SleepFn = asyncio.sleep,
    ) -> None:
        default_enabled = (
            settings.ROOT_KEY_SAFE_REMEDIATION_ENABLED
            and settings.ROOT_KEY_SAFE_REMEDIATION_STRICT_TRANSITIONS
            and settings.ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED
        )
        self._enabled = default_enabled if enabled is None else bool(enabled)
        configured_max = max_polls or settings.ROOT_KEY_SAFE_REMEDIATION_CLOSURE_MAX_POLLS
        configured_interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else settings.ROOT_KEY_SAFE_REMEDIATION_CLOSURE_POLL_INTERVAL_SECONDS
        )
        self._max_polls = max(1, int(configured_max))
        self._poll_interval_seconds = max(0.0, float(configured_interval))
        self._ingest_trigger = ingest_trigger or self._default_trigger
        self._compute_trigger = compute_trigger or self._default_trigger
        self._reconcile_trigger = reconcile_trigger or self._default_trigger
        self._poller = poller or self._default_poller
        self._sleep = sleep_fn

    async def execute_closure_cycle(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        state_machine: RootKeyRemediationStateMachineService,
        actor_metadata: dict[str, Any] | None = None,
    ) -> RootKeyClosureResult:
        self._ensure_enabled()
        run = await self._require_run(db=db, tenant_id=tenant_id, run_id=run_id)
        if run.state == RootKeyRemediationState.completed:
            return RootKeyClosureResult(
                transition_result=self._unchanged(run),
                closure_completed=True,
                idempotency_replayed=True,
                polls_used=0,
                final_snapshot=None,
            )
        self._ensure_closure_state(run.state)
        actor_payload = _sanitize_json(actor_metadata or {})
        try:
            dispatch = await self._dispatch_triggers(
                db=db,
                run=run,
                tenant_id=tenant_id,
                transition_id=transition_id,
            )
        except Exception as exc:
            reason = f"closure_trigger_error:{type(exc).__name__}"
            return await self._mark_needs_attention_result(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:dispatch_error",
                reason=reason,
                actor_metadata=actor_payload,
                dispatch=[],
                polls_used=0,
                final_snapshot=None,
                idempotency_key=f"{transition_id}:closure_summary",
            )
        if not all(item["accepted"] for item in dispatch):
            reason = self._first_dispatch_rejection(dispatch)
            return await self._mark_needs_attention_result(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:dispatch_rejected",
                reason=reason,
                actor_metadata=actor_payload,
                dispatch=dispatch,
                polls_used=0,
                final_snapshot=None,
                idempotency_key=f"{transition_id}:closure_summary",
            )
        try:
            poll_result = await self._poll_for_closure(
                db=db,
                run=run,
                tenant_id=tenant_id,
                transition_id=transition_id,
            )
        except Exception as exc:
            reason = f"closure_poll_error:{type(exc).__name__}"
            return await self._mark_needs_attention_result(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:poll_error",
                reason=reason,
                actor_metadata=actor_payload,
                dispatch=dispatch,
                polls_used=0,
                final_snapshot=None,
                idempotency_key=f"{transition_id}:closure_summary",
            )
        if poll_result["policy_failed"]:
            return await self._mark_needs_attention_result(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:policy_failed",
                reason="policy_preservation_failed",
                actor_metadata=actor_payload,
                dispatch=dispatch,
                polls_used=poll_result["polls_used"],
                final_snapshot=poll_result["final_snapshot"],
                idempotency_key=f"{transition_id}:closure_summary",
            )
        if poll_result["timed_out"]:
            fail_result = await state_machine.fail_run(
                db,
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id=f"{transition_id}:timeout",
                failure_reason="closure_timeout",
                actor_metadata=actor_payload,
                evidence_metadata={"operation": "closure_timeout"},
            )
            created = await self._record_summary(
                db=db,
                run=fail_result.run,
                transition_id=transition_id,
                dispatch=dispatch,
                polls_used=poll_result["polls_used"],
                final_snapshot=poll_result["final_snapshot"],
                terminal_state="failed",
                idempotency_key=f"{transition_id}:closure_summary",
                actor_metadata=actor_payload,
            )
            return RootKeyClosureResult(
                transition_result=fail_result,
                closure_completed=False,
                idempotency_replayed=not created,
                polls_used=poll_result["polls_used"],
                final_snapshot=poll_result["final_snapshot"],
            )
        complete_result = await state_machine.finalize_delete(
            db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=f"{transition_id}:complete",
            actor_metadata=actor_payload,
            evidence_metadata={
                "operation": "closure_complete",
                "polls_used": poll_result["polls_used"],
            },
        )
        created = await self._record_summary(
            db=db,
            run=complete_result.run,
            transition_id=transition_id,
            dispatch=dispatch,
            polls_used=poll_result["polls_used"],
            final_snapshot=poll_result["final_snapshot"],
            terminal_state="completed",
            idempotency_key=f"{transition_id}:closure_summary",
            actor_metadata=actor_payload,
        )
        return RootKeyClosureResult(
            transition_result=complete_result,
            closure_completed=True,
            idempotency_replayed=not created,
            polls_used=poll_result["polls_used"],
            final_snapshot=poll_result["final_snapshot"],
        )

    async def _dispatch_triggers(
        self,
        *,
        db: AsyncSession,
        run: Any,
        tenant_id: uuid.UUID,
        transition_id: str,
    ) -> list[dict[str, Any]]:
        operations: list[tuple[str, ClosureTrigger]] = [
            ("ingest", self._ingest_trigger),
            ("compute", self._compute_trigger),
            ("reconcile", self._reconcile_trigger),
        ]
        dispatch: list[dict[str, Any]] = []
        for stage, trigger in operations:
            payload = await trigger(
                db=db,
                run=run,
                tenant_id=tenant_id,
                idempotency_key=f"{transition_id}:{stage}",
            )
            dispatch.append(
                {
                    "stage": stage,
                    "accepted": _trigger_accepted(payload),
                    "payload": _sanitize_json(payload),
                }
            )
        return dispatch

    async def _poll_for_closure(
        self,
        *,
        db: AsyncSession,
        run: Any,
        tenant_id: uuid.UUID,
        transition_id: str,
    ) -> dict[str, Any]:
        final_snapshot: RootKeyClosureSnapshot | None = None
        policy_failed = False
        for poll_attempt in range(1, self._max_polls + 1):
            snapshot = await self._poller(
                db=db,
                run=run,
                tenant_id=tenant_id,
                poll_attempt=poll_attempt,
                idempotency_key=f"{transition_id}:poll:{poll_attempt}",
            )
            final_snapshot = snapshot
            if not snapshot.policy_preservation_passed:
                policy_failed = True
                break
            if self._snapshot_ready(snapshot):
                return {
                    "timed_out": False,
                    "policy_failed": False,
                    "polls_used": poll_attempt,
                    "final_snapshot": snapshot,
                }
            if poll_attempt < self._max_polls and self._poll_interval_seconds > 0:
                await self._sleep(self._poll_interval_seconds)
        return {
            "timed_out": not policy_failed,
            "policy_failed": policy_failed,
            "polls_used": self._max_polls,
            "final_snapshot": final_snapshot,
        }

    async def _mark_needs_attention_result(
        self,
        *,
        db: AsyncSession,
        run: Any,
        state_machine: RootKeyRemediationStateMachineService,
        transition_id: str,
        reason: str,
        actor_metadata: dict[str, Any],
        dispatch: list[dict[str, Any]],
        polls_used: int,
        final_snapshot: RootKeyClosureSnapshot | None,
        idempotency_key: str,
    ) -> RootKeyClosureResult:
        transition = await state_machine.mark_needs_attention(
            db,
            tenant_id=run.tenant_id,
            run_id=run.id,
            transition_id=transition_id,
            actor_metadata=actor_metadata,
            evidence_metadata={"operation": "closure_needs_attention", "reason": reason},
        )
        created = await self._record_summary(
            db=db,
            run=transition.run,
            transition_id=transition_id,
            dispatch=dispatch,
            polls_used=polls_used,
            final_snapshot=final_snapshot,
            terminal_state="needs_attention",
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )
        return RootKeyClosureResult(
            transition_result=transition,
            closure_completed=False,
            idempotency_replayed=not created,
            polls_used=polls_used,
            final_snapshot=final_snapshot,
        )

    async def _record_summary(
        self,
        *,
        db: AsyncSession,
        run: Any,
        transition_id: str,
        dispatch: list[dict[str, Any]],
        polls_used: int,
        final_snapshot: RootKeyClosureSnapshot | None,
        terminal_state: str,
        idempotency_key: str,
        actor_metadata: dict[str, Any],
    ) -> bool:
        summary = {
            "transition_id": transition_id,
            "terminal_state": terminal_state,
            "dispatch": dispatch,
            "polls_used": polls_used,
            "final_snapshot": _snapshot_payload(final_snapshot),
        }
        _, created = await create_root_key_remediation_artifact_idempotent(
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
            artifact_type="closure_cycle_summary",
            metadata_json=_sanitize_json(summary),
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )
        return bool(created)

    async def _require_run(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Any:
        run = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise self._terminal_error("tenant_scope_violation", "Run was not found in tenant scope.")
        return run

    def _ensure_enabled(self) -> None:
        if self._enabled:
            return
        raise self._terminal_error(
            "feature_flag_disabled",
            "Root-key closure orchestration is disabled by feature flags.",
        )

    def _ensure_closure_state(self, run_state: RootKeyRemediationState) -> None:
        if run_state in {RootKeyRemediationState.disable_window, RootKeyRemediationState.delete_window}:
            return
        raise self._terminal_error(
            "illegal_transition",
            "Closure cycle requires disable_window or delete_window state.",
        )

    def _snapshot_ready(self, snapshot: RootKeyClosureSnapshot) -> bool:
        if snapshot.unresolved_external_tasks > 0:
            return False
        return snapshot.action_resolved and snapshot.finding_resolved

    def _first_dispatch_rejection(self, dispatch: list[dict[str, Any]]) -> str:
        for item in dispatch:
            if not item["accepted"]:
                return f"{item['stage']}_trigger_rejected"
        return "closure_trigger_rejected"

    async def _default_trigger(self, **_: Any) -> dict[str, Any] | None:
        raise self._terminal_error(
            "closure_trigger_unconfigured",
            "Closure trigger callable is not configured.",
        )

    async def _default_poller(self, **_: Any) -> RootKeyClosureSnapshot:
        raise self._terminal_error(
            "closure_poller_unconfigured",
            "Closure poller callable is not configured.",
        )

    def _unchanged(self, run: Any) -> RootKeyTransitionResult:
        return RootKeyTransitionResult(
            run=run,
            state_changed=False,
            event_created=False,
            evidence_created=False,
            attempts=1,
        )

    def _terminal_error(self, code: str, message: str) -> RootKeyStateMachineError:
        return RootKeyStateMachineError(
            RootKeyErrorClassification(
                code=code,
                message=message,
                disposition=RootKeyErrorDisposition.terminal,
            )
        )


def _trigger_accepted(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return False
    if "accepted" in payload:
        return bool(payload["accepted"])
    status_value = str(payload.get("status") or "").strip().lower()
    if status_value in {"accepted", "queued", "ok", "success"}:
        return True
    status_code = payload.get("status_code")
    if isinstance(status_code, int):
        return status_code in {200, 201, 202}
    return False


def _snapshot_payload(snapshot: RootKeyClosureSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "action_resolved": bool(snapshot.action_resolved),
        "finding_resolved": bool(snapshot.finding_resolved),
        "policy_preservation_passed": bool(snapshot.policy_preservation_passed),
        "unresolved_external_tasks": int(snapshot.unresolved_external_tasks),
        "payload": _sanitize_json(snapshot.payload or {}),
    }


def _is_secret_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(token in lowered for token in _SECRET_TOKENS)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            if _is_secret_key(str(key)):
                sanitized[str(key)] = "<REDACTED>"
            else:
                sanitized[str(key)] = _sanitize_json(nested)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value
