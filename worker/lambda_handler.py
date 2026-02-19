"""
AWS Lambda entrypoint for SQS-triggered worker execution.

This processes SQS event records (queue -> Lambda) and routes jobs by job_type.
It supports partial batch failures so one bad job doesn't poison the whole batch.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import boto3

from backend.services.migration_guard import assert_database_revision_at_head
from backend.utils.sqs import parse_queue_region
from worker.config import settings
from worker.jobs import get_job_handler
from worker.main import (
    CONTRACT_VIOLATION_INVALID_JSON,
    CONTRACT_VIOLATION_MISSING_FIELDS,
    CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE,
    CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION,
    LEGACY_QUEUE_PAYLOAD_SCHEMA_VERSION,
    REMEDIATION_RUN_JOB_TYPE,
    _build_quarantine_envelope,
    _get_contract_quarantine_queue_url,
    _get_error_code,
    _is_assume_role_failure,
    _is_permission_error,
    _is_schema_version_supported,
    _is_transient_error,
    _maybe_quarantine_account,
    _resolve_schema_version,
    _supported_schema_versions,
    _validate_job,
)

logger = logging.getLogger("worker.lambda")

# Fail fast on cold start if migrations are not applied.
assert_database_revision_at_head(component="worker")

_SQS_CLIENTS: dict[str, Any] = {}


def _sqs_client(region: str) -> Any:
    region = (region or settings.AWS_REGION or "eu-north-1").strip()
    client = _SQS_CLIENTS.get(region)
    if client is None:
        client = boto3.client("sqs", region_name=region)
        _SQS_CLIENTS[region] = client
    return client


def _parse_queue_from_arn(queue_arn: str) -> tuple[str, str, str]:
    """
    Parse arn:aws:sqs:<region>:<account_id>:<queue_name>
    Returns (region, account_id, queue_name) (empty strings on failure).
    """
    parts = (queue_arn or "").split(":", 5)
    if len(parts) != 6:
        return "", "", ""
    if parts[0] != "arn" or parts[2] != "sqs":
        return "", "", ""
    region = parts[3]
    account_id = parts[4]
    queue_name = parts[5]
    return region, account_id, queue_name


def _queue_url_from_arn(queue_arn: str, fallback_region: str) -> tuple[str, str, str]:
    region, account_id, queue_name = _parse_queue_from_arn(queue_arn)
    if not region:
        region = (fallback_region or settings.AWS_REGION or "eu-north-1").strip()
    if not account_id or not queue_name:
        return "", region, ""
    return f"https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}", region, queue_name


def _maybe_extend_visibility(
    *,
    sqs: Any,
    queue_url: str,
    receipt_handle: str,
    stop_heartbeat: threading.Event,
) -> threading.Thread | None:
    """
    Best-effort visibility extension. Lambda's SQS integration should set a sane
    visibility timeout, but we defensively extend for long-running jobs.
    """
    if not queue_url or not receipt_handle:
        return None

    def _heartbeat() -> None:
        # Set visibility immediately, then refresh periodically.
        try:
            sqs.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=300,
            )
        except Exception:
            logger.debug("Visibility set failed (non-fatal).", exc_info=True)

        interval_seconds = 120
        while not stop_heartbeat.wait(interval_seconds):
            try:
                sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=300,
                )
            except Exception:
                logger.debug("Visibility heartbeat failed (non-fatal).", exc_info=True)

    t = threading.Thread(
        target=_heartbeat,
        name="sqs-visibility-heartbeat",
        daemon=True,
    )
    t.start()
    return t


def _send_contract_violation_to_quarantine(
    *,
    message_id: str,
    source_queue_url: str,
    source_queue_name: str,
    receive_count: int,
    body_raw: str,
    reason_code: str,
    reason_detail: str | None = None,
    job: dict | None = None,
) -> bool:
    quarantine_queue_url = _get_contract_quarantine_queue_url()
    if not quarantine_queue_url:
        logger.warning(
            "[%s] Contract violation (%s) queue=%s but SQS_CONTRACT_QUARANTINE_QUEUE_URL is unset. "
            "Leaving message for retry/DLQ.",
            message_id,
            reason_code,
            source_queue_name,
        )
        return False

    envelope = _build_quarantine_envelope(
        message_id=message_id,
        source_queue_name=source_queue_name,
        source_queue_url=source_queue_url,
        receive_count=receive_count,
        body_raw=body_raw,
        reason_code=reason_code,
        reason_detail=reason_detail,
        job=job,
    )

    quarantine_region = parse_queue_region(quarantine_queue_url)
    quarantine_sqs = _sqs_client(quarantine_region)
    try:
        quarantine_sqs.send_message(
            QueueUrl=quarantine_queue_url,
            MessageBody=json.dumps(envelope, separators=(",", ":"), ensure_ascii=True),
        )
    except Exception:
        logger.exception(
            "[%s] Failed to quarantine contract-violation payload queue=%s reason=%s. "
            "Leaving source message for retry/DLQ.",
            message_id,
            source_queue_name,
            reason_code,
        )
        return False

    logger.warning(
        "[%s] Contract violation (%s) quarantined queue=%s quarantine_queue=%s",
        message_id,
        reason_code,
        source_queue_name,
        quarantine_queue_url,
    )
    return True


def _approx_receive_count_from_record(record: dict) -> int:
    attrs = record.get("attributes") or {}
    raw = attrs.get("ApproximateReceiveCount")
    try:
        return max(1, int(raw))
    except Exception:
        return 1


def _process_record(record: dict) -> bool:
    """
    Return True when the record should be ACKed (deleted by Lambda),
    False when it should be retried.
    """
    message_id = record.get("messageId") or "unknown"
    receipt_handle = record.get("receiptHandle") or ""
    body_raw = record.get("body") or ""
    queue_arn = record.get("eventSourceARN") or ""
    record_region = record.get("awsRegion") or ""

    source_queue_url, region, queue_name = _queue_url_from_arn(queue_arn, record_region)
    if not queue_name:
        queue_name = "unknown"

    receive_count = _approx_receive_count_from_record(record)

    # --- Parse JSON ---
    try:
        job: dict = json.loads(body_raw)
    except json.JSONDecodeError as exc:
        quarantined = _send_contract_violation_to_quarantine(
            message_id=message_id,
            source_queue_url=source_queue_url,
            source_queue_name=queue_name,
            receive_count=receive_count,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_INVALID_JSON,
            reason_detail=f"json_error={str(exc)[:200]}",
        )
        # If we successfully quarantined, ACK the original message.
        return quarantined

    # --- Validate fields ---
    missing = _validate_job(job)
    if missing:
        missing_list = ",".join(sorted(missing))
        quarantined = _send_contract_violation_to_quarantine(
            message_id=message_id,
            source_queue_url=source_queue_url,
            source_queue_name=queue_name,
            receive_count=receive_count,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_MISSING_FIELDS,
            reason_detail=f"missing_required_fields={missing_list}",
            job=job,
        )
        return quarantined

    # Normalize job_type for routing (remediation_run detected by shape if job_type unclear)
    job_type = (job.get("job_type") or "").strip() if isinstance(job.get("job_type"), str) else job.get("job_type")
    if not job_type and job.get("run_id") and job.get("action_id") and job.get("mode"):
        job_type = REMEDIATION_RUN_JOB_TYPE

    tenant_id = job.get("tenant_id")
    account_id = job.get("account_id")
    job_region = job.get("region")

    if receive_count > 1:
        logger.warning(
            "[%s] Retried message queue=%s receive_count=%s job_type=%s schema_version=%s tenant=%s account=%s region=%s",
            message_id,
            queue_name,
            receive_count,
            job_type,
            job.get("schema_version", LEGACY_QUEUE_PAYLOAD_SCHEMA_VERSION),
            tenant_id,
            account_id,
            job_region,
        )

    # --- Get handler ---
    handler_fn = get_job_handler(str(job_type or "").strip())
    if handler_fn is None:
        quarantined = _send_contract_violation_to_quarantine(
            message_id=message_id,
            source_queue_url=source_queue_url,
            source_queue_name=queue_name,
            receive_count=receive_count,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE,
            reason_detail=f"job_type={job_type}",
            job=job,
        )
        return quarantined

    schema_version = _resolve_schema_version(job)
    if schema_version is None:
        quarantined = _send_contract_violation_to_quarantine(
            message_id=message_id,
            source_queue_url=source_queue_url,
            source_queue_name=queue_name,
            receive_count=receive_count,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION,
            reason_detail=f"invalid_schema_version={job.get('schema_version')!r}",
            job=job,
        )
        return quarantined

    if not _is_schema_version_supported(str(job_type or ""), schema_version):
        supported = ",".join(str(v) for v in sorted(_supported_schema_versions(str(job_type or ""))))
        quarantined = _send_contract_violation_to_quarantine(
            message_id=message_id,
            source_queue_url=source_queue_url,
            source_queue_name=queue_name,
            receive_count=receive_count,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION,
            reason_detail=(
                f"job_type={job_type} schema_version={schema_version} "
                f"supported_versions={supported or 'none'}"
            ),
            job=job,
        )
        return quarantined

    job["schema_version"] = schema_version

    stop_heartbeat = threading.Event()
    heartbeat_thread: threading.Thread | None = None
    if source_queue_url:
        sqs = _sqs_client(region)
        heartbeat_thread = _maybe_extend_visibility(
            sqs=sqs,
            queue_url=source_queue_url,
            receipt_handle=receipt_handle,
            stop_heartbeat=stop_heartbeat,
        )

    try:
        logger.info(
            "[%s] Processing queue=%s receive_count=%s job_type=%s schema_version=%s tenant=%s account=%s region=%s",
            message_id,
            queue_name,
            receive_count,
            job_type,
            schema_version,
            tenant_id,
            account_id,
            job_region,
        )
        handler_fn(job)
        logger.info("[%s] Job completed.", message_id)
        return True
    except Exception as exc:
        error_code = _get_error_code(exc)

        if _is_permission_error(exc):
            logger.error(
                "[%s] Permission error (%s) account=%s job_type=%s. Message will retry/DLQ. Error=%s",
                message_id,
                error_code,
                account_id,
                job_type,
                exc,
            )
            if _is_assume_role_failure(exc):
                _maybe_quarantine_account(job, receive_count=receive_count, error_code=error_code)
        elif _is_transient_error(exc):
            logger.warning(
                "[%s] Transient error (%s) job_type=%s. Message will retry. Error=%s",
                message_id,
                error_code,
                job_type,
                exc,
            )
        else:
            logger.exception(
                "[%s] Handler failed (%s) job_type=%s. Message will retry/DLQ.",
                message_id,
                error_code,
                job_type,
            )
        return False
    finally:
        stop_heartbeat.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=1.0)


def handler(event: dict, context: Any) -> dict:
    """
    Lambda handler for SQS partial-batch response.

    Returns: {"batchItemFailures": [{"itemIdentifier": "<messageId>"}]}
    """
    del context
    records = event.get("Records") or []
    failures: list[dict[str, str]] = []

    for record in records:
        ok = False
        try:
            ok = _process_record(record)
        except Exception:
            logger.exception("Unexpected worker failure processing record.")
            ok = False

        if not ok:
            message_id = record.get("messageId") or "unknown"
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}

