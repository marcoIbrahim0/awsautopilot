from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.enums import RootKeyRemediationMode, RootKeyRemediationState
from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
from backend.models.root_key_remediation_run import RootKeyRemediationRun


@dataclass(frozen=True)
class RootKeyRateMetric:
    numerator: int
    denominator: int
    rate: float | None


@dataclass(frozen=True)
class RootKeyOpsMetricsSnapshot:
    auto_success_rate: RootKeyRateMetric
    rollback_rate: RootKeyRateMetric
    needs_attention_rate: RootKeyRateMetric
    closure_pass_rate: RootKeyRateMetric
    mean_time_to_detect_unknown_dependency_seconds: float | None
    unknown_dependency_sample_size: int


async def compute_root_key_ops_metrics(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> RootKeyOpsMetricsSnapshot:
    total_runs = await _count_runs(db, tenant_id=tenant_id)
    auto_total = await _count_runs(db, tenant_id=tenant_id, mode=RootKeyRemediationMode.auto)
    auto_success = await _count_runs(
        db,
        tenant_id=tenant_id,
        mode=RootKeyRemediationMode.auto,
        state=RootKeyRemediationState.completed,
    )
    rolled_back = await _count_runs(db, tenant_id=tenant_id, state=RootKeyRemediationState.rolled_back)
    needs_attention = await _count_runs(
        db,
        tenant_id=tenant_id,
        state=RootKeyRemediationState.needs_attention,
    )
    closure_passed, closure_total = await _closure_pass_counts(db, tenant_id=tenant_id)
    mttr, mttr_count = await _unknown_dependency_detection_mttr(db, tenant_id=tenant_id)
    return RootKeyOpsMetricsSnapshot(
        auto_success_rate=_rate(auto_success, auto_total),
        rollback_rate=_rate(rolled_back, total_runs),
        needs_attention_rate=_rate(needs_attention, total_runs),
        closure_pass_rate=_rate(closure_passed, closure_total),
        mean_time_to_detect_unknown_dependency_seconds=mttr,
        unknown_dependency_sample_size=mttr_count,
    )


async def _count_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    mode: RootKeyRemediationMode | None = None,
    state: RootKeyRemediationState | None = None,
) -> int:
    stmt = select(func.count(RootKeyRemediationRun.id)).where(
        RootKeyRemediationRun.tenant_id == tenant_id
    )
    if mode is not None:
        stmt = stmt.where(RootKeyRemediationRun.mode == mode)
    if state is not None:
        stmt = stmt.where(RootKeyRemediationRun.state == state)
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def _closure_pass_counts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> tuple[int, int]:
    stmt = select(RootKeyRemediationArtifact.metadata_json).where(
        RootKeyRemediationArtifact.tenant_id == tenant_id,
        RootKeyRemediationArtifact.artifact_type == "closure_cycle_summary",
    )
    rows = (await db.execute(stmt)).scalars().all()
    passed = 0
    total = 0
    for metadata in rows:
        if not isinstance(metadata, dict):
            continue
        total += 1
        terminal_state = str(metadata.get("terminal_state") or "").strip().lower()
        if terminal_state == "completed":
            passed += 1
    return passed, total


async def _unknown_dependency_detection_mttr(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> tuple[float | None, int]:
    stmt = (
        select(
            RootKeyRemediationRun.created_at,
            func.min(RootKeyDependencyFingerprint.created_at),
        )
        .join(
            RootKeyDependencyFingerprint,
            RootKeyDependencyFingerprint.run_id == RootKeyRemediationRun.id,
        )
        .where(
            RootKeyRemediationRun.tenant_id == tenant_id,
            RootKeyDependencyFingerprint.tenant_id == tenant_id,
            RootKeyDependencyFingerprint.unknown_dependency.is_(True),
        )
        .group_by(RootKeyRemediationRun.id, RootKeyRemediationRun.created_at)
    )
    rows = (await db.execute(stmt)).all()
    deltas: list[float] = []
    for run_created_at, first_unknown_at in rows:
        if not isinstance(run_created_at, datetime) or not isinstance(first_unknown_at, datetime):
            continue
        delta = (first_unknown_at - run_created_at).total_seconds()
        if delta >= 0:
            deltas.append(delta)
    if not deltas:
        return None, 0
    return sum(deltas) / len(deltas), len(deltas)


def _rate(numerator: int, denominator: int) -> RootKeyRateMetric:
    if denominator <= 0:
        return RootKeyRateMetric(numerator=numerator, denominator=denominator, rate=None)
    return RootKeyRateMetric(
        numerator=numerator,
        denominator=denominator,
        rate=round(float(numerator) / float(denominator), 6),
    )
