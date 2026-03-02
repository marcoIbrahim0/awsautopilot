from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.enums import (
    RootKeyArtifactStatus,
    RootKeyDependencyStatus,
    RootKeyExternalTaskStatus,
)
from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
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

_SELF_CUTOFF_GUARD_CODE = "self_cutoff_guard_not_guaranteed"
_DELETE_GATING_VALIDATION_CODE = "delete_validation_not_passed"
_DELETE_GATING_CLEAN_WINDOW_CODE = "delete_disable_window_not_clean"
_DELETE_GATING_DISABLED_CODE = "delete_window_disabled"
_DELETE_GATING_DEPENDENCY_CODE = "delete_unknown_dependencies"
_DELETE_GATING_ACTIVE_KEYS_CODE = "delete_active_keys_present"
_ROLLBACK_ALERT_TASK_TYPE = "rollback_alert"
_MASKED_EMPTY_KEY = "<EMPTY>"

_CredentialSessionFactory = Callable[[str, str | None], Any]
_UsageDiscoveryFactory = Callable[[], RootKeyUsageDiscoveryService]


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
        usage_discovery_factory: _UsageDiscoveryFactory = _default_usage_discovery_factory,
        now_fn: Callable[[], datetime] = _utc_now,
        monitor_lookback_minutes: int | None = None,
    ) -> None:
        self._mutation_session_factory = mutation_session_factory
        self._observer_session_factory = observer_session_factory or mutation_session_factory
        self._usage_discovery_factory = usage_discovery_factory
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
        )
        await self._record_disable_evidence(
            db=db,
            run=disable_result.run,
            transition_id=transition_id,
            disable_summary=disable_summary,
            signals=signals,
            actor_metadata=actor_metadata,
        )
        if signals.breakage_signals:
            reason = f"disable_breakage_signals:{','.join(signals.breakage_signals)}"
            return await self._rollback_with_alert(
                db=db,
                run=disable_result.run,
                state_machine=state_machine,
                transition_id=f"{transition_id}:rollback",
                rollback_reason=reason,
                actor_metadata=actor_metadata,
                evidence_payload={
                    "disable_summary": disable_summary,
                    "signals": self._signals_payload(signals),
                },
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
            rollback_summary = self._reactivate_inactive_root_keys(
                session_boto=sessions.mutation_session,
                region=run.region,
                key_states=self._list_root_key_states(sessions.mutation_session, run.region),
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
        delete_result = await state_machine.finalize_delete(
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
        await self._record_delete_evidence(
            db=db,
            run=delete_result.run,
            transition_id=transition_id,
            delete_summary=delete_summary,
            actor_metadata=actor_metadata,
        )
        return delete_result

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
        for item in ordered_states:
            key_id = item["access_key_id"]
            if item["status"] == "inactive":
                skipped.append(_mask_access_key_id(key_id))
                continue
            client.update_access_key(AccessKeyId=key_id, Status="Inactive")
            disabled.append(_mask_access_key_id(key_id))
        return {
            "disabled_count": len(disabled),
            "skipped_count": len(skipped),
            "disabled_keys": disabled,
            "skipped_keys": skipped,
        }

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

    async def _collect_disable_signals(
        self,
        *,
        db: AsyncSession,
        run: Any,
        observer_session: Any,
    ) -> _DisableSignals:
        breakage_signals: list[str] = []
        usage = SimpleNamespace(
            managed_count=0,
            unknown_count=0,
            partial_data=True,
            retries_used=0,
        )
        try:
            usage_service = self._usage_discovery_factory()
            usage = await usage_service.discover_and_classify(
                db=db,
                session_boto=observer_session,
                tenant_id=run.tenant_id,
                run_id=run.id,
                lookback_minutes=self._monitor_lookback_minutes,
                now=self._now(),
            )
        except Exception:
            breakage_signals.append("usage_signal_collection_failed")

        if usage.partial_data:
            breakage_signals.append("usage_signal_partial_data")
        if usage.unknown_count > 0:
            breakage_signals.append("unknown_root_usage_after_disable")

        root_keys_present: int | None = None
        try:
            account_summary = observer_session.client("iam", region_name=run.region or settings.AWS_REGION).get_account_summary()
            summary_map = account_summary.get("SummaryMap") if isinstance(account_summary, dict) else {}
            root_keys_present = _safe_int(summary_map.get("AccountAccessKeysPresent")) if isinstance(summary_map, dict) else None
        except Exception:
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
        if not isinstance(metadata, dict):
            return False
        return bool(metadata.get("window_clean") is True)

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

    async def _record_disable_evidence(
        self,
        *,
        db: AsyncSession,
        run: Any,
        transition_id: str,
        disable_summary: dict[str, Any],
        signals: _DisableSignals,
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
            artifact_type="disable_window_evidence",
            metadata_json={
                "disabled_summary": disable_summary,
                **self._signals_payload(signals),
                "window_started_at": self._now().isoformat(),
            },
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
