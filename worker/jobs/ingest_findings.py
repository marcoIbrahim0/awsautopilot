"""
Security Hub ingestion job handler.
Fetches findings via assumed role, upserts into Postgres.
Optionally enqueues a compute_actions job after success (same tenant/account/region).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import boto3
from botocore.exceptions import ClientError

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import AwsAccount, Finding
from backend.utils.sqs import build_compute_actions_job_payload, parse_queue_region
from worker.config import settings
from worker.database import session_scope
from worker.services.aws import assume_role
from worker.services.security_hub import fetch_all_findings

logger = logging.getLogger("worker.jobs.ingest_findings")

# Step 2B.1: source discriminator for Security Hub findings
FINDINGS_SOURCE = "security_hub"


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


def _extract_finding_fields(raw: dict, account_id: str, region: str, tenant_id: uuid.UUID) -> dict[str, Any]:
    sid = raw.get("Id") or ""
    sev = (raw.get("Severity") or {}).get("Label")
    norm = Finding.severity_to_int(sev)
    title = (raw.get("Title") or "")[:512]
    desc = raw.get("Description")
    resources = raw.get("Resources") or []
    rid = resources[0].get("Id") if resources else None
    rtype = resources[0].get("Type") if resources else None
    comp = raw.get("Compliance") or {}
    ctrl = comp.get("SecurityControlId")
    standards = comp.get("AssociatedStandards") or []
    std_name = standards[0].get("StandardsId") if standards else None
    wf = raw.get("Workflow") or {}
    status = wf.get("Status") or "NEW"
    created = _parse_ts(raw.get("CreatedAt"))
    updated = _parse_ts(raw.get("UpdatedAt"))
    last_obs = _parse_ts(raw.get("LastObservedAt"))

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
        "standard_name": _trunc(std_name, 256),
        "status": status[:32],
        "first_observed_at": created,
        "last_observed_at": last_obs or updated,
        "sh_updated_at": updated,
        "raw_json": raw,
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
        existing.standard_name = data["standard_name"]
        existing.status = data["status"]
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
        session_boto = assume_role(role_arn=role_arn, external_id=external_id)
        findings_raw = fetch_all_findings(session_boto, region=region, account_id=account_id)

        # 3. Upsert all findings
        n_total = len(findings_raw)
        logger.info("Upserting %d findings into database tenant_id=%s account_id=%s region=%s", n_total, tenant_id, account_id, region)
        new_count = 0
        updated_count = 0
        error_count = 0

        for i, raw in enumerate(findings_raw):
            try:
                with session.begin_nested():
                    kind = _upsert_one(session, raw, account_id, region, tenant_id)
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
                logger.info("Upsert progress: %d/%d (new=%d updated=%d errors=%d)", i + 1, n_total, new_count, updated_count, error_count)

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
