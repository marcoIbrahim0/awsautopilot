"""Materialized shared attack-path read model and refresh helpers."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from sqlalchemy import Select, delete, distinct, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.models.action import Action
from backend.models.action_external_link import ActionExternalLink
from backend.models.action_finding import ActionFinding
from backend.models.action_remediation_sync_state import ActionRemediationSyncState
from backend.models.attack_path_materialized_detail import AttackPathMaterializedDetail
from backend.models.attack_path_materialized_membership import AttackPathMaterializedMembership
from backend.models.attack_path_materialized_summary import AttackPathMaterializedSummary
from backend.models.enums import EntityType
from backend.models.exception import Exception
from backend.models.finding import Finding
from backend.models.remediation_run import RemediationRun
from backend.services.attack_paths import build_shared_attack_path_records
from backend.services.remediation_handoff import build_action_implementation_artifacts
from backend.utils.sqs import ATTACK_PATH_MATERIALIZATION_JOB_TYPE, QUEUE_PAYLOAD_SCHEMA_VERSION, parse_queue_region

logger = logging.getLogger("services.attack_path_materialized")

ATTACK_PATH_MATERIALIZATION_TTL = timedelta(minutes=5)


async def list_materialized_attack_paths(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None,
    action_id: str | None,
    owner_key: str | None,
    resource_id: str | None,
    status_filter: str | None,
    view: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int, bool]:
    started = time.perf_counter()
    base_query = select(AttackPathMaterializedSummary).where(AttackPathMaterializedSummary.tenant_id == tenant_id)
    base_query = _apply_materialized_filters(
        base_query,
        tenant_id=tenant_id,
        account_id=account_id,
        action_id=action_id,
        owner_key=owner_key,
        resource_id=resource_id,
        status_filter=status_filter,
        view=view,
    )
    count_result = await db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
    total = _safe_int(count_result.scalar())
    rows = await db.execute(
        base_query.order_by(
            AttackPathMaterializedSummary.rank.desc(),
            AttackPathMaterializedSummary.confidence.desc(),
            AttackPathMaterializedSummary.path_id.asc(),
        ).limit(limit).offset(offset)
    )
    items: list[dict[str, Any]] = []
    stale_seen = False
    now = datetime.now(timezone.utc)
    for summary in rows.scalars().all():
        payload = dict(summary.summary_payload or {})
        payload["computed_at"] = _iso(summary.computed_at)
        payload["stale_after"] = _iso(summary.stale_after)
        payload["is_stale"] = bool(summary.stale_after <= now)
        if payload["is_stale"]:
            stale_seen = True
        items.append(payload)
    logger.info(
        "attack_path_materialized_list tenant_id=%s total=%s returned=%s latency_ms=%s stale_seen=%s",
        tenant_id,
        total,
        len(items),
        int((time.perf_counter() - started) * 1000),
        stale_seen,
    )
    return items, total, stale_seen


async def get_materialized_attack_path(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    path_id: str,
) -> tuple[dict[str, Any] | None, bool]:
    started = time.perf_counter()
    result = await db.execute(
        select(AttackPathMaterializedSummary, AttackPathMaterializedDetail)
        .join(
            AttackPathMaterializedDetail,
            AttackPathMaterializedDetail.summary_id == AttackPathMaterializedSummary.id,
        )
        .where(
            AttackPathMaterializedSummary.tenant_id == tenant_id,
            AttackPathMaterializedSummary.path_id == path_id,
        )
    )
    row = result.first()
    if row is None or not isinstance(row, (tuple, list)) or len(row) < 2:
        logger.info(
            "attack_path_materialized_detail tenant_id=%s path_id=%s miss=true latency_ms=%s",
            tenant_id,
            path_id,
            int((time.perf_counter() - started) * 1000),
        )
        return None, False
    summary, detail = row
    payload = dict(detail.detail_payload or {})
    now = datetime.now(timezone.utc)
    payload["computed_at"] = _iso(summary.computed_at)
    payload["stale_after"] = _iso(summary.stale_after)
    payload["is_stale"] = bool(summary.stale_after <= now)
    payload["refresh_status"] = summary.refresh_status
    logger.info(
        "attack_path_materialized_detail tenant_id=%s path_id=%s latency_ms=%s stale=%s",
        tenant_id,
        path_id,
        int((time.perf_counter() - started) * 1000),
        payload["is_stale"],
    )
    return payload, bool(payload["is_stale"])


async def has_materialized_attack_paths(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(func.count()).select_from(AttackPathMaterializedSummary).where(
            AttackPathMaterializedSummary.tenant_id == tenant_id
        )
    )
    return _safe_int(result.scalar()) > 0


async def materialize_attack_paths(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    now = datetime.now(timezone.utc)
    actions = await _load_actions_for_materialization(db, tenant_id=tenant_id, account_id=account_id, region=region)
    if account_id is None and region is None:
        await _clear_materialized_scope(db, tenant_id=tenant_id)
        if not actions:
            await db.flush()
            return {
                "tenant_id": str(tenant_id),
                "account_id": account_id,
                "region": region,
                "paths_materialized": 0,
                "actions_scanned": 0,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            }
    else:
        scoped_action_ids = [action.id for action in actions]
        await _clear_materialized_scope(
            db,
            tenant_id=tenant_id,
            account_id=account_id,
            region=region,
            scoped_action_ids=scoped_action_ids,
        )

    records = await build_shared_attack_path_records(db, tenant_id=tenant_id, actions=actions)
    records = await _enrich_attack_path_records(db, tenant_id=tenant_id, records=records, now=now)
    source_max_updated_at = _max_updated_at(actions)
    summaries_created = 0
    for record in records:
        summary_payload = _summary_payload_from_record(record, computed_at=now)
        summary = AttackPathMaterializedSummary(
            tenant_id=tenant_id,
            path_id=str(record["id"]),
            representative_action_id=getattr(record.get("representative_action"), "id", None),
            account_id=getattr(record.get("representative_action"), "account_id", None),
            region=getattr(record.get("representative_action"), "region", None),
            status=str(record.get("status") or "unavailable"),
            rank=int(record.get("rank") or 0),
            confidence=float(record.get("confidence") or 0.0),
            has_blast_radius=_record_matches_blast_radius_view(record),
            is_business_critical=_record_matches_business_critical_view(record),
            is_actively_exploited=_record_matches_actively_exploited_view(record),
            has_owners=_record_matches_owned_by_team_view(record),
            summary_payload=summary_payload,
            source_max_updated_at=source_max_updated_at,
            computed_at=now,
            stale_after=now + ATTACK_PATH_MATERIALIZATION_TTL,
            refresh_status="ready",
            refresh_error=None,
        )
        db.add(summary)
        await db.flush()
        db.add(
            AttackPathMaterializedDetail(
                tenant_id=tenant_id,
                summary_id=summary.id,
                detail_payload=_detail_payload_from_record(record, computed_at=now, stale_after=summary.stale_after),
                refresh_status="ready",
                refresh_error=None,
            )
        )
        for membership_payload in _membership_payloads(record):
            db.add(
                AttackPathMaterializedMembership(
                    tenant_id=tenant_id,
                    summary_id=summary.id,
                    path_id=summary.path_id,
                    **membership_payload,
                )
            )
        summaries_created += 1
    await db.flush()
    logger.info(
        "attack_path_materialized_refresh tenant_id=%s scope=(account=%s region=%s) actions=%s paths=%s latency_ms=%s",
        tenant_id,
        account_id,
        region,
        len(actions),
        summaries_created,
        int((time.perf_counter() - started) * 1000),
    )
    return {
        "tenant_id": str(tenant_id),
        "account_id": account_id,
        "region": region,
        "paths_materialized": summaries_created,
        "actions_scanned": len(actions),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def maybe_schedule_attack_path_refresh(
    *,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
) -> bool:
    started = time.perf_counter()
    queue_url = str(getattr(settings, "SQS_INGEST_QUEUE_URL", "") or "").strip()
    if not queue_url:
        logger.info(
            "attack_path refresh skipped tenant_id=%s scope=(account=%s region=%s) reason=no_queue_url elapsed_ms=%s",
            tenant_id,
            account_id,
            region,
            int((time.perf_counter() - started) * 1000),
        )
        return False
    try:
        queue_region = parse_queue_region(queue_url)
        boto3.client("sqs", region_name=queue_region).send_message(
            QueueUrl=queue_url,
            MessageBody=_attack_path_refresh_message(tenant_id=tenant_id, account_id=account_id, region=region),
        )
        logger.info(
            "attack_path refresh enqueued tenant_id=%s scope=(account=%s region=%s) queue_region=%s elapsed_ms=%s",
            tenant_id,
            account_id,
            region,
            queue_region,
            int((time.perf_counter() - started) * 1000),
        )
        return True
    except Exception:
        logger.warning(
            "attack_path refresh enqueue failed tenant_id=%s scope=(account=%s region=%s) elapsed_ms=%s",
            tenant_id,
            account_id,
            region,
            int((time.perf_counter() - started) * 1000),
            exc_info=True,
        )
        return False


def _attack_path_refresh_message(*, tenant_id: uuid.UUID, account_id: str | None, region: str | None) -> str:
    import json

    payload: dict[str, Any] = {
        "job_type": ATTACK_PATH_MATERIALIZATION_JOB_TYPE,
        "schema_version": QUEUE_PAYLOAD_SCHEMA_VERSION,
        "tenant_id": str(tenant_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if account_id:
        payload["account_id"] = account_id
    if region:
        payload["region"] = region
    return json.dumps(payload)


async def _load_actions_for_materialization(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None,
    region: str | None,
) -> list[Action]:
    query = (
        select(Action)
        .where(Action.tenant_id == tenant_id)
        .options(
            selectinload(Action.action_finding_links)
            .selectinload(ActionFinding.finding)
            .load_only(
                Finding.id,
                Finding.finding_id,
                Finding.severity_label,
                Finding.title,
                Finding.resource_id,
                Finding.resource_type,
                Finding.resource_key,
                Finding.account_id,
                Finding.region,
                Finding.updated_at,
                Finding.raw_json,
            ),
        )
    )
    if account_id is not None:
        query = query.where(Action.account_id == account_id)
    if region is not None:
        query = query.where(Action.region == region)
    result = await db.execute(
        query.order_by(Action.priority.desc(), Action.updated_at.desc().nullslast(), Action.id.asc())
    )
    return list(result.scalars().all())


async def _clear_materialized_scope(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    account_id: str | None = None,
    region: str | None = None,
    scoped_action_ids: list[uuid.UUID] | None = None,
) -> None:
    if account_id is None and region is None:
        await db.execute(
            delete(AttackPathMaterializedMembership).where(AttackPathMaterializedMembership.tenant_id == tenant_id)
        )
        await db.execute(delete(AttackPathMaterializedDetail).where(AttackPathMaterializedDetail.tenant_id == tenant_id))
        await db.execute(
            delete(AttackPathMaterializedSummary).where(AttackPathMaterializedSummary.tenant_id == tenant_id)
        )
        return

    membership_query = select(distinct(AttackPathMaterializedMembership.summary_id)).where(
        AttackPathMaterializedMembership.tenant_id == tenant_id
    )
    if account_id is not None:
        membership_query = membership_query.where(AttackPathMaterializedMembership.account_id == account_id)
    if region is not None:
        membership_query = membership_query.where(AttackPathMaterializedMembership.region == region)
    if scoped_action_ids:
        membership_query = membership_query.where(AttackPathMaterializedMembership.action_id.in_(scoped_action_ids))
    summary_ids = [row[0] for row in (await db.execute(membership_query)).all()]
    if not summary_ids:
        return
    await db.execute(
        delete(AttackPathMaterializedMembership).where(AttackPathMaterializedMembership.summary_id.in_(summary_ids))
    )
    await db.execute(delete(AttackPathMaterializedDetail).where(AttackPathMaterializedDetail.summary_id.in_(summary_ids)))
    await db.execute(delete(AttackPathMaterializedSummary).where(AttackPathMaterializedSummary.id.in_(summary_ids)))


def _apply_materialized_filters(
    query: Select[tuple[AttackPathMaterializedSummary]],
    *,
    tenant_id: uuid.UUID,
    account_id: str | None,
    action_id: str | None,
    owner_key: str | None,
    resource_id: str | None,
    status_filter: str | None,
    view: str | None,
) -> Select[tuple[AttackPathMaterializedSummary]]:
    if status_filter is not None:
        query = query.where(AttackPathMaterializedSummary.status == status_filter)
    if view == "highest_blast_radius":
        query = query.where(AttackPathMaterializedSummary.has_blast_radius.is_(True))
    elif view == "business_critical":
        query = query.where(AttackPathMaterializedSummary.is_business_critical.is_(True))
    elif view == "actively_exploited":
        query = query.where(AttackPathMaterializedSummary.is_actively_exploited.is_(True))
    elif view == "owned_by_my_team":
        query = query.where(AttackPathMaterializedSummary.has_owners.is_(True))

    needs_membership = any(value is not None for value in (account_id, action_id, owner_key, resource_id))
    if not needs_membership:
        return query

    membership_subquery = select(distinct(AttackPathMaterializedMembership.summary_id)).where(
        AttackPathMaterializedMembership.tenant_id == tenant_id
    )
    if account_id is not None:
        membership_subquery = membership_subquery.where(AttackPathMaterializedMembership.account_id == account_id)
    if owner_key is not None:
        membership_subquery = membership_subquery.where(AttackPathMaterializedMembership.owner_key == owner_key.strip())
    if resource_id is not None:
        membership_subquery = membership_subquery.where(AttackPathMaterializedMembership.resource_id == resource_id.strip())
    if action_id is not None:
        try:
            membership_subquery = membership_subquery.where(
                AttackPathMaterializedMembership.action_id == uuid.UUID(action_id)
            )
        except ValueError as exc:
            raise ValueError("action_id must be a valid UUID") from exc
    return query.where(AttackPathMaterializedSummary.id.in_(membership_subquery))


def _record_matches_blast_radius_view(record: dict[str, Any]) -> bool:
    return any(
        item.get("name") == "blast_radius" and float(item.get("weighted_impact") or 0) > 0
        for item in record.get("rank_factors") or []
    )


def _record_matches_business_critical_view(record: dict[str, Any]) -> bool:
    tier = _text((record.get("business_impact") or {}).get("criticality_tier"))
    return tier in {"critical", "high"}


def _record_matches_actively_exploited_view(record: dict[str, Any]) -> bool:
    if any("exploit" in str(reason).lower() for reason in record.get("risk_reasons") or []):
        return True
    return any(
        item.get("name") == "exploitability" and float(item.get("weighted_impact") or 0) >= 0.1
        for item in record.get("rank_factors") or []
    )


def _record_matches_owned_by_team_view(record: dict[str, Any]) -> bool:
    return bool(record.get("owners"))


def _summary_payload_from_record(record: dict[str, Any], *, computed_at: datetime) -> dict[str, Any]:
    graph_context = record.get("representative_graph_context") or {}
    return {
        "id": record["id"],
        "status": record["status"],
        "rank": int(record["rank"]),
        "confidence": float(record["confidence"]),
        "entry_points": _entry_point_nodes(graph_context),
        "target_assets": _target_asset_nodes(graph_context),
        "summary": record.get("summary"),
        "business_impact_summary": record.get("business_impact_summary"),
        "recommended_fix_summary": (record.get("recommended_fix") or {}).get("summary"),
        "owner_labels": list(record.get("owner_labels") or []),
        "linked_action_ids": list(record.get("linked_action_ids") or []),
        "rank_factors": list(record.get("rank_factors") or []),
        "freshness": record.get("freshness"),
        "remediation_summary": record.get("remediation_summary"),
        "runtime_signals": record.get("runtime_signals"),
        "closure_targets": record.get("closure_targets"),
        "governance_summary": record.get("governance_summary"),
        "access_scope": record.get("access_scope"),
        "computed_at": _iso(computed_at),
    }


def _detail_payload_from_record(record: dict[str, Any], *, computed_at: datetime, stale_after: datetime) -> dict[str, Any]:
    graph_context = record.get("representative_graph_context") or {}
    entry_points = _entry_point_nodes(graph_context)
    target_assets = _target_asset_nodes(graph_context)
    path_nodes = _path_nodes(graph_context, entry_points=entry_points, target_assets=target_assets)
    return {
        "id": record["id"],
        "status": record["status"],
        "rank": int(record["rank"]),
        "rank_factors": list(record.get("rank_factors") or []),
        "confidence": float(record.get("confidence") or 0.0),
        "freshness": record.get("freshness"),
        "path_nodes": path_nodes,
        "path_edges": _path_edges(path_nodes),
        "entry_points": entry_points,
        "target_assets": target_assets,
        "summary": record.get("summary"),
        "business_impact": record.get("business_impact"),
        "risk_reasons": list(record.get("risk_reasons") or []),
        "owners": list(record.get("owners") or []),
        "recommended_fix": record.get("recommended_fix"),
        "linked_actions": list(record.get("linked_actions") or []),
        "evidence": list(record.get("evidence") or []),
        "provenance": list(record.get("provenance") or []),
        "remediation_summary": record.get("remediation_summary"),
        "truncated": bool(record.get("truncated")),
        "availability_reason": record.get("availability_reason"),
        "runtime_signals": record.get("runtime_signals"),
        "exposure_validation": record.get("exposure_validation"),
        "code_context": record.get("code_context"),
        "linked_repositories": list(record.get("linked_repositories") or []),
        "implementation_artifacts": list(record.get("implementation_artifacts") or []),
        "closure_targets": record.get("closure_targets"),
        "external_workflow_summary": record.get("external_workflow_summary"),
        "exception_summary": record.get("exception_summary"),
        "evidence_exports": record.get("evidence_exports"),
        "access_scope": record.get("access_scope"),
        "computed_at": _iso(computed_at),
        "stale_after": _iso(stale_after),
    }


def _membership_payloads(record: dict[str, Any]) -> list[dict[str, Any]]:
    linked_action_rows = list(record.get("linked_actions") or [])
    representative_action = record.get("representative_action")
    representative_account_id = getattr(representative_action, "account_id", None)
    representative_region = getattr(representative_action, "region", None)
    representative_resource_id = getattr(representative_action, "resource_id", None)
    items: list[dict[str, Any]] = []
    for row in linked_action_rows:
        try:
            action_uuid = uuid.UUID(str(row.get("id")))
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "action_id": action_uuid,
                "account_id": representative_account_id,
                "region": representative_region,
                "resource_id": representative_resource_id,
                "owner_key": _text((row.get("owner_key") if isinstance(row, dict) else None))
                or _text(getattr(representative_action, "owner_key", None)),
                "owner_label": _text(row.get("owner_label")) or _text(getattr(representative_action, "owner_label", None)),
                "action_status": _text(row.get("status")),
            }
        )
    return items


def _entry_point_nodes(graph_context: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, item in enumerate(graph_context.get("entry_points") or []):
        label = _text(item.get("label")) or _text(item.get("value")) or "Entry point"
        items.append(
            {
                "node_id": f"entry-{index + 1}",
                "kind": "entry_point",
                "label": label,
                "detail": _text(item.get("source")),
                "facts": [],
            }
        )
    return items


def _target_asset_nodes(graph_context: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, item in enumerate(graph_context.get("connected_assets") or []):
        label = _text(item.get("label")) or _text(item.get("resource_id")) or "Target asset"
        items.append(
            {
                "node_id": f"target-{index + 1}",
                "kind": "target_asset",
                "label": label,
                "detail": _text(item.get("relationship")) or _text(item.get("resource_type")),
                "facts": [],
            }
        )
    return items


def _path_nodes(
    graph_context: dict[str, Any],
    *,
    entry_points: list[dict[str, Any]],
    target_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if entry_points:
        items.append(entry_points[0])
    for index, item in enumerate(graph_context.get("identity_path") or []):
        label = _text(item.get("label")) or _text(item.get("value"))
        if not label:
            continue
        items.append(
            {
                "node_id": f"identity-{index + 1}",
                "kind": "identity",
                "label": label,
                "detail": _text(item.get("source")),
                "facts": [],
            }
        )
    if target_assets:
        items.append(target_assets[0])
    return items


def _path_edges(path_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for left, right in zip(path_nodes, path_nodes[1:]):
        edges.append(
            {
                "source_node_id": left["node_id"],
                "target_node_id": right["node_id"],
                "label": "can reach",
            }
        )
    return edges


def _max_updated_at(actions: list[Action]) -> object | None:
    values = [getattr(action, "updated_at", None) for action in actions if getattr(action, "updated_at", None) is not None]
    if not values:
        return None
    return max(values)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _iso(value: object | None) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


async def _load_attack_path_exceptions(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_ids: list[uuid.UUID],
    now: datetime,
) -> dict[uuid.UUID, list[Exception]]:
    if not action_ids:
        return {}
    result = await db.execute(
        select(Exception).where(
            Exception.tenant_id == tenant_id,
            Exception.entity_type == EntityType.action,
            Exception.entity_id.in_(action_ids),
            Exception.expires_at > now,
        )
    )
    grouped: defaultdict[uuid.UUID, list[Exception]] = defaultdict(list)
    for row in result.scalars().all():
        grouped[row.entity_id].append(row)
    return dict(grouped)


async def _load_attack_path_runs(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[RemediationRun]]:
    if not action_ids:
        return {}
    result = await db.execute(
        select(RemediationRun)
        .where(RemediationRun.tenant_id == tenant_id, RemediationRun.action_id.in_(action_ids))
        .order_by(RemediationRun.created_at.desc())
    )
    grouped: defaultdict[uuid.UUID, list[RemediationRun]] = defaultdict(list)
    for run in result.scalars().all():
        grouped[run.action_id].append(run)
    return dict(grouped)


async def _load_attack_path_sync_state(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action_ids: list[uuid.UUID],
) -> tuple[dict[uuid.UUID, list[ActionRemediationSyncState]], dict[uuid.UUID, list[ActionExternalLink]]]:
    if not action_ids:
        return {}, {}
    sync_result = await db.execute(
        select(ActionRemediationSyncState).where(
            ActionRemediationSyncState.tenant_id == tenant_id,
            ActionRemediationSyncState.action_id.in_(action_ids),
        )
    )
    link_result = await db.execute(
        select(ActionExternalLink).where(
            ActionExternalLink.tenant_id == tenant_id,
            ActionExternalLink.action_id.in_(action_ids),
        )
    )
    states: defaultdict[uuid.UUID, list[ActionRemediationSyncState]] = defaultdict(list)
    for row in sync_result.scalars().all():
        states[row.action_id].append(row)
    links: defaultdict[uuid.UUID, list[ActionExternalLink]] = defaultdict(list)
    for row in link_result.scalars().all():
        links[row.action_id].append(row)
    return dict(states), dict(links)


def _artifact_links_for_runs(runs: list[RemediationRun], *, action_status: str) -> list[Any]:
    try:
        return build_action_implementation_artifacts(runs[:8], action_status=action_status)
    except Exception:
        logger.warning("Attack-path artifact projection failed; dropping additive remediation artifacts.", exc_info=True)
        return []


def _repositories_from_artifacts(artifacts: list[Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str | None, str | None, str | None]] = set()
    items: list[dict[str, Any]] = []
    for artifact in artifacts:
        metadata = artifact.metadata if isinstance(artifact.metadata, dict) else {}
        repository = metadata.get("repository")
        provider = metadata.get("provider") or "generic_git"
        if not isinstance(repository, str) or not repository.strip():
            continue
        item = (
            str(provider),
            repository.strip(),
            _text(metadata.get("base_branch")),
            _text(metadata.get("root_path")),
            artifact.run_id,
        )
        if item in seen:
            continue
        seen.add(item)
        items.append(
            {
                "provider": item[0],
                "repository": item[1],
                "base_branch": item[2],
                "root_path": item[3],
                "source_run_id": item[4],
            }
        )
    return items


def _attack_path_action_ids(records: list[dict[str, Any]]) -> list[uuid.UUID]:
    action_ids: list[uuid.UUID] = []
    for record in records:
        for raw_id in record.get("linked_action_ids") or []:
            try:
                action_ids.append(uuid.UUID(str(raw_id)))
            except (TypeError, ValueError):
                continue
    return sorted(set(action_ids), key=str)


async def _enrich_attack_path_records(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    records: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    action_ids = _attack_path_action_ids(records)
    try:
        exceptions_by_action = await _load_attack_path_exceptions(db, tenant_id=tenant_id, action_ids=action_ids, now=now)
    except SQLAlchemyError:
        logger.warning("Attack-path exception enrichment failed; continuing without exception summaries.", exc_info=True)
        exceptions_by_action = {}
    try:
        runs_by_action = await _load_attack_path_runs(db, tenant_id=tenant_id, action_ids=action_ids)
    except SQLAlchemyError:
        logger.warning("Attack-path remediation-run enrichment failed; continuing without remediation artifacts.", exc_info=True)
        runs_by_action = {}
    try:
        sync_states_by_action, links_by_action = await _load_attack_path_sync_state(
            db,
            tenant_id=tenant_id,
            action_ids=action_ids,
        )
    except SQLAlchemyError:
        logger.warning("Attack-path external workflow enrichment failed; continuing without sync projections.", exc_info=True)
        sync_states_by_action, links_by_action = {}, {}
    enriched: list[dict[str, Any]] = []
    for record in records:
        linked_action_rows = record.get("linked_actions") or []
        linked_action_ids: list[uuid.UUID] = []
        for row in linked_action_rows:
            try:
                linked_action_ids.append(uuid.UUID(str(row.get("id"))))
            except (TypeError, ValueError):
                continue
        representative_action = record["representative_action"]
        path_runs = [run for action_id in linked_action_ids for run in runs_by_action.get(action_id, [])]
        artifacts = _artifact_links_for_runs(path_runs, action_status=representative_action.status)
        repositories = _repositories_from_artifacts(artifacts)
        enriched_record = dict(record)
        enriched_record["runtime_signals"] = _runtime_signals_payload(record)
        enriched_record["exposure_validation"] = _exposure_validation_payload(record)
        enriched_record["linked_repositories"] = repositories
        enriched_record["implementation_artifacts"] = [
            artifact.model_dump() if hasattr(artifact, "model_dump") else dict(artifact)
            for artifact in artifacts
        ]
        enriched_record["code_context"] = _code_context_payload(representative_action, repositories=repositories, artifacts=artifacts)
        enriched_record["closure_targets"] = _closure_targets_payload(record)
        workflow = _external_workflow_summary_payload(
            action_ids=linked_action_ids,
            sync_states_by_action=sync_states_by_action,
            links_by_action=links_by_action,
        )
        enriched_record["external_workflow_summary"] = workflow
        enriched_record["governance_summary"] = workflow
        enriched_record["exception_summary"] = _exception_summary_payload(
            action_ids=linked_action_ids,
            exceptions_by_action=exceptions_by_action,
            now=now,
        )
        enriched_record["evidence_exports"] = _evidence_exports_payload(record, artifacts=artifacts, runs=path_runs)
        enriched_record["access_scope"] = _access_scope_payload()
        enriched.append(enriched_record)
    return enriched


def _runtime_signals_payload(record: dict[str, Any]) -> dict[str, Any]:
    graph_context = record.get("representative_graph_context") or {}
    entry_points = graph_context.get("entry_points") or []
    connected_assets = graph_context.get("connected_assets") or []
    identity_path = graph_context.get("identity_path") or []
    status = _text(record.get("status")) or "unavailable"
    confidence = float(record.get("confidence") or 0.0)
    publicly_reachable = bool(entry_points)
    sensitive_targets = sum(
        1
        for asset in connected_assets
        if "sensitive" in str(asset.get("label", "")).lower() or "data" in str(asset.get("relationship", "")).lower()
    )
    workload_presence = "present" if connected_assets else "unknown"
    summary = (
        f"{len(entry_points)} entry point(s), {len(identity_path)} identity hop(s), and {len(connected_assets)} connected asset(s) inform this path."
        if status in {"available", "partial"}
        else "Runtime truth is not fully verified for this path yet."
    )
    return {
        "workload_presence": workload_presence,
        "publicly_reachable": publicly_reachable,
        "sensitive_target_count": sensitive_targets,
        "identity_hops": len(identity_path),
        "confidence": confidence,
        "summary": summary,
    }


def _exposure_validation_payload(record: dict[str, Any]) -> dict[str, Any]:
    status = _text(record.get("status")) or "unavailable"
    freshness = record.get("freshness") or {}
    if status == "available":
        validation = "verified"
        summary = "Persisted graph evidence resolves a bounded entry point and target path."
    elif status == "partial":
        validation = "partial"
        summary = "The path is supported by graph evidence, but some runtime or graph detail is truncated."
    else:
        validation = "unverified"
        summary = "The path remains bounded and fail-closed because runtime or graph evidence is incomplete."
    return {
        "status": validation,
        "summary": summary,
        "observed_at": freshness.get("observed_at"),
    }


def _closure_targets_payload(record: dict[str, Any]) -> dict[str, Any]:
    linked_actions = record.get("linked_actions") or []
    open_ids = [item["id"] for item in linked_actions if item.get("status") == "open"]
    in_progress_ids = [item["id"] for item in linked_actions if item.get("status") == "in_progress"]
    resolved_ids = [item["id"] for item in linked_actions if item.get("status") == "resolved"]
    if in_progress_ids:
        summary = f"{len(in_progress_ids)} linked action(s) are in progress; closing the remaining open items will reduce this path."
    elif open_ids:
        summary = f"{len(open_ids)} open linked action(s) remain before this path can materially drop."
    else:
        summary = "All currently linked actions are resolved; monitor for drift or reopen."
    return {
        "open_action_ids": open_ids,
        "in_progress_action_ids": in_progress_ids,
        "resolved_action_ids": resolved_ids,
        "summary": summary,
    }


def _external_workflow_summary_payload(
    *,
    action_ids: list[uuid.UUID],
    sync_states_by_action: dict[uuid.UUID, list[ActionRemediationSyncState]],
    links_by_action: dict[uuid.UUID, list[ActionExternalLink]],
) -> dict[str, Any]:
    drifted_count = 0
    in_sync_count = 0
    linked_items: list[str] = []
    providers: set[str] = set()
    for action_id in action_ids:
        for state in sync_states_by_action.get(action_id, []):
            providers.add(state.provider)
            if state.sync_status == "drifted":
                drifted_count += 1
            else:
                in_sync_count += 1
        for link in links_by_action.get(action_id, []):
            providers.add(link.provider)
            ref = link.external_key or link.external_id or link.provider
            linked_items.append(f"{link.provider}:{ref}")
    if not providers:
        summary = "No external workflow links are attached to this path."
    elif drifted_count:
        summary = f"{drifted_count} linked external workflow item(s) are drifted across {len(providers)} provider(s)."
    else:
        summary = f"External workflow links are present across {len(providers)} provider(s) and currently aligned."
    return {
        "provider_count": len(providers),
        "drifted_count": drifted_count,
        "in_sync_count": in_sync_count,
        "linked_items": sorted(linked_items),
        "summary": summary,
    }


def _exception_summary_payload(
    *,
    action_ids: list[uuid.UUID],
    exceptions_by_action: dict[uuid.UUID, list[Exception]],
    now: datetime,
) -> dict[str, Any]:
    active_count = 0
    expiring_count = 0
    for action_id in action_ids:
        for row in exceptions_by_action.get(action_id, []):
            active_count += 1
            if row.expires_at <= now + timedelta(days=settings.ACTIONS_OWNER_QUEUE_EXPIRING_EXCEPTION_DAYS):
                expiring_count += 1
    if not active_count:
        summary = "No active action exceptions are attached to this path."
    elif expiring_count:
        summary = f"{expiring_count} active exception(s) are nearing expiry across linked actions."
    else:
        summary = f"{active_count} active exception(s) currently govern linked actions on this path."
    return {
        "active_count": active_count,
        "expiring_count": expiring_count,
        "summary": summary,
    }


def _evidence_exports_payload(record: dict[str, Any], *, artifacts: list[Any], runs: list[RemediationRun]) -> dict[str, Any]:
    evidence_count = len(record.get("evidence") or [])
    artifact_count = len(artifacts)
    export_ready = bool(evidence_count or artifact_count or runs)
    if export_ready:
        summary = f"{evidence_count} evidence item(s) and {artifact_count} implementation artifact(s) are available for closure review."
    else:
        summary = "No exportable implementation or evidence artifacts are attached yet."
    return {
        "evidence_item_count": evidence_count,
        "implementation_artifact_count": artifact_count,
        "export_ready": export_ready,
        "summary": summary,
    }


def _access_scope_payload() -> dict[str, Any]:
    return {
        "scope": "tenant_scoped",
        "evidence_visibility": "full",
        "restricted_sections": [],
        "export_allowed": True,
    }


def _code_context_payload(representative_action: Action, *, repositories: list[dict[str, Any]], artifacts: list[Any]) -> dict[str, Any]:
    owner_label = representative_action.owner_label or "Unassigned"
    repository_count = len(repositories)
    artifact_count = len(artifacts)
    if repositories:
        repo_summary = f"{repository_count} linked repo target(s) and {artifact_count} implementation artifact(s) are available."
    else:
        repo_summary = f"{artifact_count} implementation artifact(s) are available, but no repo-aware target is attached yet."
    return {
        "owner_label": owner_label,
        "service_owner_key": representative_action.owner_key,
        "repository_count": repository_count,
        "implementation_artifact_count": artifact_count,
        "summary": repo_summary,
    }
