"""
Security Hub ingestion job handler.
Fetches findings via assumed role, upserts into Postgres.
Optionally enqueues a compute_actions job after success (same tenant/account/region).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import AwsAccount, Finding
from backend.models.action_finding import ActionFinding
from backend.services.canonicalization import (
    build_resource_key,
    canonicalize_control_id,
    normalize_control_id_token,
)
from backend.services.finding_relationship_context import enrich_finding_raw_json
from backend.services.action_run_confirmation import reevaluate_confirmation_for_actions
from backend.services.control_scope import ACTION_TYPE_DEFAULT, action_type_from_control
from backend.utils.sqs import build_compute_actions_job_payload, parse_queue_region
from backend.workers.config import settings
from backend.workers.database import session_scope
from backend.workers.services.aws import (
    WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
    assume_role,
    build_assume_role_tags,
)
from backend.workers.services.json_safe import make_json_safe
from backend.workers.services.security_hub import fetch_all_findings

logger = logging.getLogger("worker.jobs.ingest_findings")

# Step 2B.1: source discriminator for Security Hub findings
FINDINGS_SOURCE = "security_hub"

_SG_SCOPED_ACTION_TYPES = {"sg_restrict_public_ports"}
_S3_BUCKET_SCOPED_ACTION_TYPES = {
    "s3_bucket_block_public_access",
    "s3_bucket_encryption",
    "s3_bucket_access_logging",
    "s3_bucket_lifecycle_configuration",
    "s3_bucket_encryption_kms",
    "s3_bucket_require_ssl",
}
_SECURITY_HUB_CONSISTENCY_MAX_FETCH_PASSES = 3
_SECURITY_HUB_CONSISTENCY_RETRY_SECONDS = 2.0
_SECURITY_HUB_SEMANTIC_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    # Current live Security Hub S3.11 is event notifications, not the product's lifecycle family.
    "S3.11": ("event notifications",),
    # Current live Security Hub S3.15 is Object Lock, not the product's SSE-KMS family.
    "S3.15": ("object lock",),
}


def _is_security_hub_not_enabled_error(exc: ClientError) -> bool:
    """True when Security Hub isn't enabled/subscribed in the target account/region."""
    code = exc.response.get("Error", {}).get("Code", "")
    message = str(exc.response.get("Error", {}).get("Message", "")).lower()
    if code != "InvalidAccessException":
        return False
    return (
        "not subscribed to aws security hub" in message
        or "security hub is not enabled" in message
        or "enable security hub" in message
    )


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _trunc(s: str | None, n: int) -> str | None:
    if s is None:
        return None
    return s[:n] if len(s) > n else s


def _normalized_finding_status(raw: dict) -> str:
    """
    Map Security Hub finding state to SaaS finding.status.

    Only Compliance.Status=PASSED is treated as RESOLVED. All other states
    remain open (NEW/NOTIFIED) to avoid false "resolved" matches.
    """
    compliance = raw.get("Compliance") or {}
    compliance_status = str(compliance.get("Status") or "").upper()
    if compliance_status == "PASSED":
        return "RESOLVED"

    workflow = raw.get("Workflow") or {}
    workflow_status = str(workflow.get("Status") or "").upper()
    if workflow_status == "NOTIFIED":
        return "NOTIFIED"
    return "NEW"


def _finding_state_token(raw: dict[str, Any]) -> tuple[str, str, str, str, str]:
    compliance = raw.get("Compliance") or {}
    workflow = raw.get("Workflow") or {}
    return (
        str(raw.get("Id") or ""),
        str(raw.get("UpdatedAt") or ""),
        str(compliance.get("Status") or ""),
        str(workflow.get("Status") or ""),
        str(raw.get("RecordState") or ""),
    )


def _finding_is_newer_or_changed(current: dict[str, Any], candidate: dict[str, Any]) -> bool:
    current_updated = _parse_ts(str(current.get("UpdatedAt") or ""))
    candidate_updated = _parse_ts(str(candidate.get("UpdatedAt") or ""))
    if current_updated is None:
        return candidate_updated is not None or _finding_state_token(candidate) != _finding_state_token(current)
    if candidate_updated is None:
        return False
    if candidate_updated > current_updated:
        return True
    return candidate_updated == current_updated and _finding_state_token(candidate) != _finding_state_token(current)


def _merge_finding_batches(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {
        finding_id: item for item in existing if (finding_id := str(item.get("Id") or "").strip())
    }
    for item in incoming:
        finding_id = str(item.get("Id") or "").strip()
        if not finding_id:
            continue
        current = merged.get(finding_id)
        if current is None or _finding_is_newer_or_changed(current, item):
            merged[finding_id] = item
    return list(merged.values())


def _findings_state_signature(findings: list[dict[str, Any]]) -> tuple[tuple[str, str, str, str, str], ...]:
    return tuple(sorted(_finding_state_token(item) for item in findings if isinstance(item, dict)))


def _fetch_findings_with_consistency_retry(
    session_boto: Any,
    *,
    region: str,
    account_id: str,
) -> list[dict[str, Any]]:
    findings = fetch_all_findings(session_boto, region=region, account_id=account_id)
    if not findings:
        return findings
    previous_signature = _findings_state_signature(findings)
    for _ in range(_SECURITY_HUB_CONSISTENCY_MAX_FETCH_PASSES - 1):
        time.sleep(_SECURITY_HUB_CONSISTENCY_RETRY_SECONDS)
        findings = _merge_finding_batches(
            findings,
            fetch_all_findings(session_boto, region=region, account_id=account_id),
        )
        current_signature = _findings_state_signature(findings)
        if current_signature == previous_signature:
            break
        previous_signature = current_signature
    return findings


def _resource_id_and_type(resource: dict[str, Any]) -> tuple[str | None, str | None]:
    rid = resource.get("Id")
    rtype = resource.get("Type")
    return (
        str(rid) if rid is not None else None,
        str(rtype) if rtype is not None else None,
    )


def _select_primary_resource(resources_raw: object, control_id: str | None) -> tuple[str | None, str | None]:
    """
    Pick the most useful resource for action grouping/bundling.

    Security Hub findings can include multiple resources (for example AwsAccount +
    AwsEc2SecurityGroup). For resource-scoped controls, prefer the concrete target
    resource type instead of always taking Resources[0].
    """
    if not isinstance(resources_raw, list):
        return None, None
    resources = [r for r in resources_raw if isinstance(r, dict)]
    if not resources:
        return None, None

    action_type = action_type_from_control(str(control_id) if control_id is not None else None)

    preferred_types: tuple[str, ...] = ()
    if action_type in _SG_SCOPED_ACTION_TYPES:
        preferred_types = ("AwsEc2SecurityGroup",)
    elif action_type in _S3_BUCKET_SCOPED_ACTION_TYPES:
        preferred_types = ("AwsS3Bucket",)

    for preferred_type in preferred_types:
        for resource in resources:
            if str(resource.get("Type") or "").strip() == preferred_type:
                return _resource_id_and_type(resource)

    # Fallback heuristics when Type is absent or inconsistent.
    if action_type in _SG_SCOPED_ACTION_TYPES:
        for resource in resources:
            rid = str(resource.get("Id") or "")
            if "security-group/" in rid or "sg-" in rid:
                return _resource_id_and_type(resource)
    if action_type in _S3_BUCKET_SCOPED_ACTION_TYPES:
        for resource in resources:
            rid = str(resource.get("Id") or "")
            if rid.startswith("arn:aws:s3:::"):
                return _resource_id_and_type(resource)

    return _resource_id_and_type(resources[0])


def _materializable_control_id(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    Return the control token eligible for product materialization.

    The product keeps canonical family IDs S3.11 and S3.15 for lifecycle and
    SSE-KMS guidance, but current live Security Hub uses those same IDs for
    unrelated controls (event notifications and Object Lock). We keep the raw
    control_id for transparency while excluding those live semantics from the
    lifecycle/SSE-KMS action families.
    """
    comp = raw.get("Compliance") or {}
    control_id = normalize_control_id_token(str(comp.get("SecurityControlId") or ""))
    if not control_id:
        return None, None

    title = str(raw.get("Title") or "").strip().lower()
    exclusion_markers = _SECURITY_HUB_SEMANTIC_EXCLUSIONS.get(control_id)
    if exclusion_markers and any(marker in title for marker in exclusion_markers):
        return None, f"security_hub_semantic_drift:{control_id}"
    return control_id, None


def _extract_finding_fields(raw: dict, account_id: str, region: str, tenant_id: uuid.UUID) -> dict[str, Any]:
    sid = raw.get("Id") or ""
    sev = (raw.get("Severity") or {}).get("Label")
    norm = Finding.severity_to_int(sev)
    title = (raw.get("Title") or "")[:512]
    desc = raw.get("Description")
    resources = raw.get("Resources") or []
    comp = raw.get("Compliance") or {}
    ctrl = comp.get("SecurityControlId")
    materializable_control_id, exclusion_reason = _materializable_control_id(raw)
    rid, rtype = _select_primary_resource(resources, materializable_control_id)
    standards = comp.get("AssociatedStandards") or []
    std_name = standards[0].get("StandardsId") if standards else None
    created = _parse_ts(raw.get("CreatedAt"))
    updated = _parse_ts(raw.get("UpdatedAt"))
    last_obs = _parse_ts(raw.get("LastObservedAt"))

    canonical_control_id = canonicalize_control_id(materializable_control_id)
    in_scope = (
        action_type_from_control(materializable_control_id) != ACTION_TYPE_DEFAULT
        if materializable_control_id is not None
        else False
    )
    resource_key = build_resource_key(
        account_id=account_id,
        region=region,
        resource_id=str(rid) if rid is not None else None,
        resource_type=str(rtype) if rtype is not None else None,
    )
    raw_json = enrich_finding_raw_json(
        make_json_safe(raw),
        account_id=account_id,
        region=region,
        resource_id=_trunc(rid, 2048),
        resource_type=_trunc(rtype, 256),
        resource_key=_trunc(resource_key, 512),
    )
    if exclusion_reason:
        raw_json["materialization_excluded_reason"] = exclusion_reason
    status = _normalized_finding_status(raw)[:32]
    resolved_at = (last_obs or updated or datetime.now(timezone.utc)) if status == "RESOLVED" else None

    return {
        "tenant_id": tenant_id,
        "account_id": account_id,
        "region": region,
        "finding_id": sid[:512],
        "source": FINDINGS_SOURCE,
        "severity_label": (sev or "INFORMATIONAL")[:32],
        "severity_normalized": norm,
        "title": title,
        "description": _trunc(desc, 65535),
        "resource_id": _trunc(rid, 2048),
        "resource_type": _trunc(rtype, 256),
        "control_id": _trunc(ctrl, 64),
        "canonical_control_id": _trunc(canonical_control_id, 64),
        "resource_key": _trunc(resource_key, 512),
        "standard_name": _trunc(std_name, 256),
        "status": status,
        "resolved_at": resolved_at,
        "in_scope": bool(in_scope),
        "first_observed_at": created,
        "last_observed_at": last_obs or updated,
        "sh_updated_at": updated,
        "raw_json": raw_json,
    }


def _upsert_one(
    session: Session,
    raw: dict,
    account_id: str,
    region: str,
    tenant_id: uuid.UUID,
) -> Literal["new", "updated"]:
    fid = raw.get("Id") or ""
    # Include tenant_id and source in filter (Step 2B.1: unique per source)
    existing = (
        session.query(Finding)
        .filter(
            Finding.tenant_id == tenant_id,
            Finding.finding_id == fid,
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.source == FINDINGS_SOURCE,
        )
        .first()
    )
    data = _extract_finding_fields(raw, account_id, region, tenant_id)

    if existing:
        existing.severity_label = data["severity_label"]
        existing.severity_normalized = data["severity_normalized"]
        existing.title = data["title"]
        existing.description = data["description"]
        existing.resource_id = data["resource_id"]
        existing.resource_type = data["resource_type"]
        existing.control_id = data["control_id"]
        existing.canonical_control_id = data.get("canonical_control_id")
        existing.resource_key = data.get("resource_key")
        existing.standard_name = data["standard_name"]
        existing.status = data["status"]
        existing.resolved_at = data.get("resolved_at") if data["status"] == "RESOLVED" else None
        existing.in_scope = bool(data.get("in_scope", False))
        existing.last_observed_at = data["last_observed_at"]
        existing.sh_updated_at = data["sh_updated_at"]
        existing.raw_json = data["raw_json"]
        return "updated"
    session.add(Finding(**data))
    return "new"


def execute_ingest_job(job: dict) -> None:
    """
    Process an ingest_findings job: assume_role → fetch Security Hub → upsert into Postgres.

    Args:
        job: Payload with tenant_id, account_id, region, job_type; created_at optional.
    """
    tenant_id_str = job.get("tenant_id")
    account_id = job.get("account_id")
    region = job.get("region")

    if not tenant_id_str or not account_id or not region:
        raise ValueError("job missing tenant_id, account_id, or region")

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except (TypeError, ValueError):
        raise ValueError(f"invalid tenant_id: {tenant_id_str}")

    # Single session_scope for the entire job: account lookup + upserts in one transaction
    resolved_finding_ids: set[str] = set()
    with session_scope() as session:
        # 1. Load AWS account credentials
        acc = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if not acc:
            raise ValueError(f"aws_account not found for tenant_id={tenant_id} account_id={account_id}")

        role_arn = acc.role_read_arn
        external_id = acc.external_id

        # 2. Assume role and fetch findings (outside DB transaction logic, but within session scope)
        logger.info("Assuming role for account_id=%s region=%s", account_id, region)
        session_boto = assume_role(
            role_arn=role_arn,
            external_id=external_id,
            source_identity=WORKER_ASSUME_ROLE_SOURCE_IDENTITY,
            tags=build_assume_role_tags(service_component="worker", tenant_id=tenant_id),
        )
        try:
            findings_raw = _fetch_findings_with_consistency_retry(
                session_boto,
                region=region,
                account_id=account_id,
            )
        except ClientError as e:
            if _is_security_hub_not_enabled_error(e):
                logger.warning(
                    "Skipping ingest: Security Hub is not enabled/subscribed for account_id=%s region=%s tenant_id=%s",
                    account_id,
                    region,
                    tenant_id,
                )
                return
            raise

        # 3. Upsert all findings
        n_total = len(findings_raw)
        logger.info("Upserting %d findings into database tenant_id=%s account_id=%s region=%s", n_total, tenant_id, account_id, region)
        new_count = 0
        updated_count = 0
        error_count = 0
        out_of_scope_count = 0

        for i, raw in enumerate(findings_raw):
            try:
                with session.begin_nested():
                    kind = _upsert_one(session, raw, account_id, region, tenant_id)
                if _normalized_finding_status(raw) == "RESOLVED":
                    finding_identifier = str(raw.get("Id") or "").strip()
                    if finding_identifier:
                        resolved_finding_ids.add(finding_identifier)
                # Track out-of-scope volume for visibility; filtering is now driven by Finding.in_scope.
                if settings.ONLY_IN_SCOPE_CONTROLS:
                    comp = raw.get("Compliance") or {}
                    ctrl = comp.get("SecurityControlId")
                    if action_type_from_control(str(ctrl) if ctrl is not None else None) == ACTION_TYPE_DEFAULT:
                        out_of_scope_count += 1
                if kind == "new":
                    new_count += 1
                else:
                    updated_count += 1
            except IntegrityError as e:
                error_count += 1
                logger.warning("Duplicate or constraint error for finding Id=%s: %s", raw.get("Id"), e)
            except Exception as e:
                error_count += 1
                logger.exception("Failed to upsert finding Id=%s: %s", raw.get("Id"), e)
            if (i + 1) % 50 == 0:
                logger.info(
                    "Upsert progress: %d/%d (new=%d updated=%d out_of_scope=%d errors=%d)",
                    i + 1,
                    n_total,
                    new_count,
                    updated_count,
                    out_of_scope_count,
                    error_count,
                )

    if resolved_finding_ids:
        with session_scope() as session:
            action_rows = (
                session.query(ActionFinding.action_id)
                .join(Finding, Finding.id == ActionFinding.finding_id)
                .filter(
                    Finding.tenant_id == tenant_id,
                    Finding.account_id == account_id,
                    Finding.region == region,
                    Finding.source == FINDINGS_SOURCE,
                    Finding.finding_id.in_(sorted(resolved_finding_ids)),
                )
                .all()
            )
            action_ids = [row[0] for row in action_rows if row and row[0] is not None]
            if action_ids:
                reevaluate_confirmation_for_actions(session, action_ids=action_ids)
                logger.info(
                    "Re-evaluated action confirmations from Security Hub resolved findings tenant_id=%s account_id=%s region=%s actions=%d",
                    tenant_id,
                    account_id,
                    region,
                    len(set(action_ids)),
                )

    logger.info(
        "ingest_findings complete tenant_id=%s account_id=%s region=%s processed=%d new=%d updated=%d errors=%d",
        tenant_id,
        account_id,
        region,
        len(findings_raw),
        new_count,
        updated_count,
        error_count,
    )
    if settings.ONLY_IN_SCOPE_CONTROLS and out_of_scope_count:
        logger.info(
            "ingest_findings included out-of-scope controls tenant_id=%s account_id=%s region=%s out_of_scope=%d",
            tenant_id,
            account_id,
            region,
            out_of_scope_count,
        )

    # Optional: enqueue compute_actions for same tenant/account/region so actions stay in sync
    if settings.has_ingest_queue:
        try:
            queue_url = settings.SQS_INGEST_QUEUE_URL.strip()
            queue_region = parse_queue_region(queue_url)
            sqs = boto3.client("sqs", region_name=queue_region)
            now = datetime.now(timezone.utc).isoformat()
            payload = build_compute_actions_job_payload(
                tenant_id, now, account_id=account_id, region=region
            )
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
            logger.info("Enqueued compute_actions for tenant_id=%s account_id=%s region=%s", tenant_id, account_id, region)
        except ClientError as e:
            logger.warning("Failed to enqueue compute_actions after ingest: %s", e)
        except Exception as e:
            logger.warning("Failed to enqueue compute_actions after ingest: %s", e)
