"""
Amazon Inspector v2 ingestion job handler (Step 2B.2).

Fetches Inspector vulnerability findings (CVE, package, code) via assumed role,
normalizes to our finding shape, and upserts into Postgres with source='inspector'.
Optionally enqueues compute_actions for the same tenant/account/region.
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
from backend.workers.config import settings
from backend.workers.database import session_scope
from backend.workers.services.aws import assume_role
from backend.workers.services.inspector import (
    fetch_all_inspector_findings,
    normalize_inspector_finding,
)

logger = logging.getLogger("worker.jobs.ingest_inspector")

SOURCE = "inspector"


def _upsert_one(
    session: Session,
    data: dict[str, Any],
) -> Literal["new", "updated"]:
    """Upsert one Inspector finding by (finding_id, account_id, region, source)."""
    fid = data["finding_id"]
    account_id = data["account_id"]
    region = data["region"]
    tenant_id = data["tenant_id"]

    existing = (
        session.query(Finding)
        .filter(
            Finding.tenant_id == tenant_id,
            Finding.finding_id == fid,
            Finding.account_id == account_id,
            Finding.region == region,
            Finding.source == SOURCE,
        )
        .first()
    )
    if existing:
        existing.severity_label = data["severity_label"]
        existing.severity_normalized = data["severity_normalized"]
        existing.title = data["title"]
        existing.description = data["description"]
        existing.resource_id = data["resource_id"]
        existing.resource_type = data["resource_type"]
        existing.canonical_control_id = data.get("canonical_control_id")
        existing.resource_key = data.get("resource_key")
        existing.status = data["status"]
        existing.in_scope = bool(data.get("in_scope", False))
        existing.last_observed_at = data["last_observed_at"]
        existing.sh_updated_at = data["sh_updated_at"]
        existing.raw_json = data["raw_json"]
        return "updated"
    session.add(Finding(**data))
    return "new"


def execute_ingest_inspector_job(job: dict) -> None:
    """
    Process an ingest_inspector job: assume_role → fetch Inspector v2 → upsert.

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

    if settings.ONLY_IN_SCOPE_CONTROLS:
        logger.info(
            "Skipping Inspector ingest (ONLY_IN_SCOPE_CONTROLS=true) tenant_id=%s account_id=%s region=%s",
            tenant_id,
            account_id,
            region,
        )
        return

    with session_scope() as session:
        acc = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if not acc:
            raise ValueError(
                f"aws_account not found for tenant_id={tenant_id} account_id={account_id}"
            )

        role_arn = acc.role_read_arn
        external_id = acc.external_id

        logger.info(
            "Assuming role for Inspector account_id=%s region=%s",
            account_id,
            region,
        )
        session_boto = assume_role(role_arn=role_arn, external_id=external_id)
        findings_raw = fetch_all_inspector_findings(
            session_boto, region=region, account_id=account_id
        )

        n_total = len(findings_raw)
        logger.info(
            "Upserting %d Inspector findings tenant_id=%s account_id=%s region=%s",
            n_total,
            tenant_id,
            account_id,
            region,
        )
        new_count = 0
        updated_count = 0
        error_count = 0

        for i, raw in enumerate(findings_raw):
            try:
                data = normalize_inspector_finding(raw, account_id, region, tenant_id)
                with session.begin_nested():
                    kind = _upsert_one(session, data)
                if kind == "new":
                    new_count += 1
                else:
                    updated_count += 1
            except IntegrityError as e:
                error_count += 1
                logger.warning(
                    "Duplicate or constraint error for Inspector finding arn=%s: %s",
                    raw.get("findingArn"),
                    e,
                )
            except Exception as e:
                error_count += 1
                logger.exception(
                    "Failed to upsert Inspector finding arn=%s: %s",
                    raw.get("findingArn"),
                    e,
                )
            if (i + 1) % 50 == 0:
                logger.info(
                    "Inspector upsert progress: %d/%d (new=%d updated=%d errors=%d)",
                    i + 1,
                    n_total,
                    new_count,
                    updated_count,
                    error_count,
                )

    logger.info(
        "ingest_inspector complete tenant_id=%s account_id=%s region=%s "
        "processed=%d new=%d updated=%d errors=%d",
        tenant_id,
        account_id,
        region,
        n_total,
        new_count,
        updated_count,
        error_count,
    )

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
            logger.info(
                "Enqueued compute_actions after Inspector ingest tenant_id=%s account_id=%s region=%s",
                tenant_id,
                account_id,
                region,
            )
        except ClientError as e:
            logger.warning("Failed to enqueue compute_actions after Inspector ingest: %s", e)
        except Exception as e:
            logger.warning("Failed to enqueue compute_actions after Inspector ingest: %s", e)
