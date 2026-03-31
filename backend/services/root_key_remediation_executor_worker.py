from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.action import Action
from backend.models.enums import (
    RootKeyArtifactStatus,
    RootKeyDependencyStatus,
    RootKeyExternalTaskStatus,
)
from backend.models.finding import Finding
from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_external_task import RootKeyExternalTask
from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
from backend.services.root_key_remediation_closure import (
    RootKeyClosureSnapshot,
    RootKeyRemediationClosureService,
)
from backend.services.root_key_remediation_state_machine import (
    RootKeyErrorClassification,
    RootKeyErrorDisposition,
    RootKeyRemediationStateMachineService,
    RootKeyStateMachineError,
    RootKeyTransitionResult,
)
from backend.services.root_key_remediation_store import (
    create_root_key_external_task_idempotent,
    create_root_key_remediation_artifact_idempotent,
    get_root_key_remediation_run,
)
from backend.services.root_key_usage_discovery import RootKeyUsageDiscoveryService
from backend.utils.sqs import (
    build_compute_actions_job_payload,
    build_ingest_job_payload,
    build_reconcile_inventory_shard_job_payload,
    parse_queue_region,
)

_SELF_CUTOFF_GUARD_CODE = "self_cutoff_guard_not_guaranteed"
_DISABLE_PRESERVED_CALLER_KEY_CODE = "mutation_key_preserved_requires_new_credential_context"
_DELETE_GATING_VALIDATION_CODE = "delete_validation_not_passed"
_DELETE_GATING_CLEAN_WINDOW_CODE = "delete_disable_window_not_clean"
_DELETE_GATING_DISABLED_CODE = "delete_window_disabled"
_DELETE_GATING_DEPENDENCY_CODE = "delete_unknown_dependencies"
_DELETE_GATING_ACTIVE_KEYS_CODE = "delete_active_keys_present"
_DELETE_GATING_ROOT_MFA_CODE = "root_mfa_not_enrolled"
_ROLLBACK_ALERT_TASK_TYPE = "rollback_alert"
FINAL_ROOT_KEY_MANUAL_DELETE_TASK_TYPE = "final_root_key_manual_delete_required"
_MASKED_EMPTY_KEY = "<EMPTY>"

_CredentialSessionFactory = Callable[[str, str | None], Any]
_UsageDiscoveryFactory = Callable[[], RootKeyUsageDiscoveryService]
_ClosureServiceFactory = Callable[[], RootKeyRemediationClosureService]


@dataclass(frozen=True)
class _ExecutionSessions:
    mutation_session: Any
    observer_session: Any
    mutation_access_key_id: str | None
    observer_access_key_id: str | None

    @property
    def has_separate_observer_context(self) -> bool:
        if not self.mutation_access_key_id or not self.observer_access_key_id:
            return False
        return self.mutation_access_key_id != self.observer_access_key_id


@dataclass(frozen=True)
class _DisableSignals:
    window_clean: bool
    root_keys_present: int | None
    managed_usage_count: int
    unknown_usage_count: int
    partial_data: bool
    breakage_signals: tuple[str, ...]
    retries_used: int


def _default_session_factory(account_id: str, region: str | None) -> Any:
    del account_id
    return boto3.Session(region_name=region or settings.AWS_REGION)


def _default_usage_discovery_factory() -> RootKeyUsageDiscoveryService:
    return RootKeyUsageDiscoveryService(enabled=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _mask_access_key_id(access_key_id: str | None) -> str:
    key = str(access_key_id or "").strip()
    if not key:
        return _MASKED_EMPTY_KEY
    if len(key) < 8:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
        return f"key-{digest}"
    return f"{key[:4]}...{key[-4:]}"


def _extract_access_key_id(session_boto: Any) -> str | None:
    credentials = session_boto.get_credentials() if hasattr(session_boto, "get_credentials") else None
    if credentials is None:
        return None
    if hasattr(credentials, "get_frozen_credentials"):
        frozen = credentials.get_frozen_credentials()
        key = getattr(frozen, "access_key", None)
        return str(key).strip() if key else None
    key = getattr(credentials, "access_key", None)
    return str(key).strip() if key else None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


class RootKeyRemediationExecutorWorker:
    def __init__(
        self,
        *,
        mutation_session_factory: _CredentialSessionFactory = _default_session_factory,
        observer_session_factory: _CredentialSessionFactory | None = None,
        observer_only_delete_finalize: bool = False,
        usage_discovery_factory: _UsageDiscoveryFactory = _default_usage_discovery_factory,
        closure_service_factory: _ClosureServiceFactory | None = None,
        now_fn: Callable[[], datetime] = _utc_now,
        monitor_lookback_minutes: int | None = None,
    ) -> None:
        self._mutation_session_factory = mutation_session_factory
        self._observer_session_factory = observer_session_factory or mutation_session_factory
        self._observer_only_delete_finalize = bool(observer_only_delete_finalize)
        self._usage_discovery_factory = usage_discovery_factory
        self._closure_service_factory = closure_service_factory or self._default_closure_service_factory
        self._now = now_fn
        default_lookback = getattr(settings, "ROOT_KEY_SAFE_REMEDIATION_MONITOR_LOOKBACK_MINUTES", 15)
        configured_lookback = monitor_lookback_minutes if monitor_lookback_minutes is not None else default_lookback
        self._monitor_lookback_minutes = max(1, int(configured_lookback))

    async def execute_disable(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        state_machine: RootKeyRemediationStateMachineService,
        actor_metadata: dict[str, Any] | None = None,
    ) -> RootKeyTransitionResult:
        run = await self._require_run(db=db, tenant_id=tenant_id, run_id=run_id)
        sessions = self._build_execution_sessions(run)
        key_states = self._list_root_key_states(sessions.mutation_session, run.region)
        guard_reason = self._evaluate_self_cutoff_guard(key_states=key_states, sessions=sessions)
        if guard_reason:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:guard",
                reason=f"{_SELF_CUTOFF_GUARD_CODE}:{guard_reason}",
                actor_metadata=actor_metadata,
            )

        try:
            disable_summary = self._disable_root_keys(
                session_boto=sessions.mutation_session,
                region=run.region,
                key_states=key_states,
                mutation_access_key_id=sessions.mutation_access_key_id,
            )
        except RootKeyStateMachineError:
            raise
        except Exception as exc:
            reason = f"disable_execution_error:{type(exc).__name__}"
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:disable_error",
                reason=reason,
                actor_metadata=actor_metadata,
            )
        disable_result = await state_machine.start_disable_window(
            db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            actor_metadata=actor_metadata,
            evidence_metadata={
                "operation": "disable",
                "disabled_key_count": disable_summary["disabled_count"],
                "skipped_key_count": disable_summary["skipped_count"],
            },
        )
        signals = await self._collect_disable_signals(
            db=db,
            run=disable_result.run,
            observer_session=sessions.observer_session,
            mutation_session=sessions.mutation_session,
        )
        await self._record_disable_evidence(
            db=db,
            run=disable_result.run,
            transition_id=transition_id,
            disable_summary=disable_summary,
            signals=signals,
            operator_attention_reason=self._disable_progression_block_reason(disable_summary),
            actor_metadata=actor_metadata,
        )
        progression_block_reason = self._disable_progression_block_reason(disable_summary)
        if signals.breakage_signals:
            reason = f"disable_breakage_signals:{','.join(signals.breakage_signals)}"
            try:
                rollback_summary = self._rollback_summary(
                    session_boto=sessions.mutation_session,
                    region=run.region,
                )
            except Exception as exc:
                reason = f"{reason},rollback_execution_error:{type(exc).__name__}"
                rollback_summary = {
                    "reactivated_count": 0,
                    "skipped_count": 0,
                    "reactivated_keys": [],
                    "skipped_keys": [],
                    "rollback_execution_error": type(exc).__name__,
                }
            return await self._rollback_with_alert(
                db=db,
                run=disable_result.run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:rollback",
                rollback_reason=reason,
                actor_metadata=actor_metadata,
                evidence_payload={
                    **rollback_summary,
                    "disable_summary": disable_summary,
                    "signals": self._signals_payload(signals),
                },
            )
        if progression_block_reason is not None:
            if progression_block_reason == _DISABLE_PRESERVED_CALLER_KEY_CODE:
                await self._create_final_key_manual_delete_task(
                    db=db,
                    run=disable_result.run,
                    idempotency_key=f"{transition_id}:final-key-task",
                    disable_summary=disable_summary,
                    actor_metadata=actor_metadata,
                )
            return await self._mark_needs_attention(
                db=db,
                run=disable_result.run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:operator_attention",
                reason=progression_block_reason,
                actor_metadata=actor_metadata,
            )
        return disable_result

    async def execute_rollback(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        rollback_reason: str,
        state_machine: RootKeyRemediationStateMachineService,
        actor_metadata: dict[str, Any] | None = None,
    ) -> RootKeyTransitionResult:
        run = await self._require_run(db=db, tenant_id=tenant_id, run_id=run_id)
        sessions = self._build_execution_sessions(run)
        try:
            rollback_summary = self._rollback_summary(
                session_boto=sessions.mutation_session,
                region=run.region,
            )
        except RootKeyStateMachineError:
            raise
        except Exception as exc:
            reason = f"rollback_execution_error:{type(exc).__name__}"
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:rollback_error",
                reason=reason,
                actor_metadata=actor_metadata,
            )
        rollback_result = await state_machine.rollback(
            db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            rollback_reason=rollback_reason,
            actor_metadata=actor_metadata,
            evidence_metadata={
                "operation": "rollback",
                "reactivated_key_count": rollback_summary["reactivated_count"],
            },
        )
        await self._record_rollback_evidence(
            db=db,
            run=rollback_result.run,
            transition_id=transition_id,
            rollback_reason=rollback_reason,
            rollback_summary=rollback_summary,
            actor_metadata=actor_metadata,
        )
        await self._create_rollback_alert_task(
            db=db,
            run=rollback_result.run,
            idempotency_key=f"{transition_id}:alert",
            rollback_reason=rollback_reason,
            actor_metadata=actor_metadata,
        )
        return rollback_result

    async def execute_delete(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        state_machine: RootKeyRemediationStateMachineService,
        actor_metadata: dict[str, Any] | None = None,
    ) -> RootKeyTransitionResult:
        run = await self._require_run(db=db, tenant_id=tenant_id, run_id=run_id)
        delete_gate_error = await self._delete_gate_error(db=db, run=run)
        if delete_gate_error is not None:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:gate",
                reason=delete_gate_error,
                actor_metadata=actor_metadata,
            )

        sessions = self._build_execution_sessions(run)
        mfa_enrolled = self._is_root_mfa_enrolled(sessions.observer_session, run.region)
        if mfa_enrolled is False:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:mfa_gate",
                reason=_DELETE_GATING_ROOT_MFA_CODE,
                actor_metadata=actor_metadata,
            )

        if self._observer_only_delete_finalize:
            return await self._finalize_manual_delete_handoff(
                db=db,
                run=run,
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id=transition_id,
                state_machine=state_machine,
                actor_metadata=actor_metadata,
                observer_session=sessions.observer_session,
            )

        key_states = self._list_root_key_states(sessions.mutation_session, run.region)
        active_keys = [item["access_key_id"] for item in key_states if item["status"] == "active"]
        if active_keys:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:active_key_gate",
                reason=f"{_DELETE_GATING_ACTIVE_KEYS_CODE}:{len(active_keys)}",
                actor_metadata=actor_metadata,
            )

        guard_reason = self._evaluate_self_cutoff_guard(key_states=key_states, sessions=sessions)
        if guard_reason:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:guard",
                reason=f"{_SELF_CUTOFF_GUARD_CODE}:{guard_reason}",
                actor_metadata=actor_metadata,
            )

        try:
            delete_summary = self._delete_root_keys(
                session_boto=sessions.mutation_session,
                region=run.region,
                key_states=key_states,
                mutation_access_key_id=sessions.mutation_access_key_id,
            )
        except RootKeyStateMachineError:
            raise
        except Exception as exc:
            reason = f"delete_execution_error:{type(exc).__name__}"
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:delete_error",
                reason=reason,
                actor_metadata=actor_metadata,
            )
        post_delete_states = self._list_root_key_states(sessions.mutation_session, run.region)
        required_safe_permissions_unchanged = len(post_delete_states) == 0
        await self._record_delete_evidence(
            db=db,
            run=run,
            transition_id=transition_id,
            delete_summary=delete_summary,
            remaining_root_keys=len(post_delete_states),
            required_safe_permissions_unchanged=required_safe_permissions_unchanged,
            actor_metadata=actor_metadata,
        )
        if self._closure_enabled():
            closure = self._closure_service_factory()
            closure_result = await closure.execute_closure_cycle(
                db,
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id=f"{transition_id}:closure",
                state_machine=state_machine,
                actor_metadata=actor_metadata,
            )
            return closure_result.transition_result

        return await state_machine.finalize_delete(
            db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            actor_metadata=actor_metadata,
            evidence_metadata={
                "operation": "delete",
                "deleted_key_count": delete_summary["deleted_count"],
                "skipped_key_count": delete_summary["skipped_count"],
            },
        )

    async def _require_run(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Any:
        run = await get_root_key_remediation_run(db, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise RootKeyStateMachineError(
                RootKeyErrorClassification(
                    code="tenant_scope_violation",
                    message="Run was not found in tenant scope.",
                    disposition=RootKeyErrorDisposition.terminal,
                )
            )
        return run

    def _build_execution_sessions(self, run: Any) -> _ExecutionSessions:
        mutation = self._mutation_session_factory(run.account_id, run.region)
        observer = self._observer_session_factory(run.account_id, run.region)
        return _ExecutionSessions(
            mutation_session=mutation,
            observer_session=observer,
            mutation_access_key_id=_extract_access_key_id(mutation),
            observer_access_key_id=_extract_access_key_id(observer),
        )

    def _evaluate_self_cutoff_guard(
        self,
        *,
        key_states: list[dict[str, str]],
        sessions: _ExecutionSessions,
    ) -> str | None:
        key_ids = {item["access_key_id"] for item in key_states}
        observer_key = sessions.observer_access_key_id
        if key_ids and not observer_key:
            return "observer_credentials_identity_unavailable"
        if observer_key and observer_key in key_ids and not sessions.has_separate_observer_context:
            return "observer_credentials_overlap_with_mutation_target"
        return None

    def _list_root_key_states(self, session_boto: Any, region: str | None) -> list[dict[str, str]]:
        client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
        response = client.list_access_keys()
        metadata = response.get("AccessKeyMetadata") if isinstance(response, dict) else None
        if not isinstance(metadata, list):
            return []
        rows: list[dict[str, str]] = []
        for item in metadata:
            if not isinstance(item, dict):
                continue
            key_id = str(item.get("AccessKeyId") or "").strip()
            status = str(item.get("Status") or "").strip().lower()
            if not key_id:
                continue
            normalized = "inactive" if status == "inactive" else "active"
            rows.append({"access_key_id": key_id, "status": normalized})
        rows.sort(key=lambda row: row["access_key_id"])
        return rows

    def _is_root_mfa_enrolled(self, session_boto: Any, region: str | None) -> bool | None:
        client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
        try:
            summary = client.get_account_summary()
        except Exception:
            return None
        summary_map = summary.get("SummaryMap") if isinstance(summary, dict) else None
        if not isinstance(summary_map, dict):
            return None
        mfa_enabled = _safe_int(summary_map.get("AccountMFAEnabled"))
        if mfa_enabled is None:
            return None
        return mfa_enabled == 1

    def _disable_root_keys(
        self,
        *,
        session_boto: Any,
        region: str | None,
        key_states: list[dict[str, str]],
        mutation_access_key_id: str | None,
    ) -> dict[str, Any]:
        client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
        ordered_states = self._ordered_for_mutation(
            key_states=key_states,
            mutation_access_key_id=mutation_access_key_id,
        )
        disabled: list[str] = []
        skipped: list[str] = []
        caller_key_preserved: str | None = None
        for item in ordered_states:
            key_id = item["access_key_id"]
            # Never disable the key we are currently using to make the IAM call.
            # Disabling our own key would invalidate the session before rollback
            # can run and leave the account in a permanently locked state.
            if mutation_access_key_id and key_id == mutation_access_key_id:
                caller_key_preserved = _mask_access_key_id(key_id)
                continue
            if item["status"] == "inactive":
                skipped.append(_mask_access_key_id(key_id))
                continue
            client.update_access_key(AccessKeyId=key_id, Status="Inactive")
            disabled.append(_mask_access_key_id(key_id))
        result: dict[str, Any] = {
            "disabled_count": len(disabled),
            "skipped_count": len(skipped),
            "disabled_keys": disabled,
            "skipped_keys": skipped,
        }
        if caller_key_preserved is not None:
            result["caller_key_preserved"] = caller_key_preserved
        return result

    def _rollback_summary(
        self,
        *,
        session_boto: Any,
        region: str | None,
    ) -> dict[str, Any]:
        return self._reactivate_inactive_root_keys(
            session_boto=session_boto,
            region=region,
            key_states=self._list_root_key_states(session_boto, region),
        )

    def _reactivate_inactive_root_keys(
        self,
        *,
        session_boto: Any,
        region: str | None,
        key_states: list[dict[str, str]],
    ) -> dict[str, Any]:
        client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
        reactivated: list[str] = []
        skipped: list[str] = []
        for item in key_states:
            key_id = item["access_key_id"]
            if item["status"] == "active":
                skipped.append(_mask_access_key_id(key_id))
                continue
            client.update_access_key(AccessKeyId=key_id, Status="Active")
            reactivated.append(_mask_access_key_id(key_id))
        return {
            "reactivated_count": len(reactivated),
            "skipped_count": len(skipped),
            "reactivated_keys": reactivated,
            "skipped_keys": skipped,
        }

    def _delete_root_keys(
        self,
        *,
        session_boto: Any,
        region: str | None,
        key_states: list[dict[str, str]],
        mutation_access_key_id: str | None,
    ) -> dict[str, Any]:
        client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
        ordered_states = self._ordered_for_mutation(
            key_states=key_states,
            mutation_access_key_id=mutation_access_key_id,
        )
        deleted: list[str] = []
        skipped: list[str] = []
        for item in ordered_states:
            key_id = item["access_key_id"]
            if item["status"] != "inactive":
                skipped.append(_mask_access_key_id(key_id))
                continue
            client.delete_access_key(AccessKeyId=key_id)
            deleted.append(_mask_access_key_id(key_id))
        return {
            "deleted_count": len(deleted),
            "skipped_count": len(skipped),
            "deleted_keys": deleted,
            "skipped_keys": skipped,
        }

    async def _discover_usage_result(
        self,
        *,
        db: AsyncSession,
        run: Any,
        session_boto: Any,
    ) -> Any:
        usage_service = self._usage_discovery_factory()
        return await usage_service.discover_and_classify(
            db=db,
            session_boto=session_boto,
            tenant_id=run.tenant_id,
            run_id=run.id,
            lookback_minutes=self._monitor_lookback_minutes,
            now=self._now(),
        )

    def _root_keys_present_signal(
        self,
        *,
        session_boto: Any,
        region: str | None,
    ) -> tuple[int | None, bool]:
        try:
            client = session_boto.client("iam", region_name=region or settings.AWS_REGION)
            account_summary = client.get_account_summary()
        except Exception:
            return None, True
        summary_map = account_summary.get("SummaryMap") if isinstance(account_summary, dict) else {}
        if not isinstance(summary_map, dict):
            return None, False
        return _safe_int(summary_map.get("AccountAccessKeysPresent")), False

    def _should_retry_with_mutation(
        self,
        *,
        primary_session: Any,
        fallback_session: Any | None,
        primary_failed: bool,
        primary_partial: bool,
    ) -> bool:
        if fallback_session is None or fallback_session is primary_session:
            return False
        return primary_failed or primary_partial

    async def _collect_disable_signals(
        self,
        *,
        db: AsyncSession,
        run: Any,
        observer_session: Any,
        mutation_session: Any | None = None,
    ) -> _DisableSignals:
        breakage_signals: list[str] = []
        usage = SimpleNamespace(
            managed_count=0,
            unknown_count=0,
            partial_data=True,
            retries_used=0,
        )
        usage_failed = False
        try:
            usage = await self._discover_usage_result(
                db=db,
                run=run,
                session_boto=observer_session,
            )
        except Exception:
            usage_failed = True
        if self._should_retry_with_mutation(
            primary_session=observer_session,
            fallback_session=mutation_session,
            primary_failed=usage_failed,
            primary_partial=bool(usage.partial_data),
        ):
            try:
                usage = await self._discover_usage_result(
                    db=db,
                    run=run,
                    session_boto=mutation_session,
                )
                usage_failed = False
            except Exception:
                pass
        if usage_failed:
            breakage_signals.append("usage_signal_collection_failed")

        if usage.partial_data:
            breakage_signals.append("usage_signal_partial_data")
        if usage.unknown_count > 0:
            breakage_signals.append("unknown_root_usage_after_disable")

        root_keys_present, health_failed = self._root_keys_present_signal(
            session_boto=observer_session,
            region=run.region,
        )
        if self._should_retry_with_mutation(
            primary_session=observer_session,
            fallback_session=mutation_session,
            primary_failed=health_failed,
            primary_partial=root_keys_present is None,
        ):
            fallback_root_keys_present, fallback_health_failed = self._root_keys_present_signal(
                session_boto=mutation_session,
                region=run.region,
            )
            if not fallback_health_failed or fallback_root_keys_present is not None:
                root_keys_present = fallback_root_keys_present
                health_failed = fallback_health_failed
        if health_failed:
            breakage_signals.append("health_signal_collection_failed")
        if root_keys_present is None:
            breakage_signals.append("health_signal_unreadable")

        return _DisableSignals(
            window_clean=not breakage_signals,
            root_keys_present=root_keys_present,
            managed_usage_count=int(usage.managed_count),
            unknown_usage_count=int(usage.unknown_count),
            partial_data=bool(usage.partial_data),
            breakage_signals=tuple(sorted(set(breakage_signals))),
            retries_used=int(usage.retries_used),
        )

    def _ordered_for_mutation(
        self,
        *,
        key_states: list[dict[str, str]],
        mutation_access_key_id: str | None,
    ) -> list[dict[str, str]]:
        if not mutation_access_key_id:
            return list(key_states)
        primary = [item for item in key_states if item["access_key_id"] != mutation_access_key_id]
        tail = [item for item in key_states if item["access_key_id"] == mutation_access_key_id]
        return primary + tail

    async def _delete_gate_error(self, *, db: AsyncSession, run: Any) -> str | None:
        if str(getattr(run.state, "value", run.state)) not in {"disable_window", "delete_window"}:
            return _DELETE_GATING_VALIDATION_CODE
        if not await self._is_disable_window_clean(db=db, run=run):
            return _DELETE_GATING_CLEAN_WINDOW_CODE
        if not bool(settings.ROOT_KEY_SAFE_REMEDIATION_DELETE_ENABLED):
            return _DELETE_GATING_DISABLED_CODE
        if await self._has_unknown_active_dependencies(db=db, run=run):
            return _DELETE_GATING_DEPENDENCY_CODE
        return None

    async def _is_disable_window_clean(self, *, db: AsyncSession, run: Any) -> bool:
        metadata = await self._latest_disable_window_metadata(db=db, run=run)
        if not isinstance(metadata, dict):
            return False
        if metadata.get("window_clean") is True:
            return True
        return await self._manual_final_key_handoff_completed_without_breakage(
            db=db,
            run=run,
            metadata=metadata,
        )

    async def _latest_disable_window_metadata(self, *, db: AsyncSession, run: Any) -> dict[str, Any] | None:
        result = await db.execute(
            select(RootKeyRemediationArtifact.metadata_json)
            .where(
                RootKeyRemediationArtifact.tenant_id == run.tenant_id,
                RootKeyRemediationArtifact.run_id == run.id,
                RootKeyRemediationArtifact.artifact_type == "disable_window_evidence",
            )
            .order_by(RootKeyRemediationArtifact.created_at.desc())
            .limit(1)
        )
        metadata = result.scalar_one_or_none()
        return metadata if isinstance(metadata, dict) else None

    async def _manual_final_key_handoff_completed_without_breakage(
        self,
        *,
        db: AsyncSession,
        run: Any,
        metadata: dict[str, Any],
    ) -> bool:
        if metadata.get("operator_attention_reason") != _DISABLE_PRESERVED_CALLER_KEY_CODE:
            return False
        if bool(metadata.get("partial_data")):
            return False
        if int(metadata.get("unknown_usage_count") or 0) > 0:
            return False
        breakage_signals = metadata.get("breakage_signals")
        if isinstance(breakage_signals, list) and breakage_signals:
            return False
        if isinstance(breakage_signals, tuple) and breakage_signals:
            return False
        result = await db.execute(
            select(RootKeyExternalTask.id)
            .where(
                RootKeyExternalTask.tenant_id == run.tenant_id,
                RootKeyExternalTask.run_id == run.id,
                RootKeyExternalTask.task_type == FINAL_ROOT_KEY_MANUAL_DELETE_TASK_TYPE,
                RootKeyExternalTask.status == RootKeyExternalTaskStatus.completed,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _finalize_manual_delete_handoff(
        self,
        *,
        db: AsyncSession,
        run: Any,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
        transition_id: str,
        state_machine: RootKeyRemediationStateMachineService,
        actor_metadata: dict[str, Any] | None,
        observer_session: Any,
    ) -> RootKeyTransitionResult:
        remaining_root_keys, health_failed = self._root_keys_present_signal(
            session_boto=observer_session,
            region=run.region,
        )
        if health_failed or remaining_root_keys is None:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:observer_finalize_unreadable",
                reason="delete_manual_handoff_observer_unreadable",
                actor_metadata=actor_metadata,
            )
        if remaining_root_keys > 0:
            return await self._mark_needs_attention(
                db=db,
                run=run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:observer_finalize_active_keys",
                reason=f"{_DELETE_GATING_ACTIVE_KEYS_CODE}:{remaining_root_keys}",
                actor_metadata=actor_metadata,
            )
        delete_summary = {
            "deleted_count": 0,
            "skipped_count": 0,
            "deleted_keys": [],
            "skipped_keys": [],
            "manual_handoff_finalize": True,
        }
        await self._record_delete_evidence(
            db=db,
            run=run,
            transition_id=transition_id,
            delete_summary=delete_summary,
            remaining_root_keys=0,
            required_safe_permissions_unchanged=True,
            actor_metadata=actor_metadata,
        )
        if self._closure_enabled():
            closure = self._closure_service_factory()
            closure_result = await closure.execute_closure_cycle(
                db,
                tenant_id=tenant_id,
                run_id=run_id,
                transition_id=f"{transition_id}:closure",
                state_machine=state_machine,
                actor_metadata=actor_metadata,
            )
            return closure_result.transition_result
        return await state_machine.finalize_delete(
            db,
            tenant_id=tenant_id,
            run_id=run_id,
            transition_id=transition_id,
            actor_metadata=actor_metadata,
            evidence_metadata={
                "operation": "delete",
                "deleted_key_count": 0,
                "skipped_key_count": 0,
                "manual_handoff_finalize": True,
            },
        )

    async def _has_unknown_active_dependencies(self, *, db: AsyncSession, run: Any) -> bool:
        result = await db.execute(
            select(RootKeyDependencyFingerprint.id)
            .where(
                RootKeyDependencyFingerprint.tenant_id == run.tenant_id,
                RootKeyDependencyFingerprint.run_id == run.id,
                RootKeyDependencyFingerprint.unknown_dependency.is_(True),
                RootKeyDependencyFingerprint.status.in_(
                    (
                        RootKeyDependencyStatus.unknown,
                        RootKeyDependencyStatus.warn,
                        RootKeyDependencyStatus.fail,
                    )
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _closure_enabled(self) -> bool:
        return bool(getattr(settings, "ROOT_KEY_SAFE_REMEDIATION_CLOSURE_ENABLED", False))

    def _default_closure_service_factory(self) -> RootKeyRemediationClosureService:
        return RootKeyRemediationClosureService(
            enabled=True,
            ingest_trigger=self._closure_trigger_ingest,
            compute_trigger=self._closure_trigger_compute,
            reconcile_trigger=self._closure_trigger_reconcile,
            poller=self._closure_poller,
        )

    async def _closure_trigger_ingest(self, *, tenant_id: uuid.UUID, run: Any, **_: Any) -> dict[str, Any]:
        if not settings.has_ingest_queue:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": "ingest_queue_unavailable",
            }
        payload = build_ingest_job_payload(
            tenant_id=tenant_id,
            account_id=run.account_id,
            region=run.region or settings.AWS_REGION,
            created_at=self._now().isoformat(),
        )
        return self._send_queue_message(
            queue_url=settings.SQS_INGEST_QUEUE_URL,
            payload=payload,
        )

    async def _closure_trigger_compute(self, *, tenant_id: uuid.UUID, run: Any, **_: Any) -> dict[str, Any]:
        if not settings.has_ingest_queue:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": "compute_queue_unavailable",
            }
        payload = build_compute_actions_job_payload(
            tenant_id=tenant_id,
            created_at=self._now().isoformat(),
            account_id=run.account_id,
            region=run.region,
        )
        return self._send_queue_message(
            queue_url=settings.SQS_INGEST_QUEUE_URL,
            payload=payload,
        )

    async def _closure_trigger_reconcile(self, *, tenant_id: uuid.UUID, run: Any, **_: Any) -> dict[str, Any]:
        if not settings.has_inventory_reconcile_queue:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": "reconcile_queue_unavailable",
            }
        services = list(settings.control_plane_inventory_services_list)
        if not services:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": "reconcile_services_unconfigured",
            }
        max_resources = int(settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD or 500)
        queue_url = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL
        enqueued = 0
        for service in services:
            payload = build_reconcile_inventory_shard_job_payload(
                tenant_id=tenant_id,
                account_id=run.account_id,
                region=run.region or settings.AWS_REGION,
                service=service,
                created_at=self._now().isoformat(),
                sweep_mode="global",
                max_resources=max_resources,
            )
            response = self._send_queue_message(queue_url=queue_url, payload=payload)
            if not response.get("accepted", False):
                response["enqueued_jobs"] = enqueued
                return response
            enqueued += 1
        return {
            "accepted": True,
            "status_code": 202,
            "enqueued_jobs": enqueued,
        }

    def _send_queue_message(self, *, queue_url: str, payload: dict[str, Any]) -> dict[str, Any]:
        queue_url_normalized = (queue_url or "").strip()
        if not queue_url_normalized:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": "queue_url_unconfigured",
            }
        try:
            queue_region = parse_queue_region(queue_url_normalized)
            sqs = boto3.client("sqs", region_name=queue_region)
            response = sqs.send_message(
                QueueUrl=queue_url_normalized,
                MessageBody=json.dumps(payload),
            )
        except Exception as exc:
            return {
                "accepted": False,
                "status_code": 503,
                "reason": f"queue_send_failed:{type(exc).__name__}",
            }
        return {
            "accepted": True,
            "status_code": 202,
            "message_id": str(response.get("MessageId") or ""),
        }

    async def _closure_poller(
        self,
        *,
        db: AsyncSession,
        run: Any,
        poll_attempt: int,
        **_: Any,
    ) -> RootKeyClosureSnapshot:
        action_status = await self._action_status(db=db, run=run)
        finding_status = await self._finding_effective_status(db=db, run=run)
        unresolved_external_tasks = await self._count_unresolved_external_tasks(db=db, run=run)
        policy_snapshot = await self._policy_preservation_snapshot(db=db, run=run)
        return RootKeyClosureSnapshot(
            action_resolved=action_status == "resolved",
            finding_resolved=finding_status == "RESOLVED",
            policy_preservation_passed=policy_snapshot["passed"],
            unresolved_external_tasks=unresolved_external_tasks,
            payload={
                "poll_attempt": poll_attempt,
                "action_status": action_status,
                "finding_status": finding_status,
                "unresolved_external_tasks": unresolved_external_tasks,
                "policy_preservation": policy_snapshot,
            },
        )

    async def _action_status(self, *, db: AsyncSession, run: Any) -> str:
        result = await db.execute(
            select(Action.status).where(
                Action.tenant_id == run.tenant_id,
                Action.id == run.action_id,
            )
        )
        status_value = result.scalar_one_or_none()
        return str(status_value or "").strip().lower()

    async def _finding_effective_status(self, *, db: AsyncSession, run: Any) -> str:
        if run.finding_id is None:
            return "NEW"
        result = await db.execute(
            select(Finding.status, Finding.shadow_status_normalized).where(
                Finding.tenant_id == run.tenant_id,
                Finding.id == run.finding_id,
            )
        )
        row = result.first()
        if row is None:
            return "NEW"
        canonical = str(row[0] or "").strip().upper()
        shadow = str(row[1] or "").strip().upper()
        if shadow == "RESOLVED":
            return "RESOLVED"
        if shadow == "OPEN" and canonical == "RESOLVED":
            return "NEW"
        return canonical

    async def _count_unresolved_external_tasks(self, *, db: AsyncSession, run: Any) -> int:
        result = await db.execute(
            select(RootKeyExternalTask.id).where(
                RootKeyExternalTask.tenant_id == run.tenant_id,
                RootKeyExternalTask.run_id == run.id,
                RootKeyExternalTask.status.notin_(
                    (
                        RootKeyExternalTaskStatus.completed,
                        RootKeyExternalTaskStatus.cancelled,
                    )
                ),
            )
        )
        rows = result.scalars().all()
        return len(rows)

    async def _policy_preservation_snapshot(self, *, db: AsyncSession, run: Any) -> dict[str, Any]:
        disable_metadata = await self._latest_artifact_metadata(
            db=db,
            run=run,
            artifact_type="disable_window_evidence",
        )
        delete_metadata = await self._latest_artifact_metadata(
            db=db,
            run=run,
            artifact_type="delete_window_evidence",
        )
        disable_window_clean = bool(disable_metadata.get("window_clean") is True)
        delete_summary = delete_metadata.get("delete_summary")
        delete_summary_available = isinstance(delete_summary, dict)
        required_safe_permissions_unchanged = delete_metadata.get("required_safe_permissions_unchanged")
        if required_safe_permissions_unchanged is None:
            required_safe_permissions_unchanged = disable_metadata.get("required_safe_permissions_unchanged")
        policy_flag = required_safe_permissions_unchanged is True
        passed = disable_window_clean and delete_summary_available and policy_flag
        return {
            "passed": passed,
            "disable_window_clean": disable_window_clean,
            "delete_summary_available": delete_summary_available,
            "required_safe_permissions_unchanged": bool(policy_flag),
        }

    async def _latest_artifact_metadata(
        self,
        *,
        db: AsyncSession,
        run: Any,
        artifact_type: str,
    ) -> dict[str, Any]:
        result = await db.execute(
            select(RootKeyRemediationArtifact.metadata_json)
            .where(
                RootKeyRemediationArtifact.tenant_id == run.tenant_id,
                RootKeyRemediationArtifact.run_id == run.id,
                RootKeyRemediationArtifact.artifact_type == artifact_type,
            )
            .order_by(RootKeyRemediationArtifact.created_at.desc())
            .limit(1)
        )
        metadata = result.scalar_one_or_none()
        if isinstance(metadata, dict):
            return metadata
        return {}

    async def _record_disable_evidence(
        self,
        *,
        db: AsyncSession,
        run: Any,
        transition_id: str,
        disable_summary: dict[str, Any],
        signals: _DisableSignals,
        operator_attention_reason: str | None,
        actor_metadata: dict[str, Any] | None,
    ) -> None:
        metadata_json = {
            "disabled_summary": disable_summary,
            **self._signals_payload(signals),
            "required_safe_permissions_unchanged": bool(signals.window_clean),
            "window_started_at": self._now().isoformat(),
        }
        if operator_attention_reason is not None:
            metadata_json["window_clean"] = False
            metadata_json["operator_attention_reason"] = operator_attention_reason
        await create_root_key_remediation_artifact_idempotent(
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
            artifact_type="disable_window_evidence",
            metadata_json=metadata_json,
            idempotency_key=f"{transition_id}:disable_window_evidence",
            actor_metadata=actor_metadata,
        )

    async def _record_rollback_evidence(
        self,
        *,
        db: AsyncSession,
        run: Any,
        transition_id: str,
        rollback_reason: str,
        rollback_summary: dict[str, Any],
        actor_metadata: dict[str, Any] | None,
    ) -> None:
        await create_root_key_remediation_artifact_idempotent(
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
            artifact_type="rollback_evidence",
            metadata_json={
                "rollback_reason": rollback_reason,
                "rollback_summary": rollback_summary,
                "recorded_at": self._now().isoformat(),
            },
            idempotency_key=f"{transition_id}:rollback_evidence",
            actor_metadata=actor_metadata,
        )

    async def _record_delete_evidence(
        self,
        *,
        db: AsyncSession,
        run: Any,
        transition_id: str,
        delete_summary: dict[str, Any],
        remaining_root_keys: int,
        required_safe_permissions_unchanged: bool,
        actor_metadata: dict[str, Any] | None,
    ) -> None:
        await create_root_key_remediation_artifact_idempotent(
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
            artifact_type="delete_window_evidence",
            metadata_json={
                "delete_summary": delete_summary,
                "remaining_root_keys": int(remaining_root_keys),
                "required_safe_permissions_unchanged": bool(required_safe_permissions_unchanged),
                "recorded_at": self._now().isoformat(),
            },
            idempotency_key=f"{transition_id}:delete_window_evidence",
            actor_metadata=actor_metadata,
        )

    async def _rollback_with_alert(
        self,
        *,
        db: AsyncSession,
        run: Any,
        state_machine: RootKeyRemediationStateMachineService,
        transition_id: str,
        rollback_reason: str,
        actor_metadata: dict[str, Any] | None,
        evidence_payload: dict[str, Any],
    ) -> RootKeyTransitionResult:
        rollback_result = await state_machine.rollback(
            db,
            tenant_id=run.tenant_id,
            run_id=run.id,
            transition_id=transition_id,
            rollback_reason=rollback_reason,
            actor_metadata=actor_metadata,
            evidence_metadata={"operation": "auto_rollback", "reason": rollback_reason},
        )
        await self._record_rollback_evidence(
            db=db,
            run=rollback_result.run,
            transition_id=transition_id,
            rollback_reason=rollback_reason,
            rollback_summary=evidence_payload,
            actor_metadata=actor_metadata,
        )
        await self._create_rollback_alert_task(
            db=db,
            run=rollback_result.run,
            idempotency_key=f"{transition_id}:alert",
            rollback_reason=rollback_reason,
            actor_metadata=actor_metadata,
        )
        return rollback_result

    async def _mark_needs_attention(
        self,
        *,
        db: AsyncSession,
        run: Any,
        state_machine: RootKeyRemediationStateMachineService,
        transition_id: str,
        reason: str,
        actor_metadata: dict[str, Any] | None,
    ) -> RootKeyTransitionResult:
        return await state_machine.mark_needs_attention(
            db,
            tenant_id=run.tenant_id,
            run_id=run.id,
            transition_id=transition_id,
            actor_metadata=actor_metadata,
            evidence_metadata={"operation": "mark_needs_attention", "reason": reason},
        )

    async def _create_rollback_alert_task(
        self,
        *,
        db: AsyncSession,
        run: Any,
        idempotency_key: str,
        rollback_reason: str,
        actor_metadata: dict[str, Any] | None,
    ) -> None:
        await create_root_key_external_task_idempotent(
            db,
            run_id=run.id,
            tenant_id=run.tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            state=run.state,
            status=RootKeyExternalTaskStatus.open,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            task_type=_ROLLBACK_ALERT_TASK_TYPE,
            task_payload={
                "reason": rollback_reason,
                "raised_at": self._now().isoformat(),
            },
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )

    async def _create_final_key_manual_delete_task(
        self,
        *,
        db: AsyncSession,
        run: Any,
        idempotency_key: str,
        disable_summary: dict[str, Any],
        actor_metadata: dict[str, Any] | None,
    ) -> None:
        await create_root_key_external_task_idempotent(
            db,
            run_id=run.id,
            tenant_id=run.tenant_id,
            account_id=run.account_id,
            region=run.region,
            control_id=run.control_id,
            action_id=run.action_id,
            finding_id=run.finding_id,
            state=run.state,
            status=RootKeyExternalTaskStatus.open,
            strategy_id=run.strategy_id,
            mode=run.mode,
            correlation_id=run.correlation_id,
            task_type=FINAL_ROOT_KEY_MANUAL_DELETE_TASK_TYPE,
            task_payload={
                "preserved_access_key_id": disable_summary.get("caller_key_preserved"),
                "instructions": "Delete the preserved final root access key using an alternate authenticated path, then resume delete verification.",
                "raised_at": self._now().isoformat(),
            },
            idempotency_key=idempotency_key,
            actor_metadata=actor_metadata,
        )

    def _signals_payload(self, signals: _DisableSignals) -> dict[str, Any]:
        return {
            "window_clean": signals.window_clean,
            "root_keys_present": signals.root_keys_present,
            "managed_usage_count": signals.managed_usage_count,
            "unknown_usage_count": signals.unknown_usage_count,
            "partial_data": signals.partial_data,
            "breakage_signals": list(signals.breakage_signals),
            "retries_used": signals.retries_used,
        }

    def _disable_progression_block_reason(
        self,
        disable_summary: dict[str, Any],
    ) -> str | None:
        if disable_summary.get("caller_key_preserved"):
            return _DISABLE_PRESERVED_CALLER_KEY_CODE
        return None
