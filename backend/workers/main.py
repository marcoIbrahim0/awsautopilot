"""
Worker entry point. SQS consumer loop and job routing.
Run from project root: PYTHONPATH=. python -m backend.workers.main
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
import json
import hashlib
import logging
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from backend.utils.sqs import (
    BACKFILL_ACTION_GROUPS_JOB_TYPE,
    BACKFILL_FINDING_KEYS_JOB_TYPE,
    COMPUTE_ACTIONS_JOB_TYPE,
    EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE,
    EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE,
    GENERATE_BASELINE_REPORT_JOB_TYPE,
    GENERATE_EXPORT_JOB_TYPE,
    INGEST_ACCESS_ANALYZER_JOB_TYPE,
    INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE,
    INGEST_INSPECTOR_JOB_TYPE,
    INTEGRATION_SYNC_JOB_TYPE,
    INGEST_JOB_TYPE,
    QUEUE_PAYLOAD_SCHEMA_VERSION,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
    RECONCILE_ACTION_REMEDIATION_SYNC_JOB_TYPE,
    RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE,
    RECONCILE_INVENTORY_SHARD_JOB_TYPE,
    RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE,
    REMEDIATION_RUN_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
    parse_queue_region,
)
from backend.services.migration_guard import assert_database_revision_at_head
from backend.models.aws_account import AwsAccount
from backend.models.enums import AwsAccountStatus
from backend.workers.config import settings
from backend.workers.database import session_scope
from backend.workers.jobs import get_job_handler

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker")

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown_requested = False


def _handle_shutdown(signum: int, frame: Any) -> None:
    global _shutdown_requested
    logger.info(f"Received signal {signum}. Finishing current message, then shutting down...")
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)

# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------
# AWS error codes that are transient and should be retried
TRANSIENT_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "RequestThrottled",
    "ProvisionedThroughputExceededException",
    "ServiceUnavailable",
    "ServiceUnavailableException",
    "InternalError",
    "InternalServiceError",
    "RequestTimeout",
    "RequestTimeoutException",
    "IDPCommunicationError",
}

# AWS error codes that indicate permission issues (non-retryable)
PERMISSION_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "UnauthorizedAccess",
    "UnauthorizedOperation",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidIdentityToken",
    "ValidationError",
}


def _is_transient_error(exc: BaseException) -> bool:
    """Check if exception is a transient AWS error that should be retried."""
    if isinstance(exc, ClientError):
        error_code = exc.response.get("Error", {}).get("Code", "")
        return error_code in TRANSIENT_ERROR_CODES
    return False


def _is_permission_error(exc: BaseException) -> bool:
    """Check if exception is a permission error (non-retryable)."""
    if isinstance(exc, ClientError):
        error_code = exc.response.get("Error", {}).get("Code", "")
        return error_code in PERMISSION_ERROR_CODES
    return False


def _get_error_code(exc: BaseException) -> str:
    """Extract AWS error code from exception, or return exception class name."""
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code", "ClientError")
    return type(exc).__name__


def _is_assume_role_failure(exc: BaseException) -> bool:
    return isinstance(exc, ClientError) and getattr(exc, "operation_name", "") == "AssumeRole"


def _approx_receive_count(msg: dict) -> int:
    attrs = msg.get("Attributes") or {}
    raw = attrs.get("ApproximateReceiveCount")
    try:
        return max(1, int(raw))
    except Exception:
        return 1


def _maybe_quarantine_account(job: dict, *, receive_count: int, error_code: str) -> None:
    if not settings.CONTROL_PLANE_AUTO_DISABLE_ASSUME_ROLE_FAILURES:
        return
    threshold = max(1, int(settings.CONTROL_PLANE_ASSUME_ROLE_QUARANTINE_RECEIVE_COUNT or 3))
    if receive_count < threshold:
        return

    tenant_id_raw = job.get("tenant_id")
    account_id = str(job.get("account_id") or "").strip()
    if not tenant_id_raw or not account_id:
        return
    try:
        tenant_id = uuid.UUID(str(tenant_id_raw))
    except ValueError:
        return

    with session_scope() as session:
        account = (
            session.query(AwsAccount)
            .filter(AwsAccount.tenant_id == tenant_id, AwsAccount.account_id == account_id)
            .first()
        )
        if account is None:
            return
        status_value = getattr(account.status, "value", str(account.status)).lower()
        if status_value == "disabled":
            return
        account.status = AwsAccountStatus.disabled

    logger.warning(
        "Auto-disabled AWS account after repeated AssumeRole failures tenant_id=%s account_id=%s receive_count=%s error_code=%s",
        tenant_id,
        account_id,
        receive_count,
        error_code,
    )


# ---------------------------------------------------------------------------
# SQS helpers with retry
# ---------------------------------------------------------------------------
REQUIRED_JOB_FIELDS = {"tenant_id", "account_id", "region", "job_type"}
COMPUTE_ACTIONS_REQUIRED_FIELDS = {"tenant_id", "job_type"}
REMEDIATION_RUN_REQUIRED_FIELDS = {"job_type", "run_id", "tenant_id", "action_id", "mode", "created_at"}
GENERATE_EXPORT_REQUIRED_FIELDS = {"job_type", "export_id", "tenant_id", "created_at"}
GENERATE_BASELINE_REPORT_REQUIRED_FIELDS = {"job_type", "report_id", "tenant_id", "created_at"}
WEEKLY_DIGEST_REQUIRED_FIELDS = {"job_type", "tenant_id", "created_at"}
PR_BUNDLE_EXEC_REQUIRED_FIELDS = {"job_type", "execution_id", "run_id", "tenant_id", "phase", "created_at"}
INTEGRATION_SYNC_REQUIRED_FIELDS = {"job_type", "task_id", "tenant_id", "created_at"}
RECONCILE_ACTION_REMEDIATION_SYNC_REQUIRED_FIELDS = {"job_type", "created_at"}
INGEST_CONTROL_PLANE_EVENT_REQUIRED_FIELDS = {
    "job_type",
    "tenant_id",
    "account_id",
    "region",
    "event",
    "event_id",
    "event_time",
    "intake_time",
    "created_at",
}
RECONCILE_INVENTORY_SHARD_REQUIRED_FIELDS = {
    "job_type",
    "tenant_id",
    "account_id",
    "region",
    "service",
    "created_at",
}
RECONCILE_RECENTLY_TOUCHED_RESOURCES_REQUIRED_FIELDS = {
    "job_type",
    "tenant_id",
    "created_at",
}
RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_REQUIRED_FIELDS = {
    "job_type",
    "tenant_id",
    "orchestration_job_id",
    "created_at",
}
BACKFILL_FINDING_KEYS_REQUIRED_FIELDS = {
    "job_type",
    "created_at",
}
BACKFILL_ACTION_GROUPS_REQUIRED_FIELDS = {
    "job_type",
    "created_at",
}
CONTRACT_VIOLATION_INVALID_JSON = "invalid_json"
CONTRACT_VIOLATION_MISSING_FIELDS = "missing_fields"
CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE = "unknown_job_type"
CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION = "unsupported_schema_version"
LEGACY_QUEUE_PAYLOAD_SCHEMA_VERSION = REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
SUPPORTED_QUEUE_SCHEMA_VERSIONS_BY_JOB_TYPE: dict[str, set[int]] = {
    job_type: {QUEUE_PAYLOAD_SCHEMA_VERSION}
    for job_type in {
        BACKFILL_ACTION_GROUPS_JOB_TYPE,
        BACKFILL_FINDING_KEYS_JOB_TYPE,
        COMPUTE_ACTIONS_JOB_TYPE,
        EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE,
        EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE,
        GENERATE_BASELINE_REPORT_JOB_TYPE,
        GENERATE_EXPORT_JOB_TYPE,
        INGEST_ACCESS_ANALYZER_JOB_TYPE,
        INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE,
        INGEST_INSPECTOR_JOB_TYPE,
        INTEGRATION_SYNC_JOB_TYPE,
        INGEST_JOB_TYPE,
        RECONCILE_ACTION_REMEDIATION_SYNC_JOB_TYPE,
        RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE,
        RECONCILE_INVENTORY_SHARD_JOB_TYPE,
        RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE,
        WEEKLY_DIGEST_JOB_TYPE,
    }
}
SUPPORTED_QUEUE_SCHEMA_VERSIONS_BY_JOB_TYPE[REMEDIATION_RUN_JOB_TYPE] = {
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
}


@dataclass
class QueuePollerMetrics:
    polls: int = 0
    empty_polls: int = 0
    messages_received: int = 0
    messages_processed: int = 0
    processing_seconds_total: float = 0.0
    receive_errors: int = 0
    last_log_at_monotonic: float = field(default_factory=time.monotonic)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_quarantine_envelope(
    *,
    message_id: str,
    source_queue_name: str,
    source_queue_url: str,
    receive_count: int,
    body_raw: str,
    reason_code: str,
    reason_detail: str | None = None,
    job: dict | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "reason_code": reason_code,
        "original_message_id": message_id,
        "original_queue_name": source_queue_name,
        "original_queue_url": source_queue_url,
        "payload_sha256": hashlib.sha256(body_raw.encode("utf-8")).hexdigest(),
        "seen_at": _utc_now_iso(),
        "approx_receive_count": receive_count,
        "original_body": body_raw,
    }
    if reason_detail:
        envelope["reason_detail"] = reason_detail
    if isinstance(job, dict):
        envelope["parsed_job"] = job
    return envelope


def _get_contract_quarantine_queue_url() -> str:
    return str(getattr(settings, "SQS_CONTRACT_QUARANTINE_QUEUE_URL", "") or "").strip()


def _quarantine_contract_violation(
    sqs: Any,
    *,
    source_queue_url: str,
    source_queue_name: str,
    msg: dict,
    body_raw: str,
    reason_code: str,
    reason_detail: str | None = None,
    job: dict | None = None,
) -> bool:
    quarantine_queue_url = _get_contract_quarantine_queue_url()
    message_id = msg.get("MessageId", "unknown")
    receipt_handle = msg.get("ReceiptHandle", "")
    receive_count = _approx_receive_count(msg)

    if not quarantine_queue_url:
        logger.warning(
            "[%s] Contract violation (%s) queue=%s but SQS_CONTRACT_QUARANTINE_QUEUE_URL is unset. "
            "Leaving message for SQS retry/DLQ.",
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
    quarantine_sqs = sqs
    source_region = parse_queue_region(source_queue_url)
    quarantine_region = parse_queue_region(quarantine_queue_url)
    if quarantine_region != source_region:
        quarantine_sqs = boto3.client("sqs", region_name=quarantine_region)

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

    _safe_delete_message(sqs, source_queue_url, receipt_handle)
    logger.warning(
        "[%s] Contract violation (%s) quarantined queue=%s quarantine_queue=%s",
        message_id,
        reason_code,
        source_queue_name,
        quarantine_queue_url,
    )
    return True


def _validate_job(job: dict) -> list[str]:
    """Return list of missing required fields, or empty if valid."""
    job_type = (job.get("job_type") or "").strip() if isinstance(job.get("job_type"), str) else job.get("job_type")
    # remediation_run has distinct shape: run_id, action_id, mode (no account_id/region)
    if job_type == REMEDIATION_RUN_JOB_TYPE or (
        job.get("run_id") and job.get("action_id") and job.get("mode")
    ):
        required = REMEDIATION_RUN_REQUIRED_FIELDS
    elif job_type == COMPUTE_ACTIONS_JOB_TYPE:
        required = COMPUTE_ACTIONS_REQUIRED_FIELDS
    elif job_type == GENERATE_EXPORT_JOB_TYPE:
        required = GENERATE_EXPORT_REQUIRED_FIELDS
    elif job_type == GENERATE_BASELINE_REPORT_JOB_TYPE:
        required = GENERATE_BASELINE_REPORT_REQUIRED_FIELDS
    elif job_type == WEEKLY_DIGEST_JOB_TYPE:
        required = WEEKLY_DIGEST_REQUIRED_FIELDS
    elif job_type == INTEGRATION_SYNC_JOB_TYPE:
        required = INTEGRATION_SYNC_REQUIRED_FIELDS
    elif job_type == RECONCILE_ACTION_REMEDIATION_SYNC_JOB_TYPE:
        required = RECONCILE_ACTION_REMEDIATION_SYNC_REQUIRED_FIELDS
    elif job_type in {EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE, EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE}:
        required = PR_BUNDLE_EXEC_REQUIRED_FIELDS
    elif job_type == INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE:
        required = INGEST_CONTROL_PLANE_EVENT_REQUIRED_FIELDS
    elif job_type == RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_JOB_TYPE:
        required = RECONCILE_INVENTORY_GLOBAL_ORCHESTRATION_REQUIRED_FIELDS
    elif job_type == RECONCILE_INVENTORY_SHARD_JOB_TYPE:
        required = RECONCILE_INVENTORY_SHARD_REQUIRED_FIELDS
    elif job_type == RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE:
        required = RECONCILE_RECENTLY_TOUCHED_RESOURCES_REQUIRED_FIELDS
    elif job_type == BACKFILL_FINDING_KEYS_JOB_TYPE:
        required = BACKFILL_FINDING_KEYS_REQUIRED_FIELDS
    elif job_type == BACKFILL_ACTION_GROUPS_JOB_TYPE:
        required = BACKFILL_ACTION_GROUPS_REQUIRED_FIELDS
    else:
        required = REQUIRED_JOB_FIELDS
    return [f for f in required if f not in job or job[f] is None]


def _parse_schema_version(raw_schema_version: Any) -> int | None:
    """Parse schema_version as an integer; return None when invalid."""
    if isinstance(raw_schema_version, bool):
        return None
    if isinstance(raw_schema_version, int):
        return raw_schema_version
    if isinstance(raw_schema_version, str):
        value = raw_schema_version.strip()
        if value.isdigit():
            return int(value)
    return None


def _resolve_schema_version(job: dict) -> int | None:
    raw_schema_version = job.get("schema_version", LEGACY_QUEUE_PAYLOAD_SCHEMA_VERSION)
    return _parse_schema_version(raw_schema_version)


def _supported_schema_versions(job_type: str) -> set[int]:
    return SUPPORTED_QUEUE_SCHEMA_VERSIONS_BY_JOB_TYPE.get(job_type, set())


def _is_schema_version_supported(job_type: str, schema_version: int) -> bool:
    return schema_version in _supported_schema_versions(job_type)


def _max_in_flight_per_queue() -> int:
    raw = getattr(settings, "WORKER_MAX_IN_FLIGHT_PER_QUEUE", 10)
    try:
        return max(1, int(raw))
    except Exception:
        return 10


def _metrics_log_interval_seconds() -> int:
    raw = getattr(settings, "WORKER_QUEUE_METRICS_LOG_INTERVAL_SECONDS", 60)
    try:
        return max(10, int(raw))
    except Exception:
        return 60


@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _receive_messages(sqs: Any, queue_url: str) -> list[dict]:
    """Receive messages from SQS with retry for transient errors."""
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,  # long polling
        VisibilityTimeout=300,
        AttributeNames=["ApproximateReceiveCount"],
    )
    return response.get("Messages", [])


@retry(
    retry=retry_if_exception(_is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _delete_message(sqs: Any, queue_url: str, receipt_handle: str) -> None:
    """Delete message from SQS with retry for transient errors."""
    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def _resolve_queue_configs() -> list[tuple[str, str]]:
    """
    Resolve queue list from WORKER_POOL and configured queue URLs.

    WORKER_POOL values:
    - legacy
    - events
    - inventory
    - export
    - all
    """
    pool = (settings.WORKER_POOL or "legacy").strip().lower()
    all_configs: dict[str, str] = {}
    if settings.SQS_INGEST_QUEUE_URL and settings.SQS_INGEST_QUEUE_URL.strip():
        all_configs["legacy"] = settings.SQS_INGEST_QUEUE_URL.strip()
    if settings.SQS_EVENTS_FAST_LANE_QUEUE_URL and settings.SQS_EVENTS_FAST_LANE_QUEUE_URL.strip():
        all_configs["events"] = settings.SQS_EVENTS_FAST_LANE_QUEUE_URL.strip()
    if settings.SQS_INVENTORY_RECONCILE_QUEUE_URL and settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip():
        all_configs["inventory"] = settings.SQS_INVENTORY_RECONCILE_QUEUE_URL.strip()
    if settings.SQS_EXPORT_REPORT_QUEUE_URL and settings.SQS_EXPORT_REPORT_QUEUE_URL.strip():
        all_configs["export"] = settings.SQS_EXPORT_REPORT_QUEUE_URL.strip()

    if pool == "all":
        selected = [
            ("events", all_configs.get("events", "")),
            ("inventory", all_configs.get("inventory", "")),
            ("export", all_configs.get("export", "")),
            ("legacy", all_configs.get("legacy", "")),
        ]
        return [(name, url) for name, url in selected if url]

    if pool in {"legacy", "events", "inventory", "export"}:
        url = all_configs.get(pool, "")
        return [(pool, url)] if url else []

    logger.warning("Unknown WORKER_POOL=%s. Falling back to legacy queue.", pool)
    url = all_configs.get("legacy", "")
    return [("legacy", url)] if url else []


def _drain_completed_futures(
    queue_name: str,
    in_flight: set[Future[float]],
    metrics: QueuePollerMetrics,
) -> None:
    done = [future for future in in_flight if future.done()]
    for future in done:
        in_flight.discard(future)
        try:
            duration = float(future.result())
            metrics.messages_processed += 1
            metrics.processing_seconds_total += max(0.0, duration)
        except Exception:
            logger.exception("Queue worker future failed queue=%s", queue_name)


def _maybe_log_queue_metrics(
    queue_name: str,
    metrics: QueuePollerMetrics,
    *,
    in_flight_count: int,
    force: bool = False,
) -> None:
    now = time.monotonic()
    interval_seconds = _metrics_log_interval_seconds()
    if not force and (now - metrics.last_log_at_monotonic) < interval_seconds:
        return

    empty_poll_rate = (metrics.empty_polls / metrics.polls) if metrics.polls else 0.0
    average_processing_ms = (
        (metrics.processing_seconds_total / metrics.messages_processed) * 1000.0
        if metrics.messages_processed
        else 0.0
    )
    logger.info(
        "Queue metrics queue=%s polls=%s empty_polls=%s empty_poll_rate=%.2f "
        "messages_received=%s messages_processed=%s in_flight=%s "
        "avg_processing_ms=%.2f receive_errors=%s",
        queue_name,
        metrics.polls,
        metrics.empty_polls,
        empty_poll_rate,
        metrics.messages_received,
        metrics.messages_processed,
        in_flight_count,
        average_processing_ms,
        metrics.receive_errors,
    )
    metrics.polls = 0
    metrics.empty_polls = 0
    metrics.messages_received = 0
    metrics.messages_processed = 0
    metrics.processing_seconds_total = 0.0
    metrics.receive_errors = 0
    metrics.last_log_at_monotonic = now


def _process_message_timed(sqs: Any, queue_url: str, msg: dict, queue_name: str) -> float:
    started = time.monotonic()
    _process_message(sqs, queue_url, msg, queue_name=queue_name)
    return time.monotonic() - started


def _run_queue_poller(queue_name: str, sqs: Any, queue_url: str, *, max_in_flight: int) -> None:
    consecutive_errors = 0
    max_consecutive_errors = 5
    metrics = QueuePollerMetrics()
    in_flight: set[Future[float]] = set()

    with ThreadPoolExecutor(
        max_workers=max_in_flight,
        thread_name_prefix=f"worker-{queue_name}",
    ) as executor:
        while not _shutdown_requested:
            _drain_completed_futures(queue_name, in_flight, metrics)
            _maybe_log_queue_metrics(queue_name, metrics, in_flight_count=len(in_flight))

            if len(in_flight) >= max_in_flight:
                wait(in_flight, timeout=1.0, return_when=FIRST_COMPLETED)
                continue

            try:
                messages = _receive_messages(sqs, queue_url)
                metrics.polls += 1
                consecutive_errors = 0
            except ClientError as e:
                metrics.receive_errors += 1
                consecutive_errors += 1
                error_code = _get_error_code(e)
                logger.error(
                    "SQS receive_message failed queue=%s after retries: %s - %s",
                    queue_name,
                    error_code,
                    e,
                )

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(
                        "Too many consecutive SQS errors queue=%s (%s). Backing off...",
                        queue_name,
                        consecutive_errors,
                    )
                    time.sleep(30)
                    consecutive_errors = 0
                else:
                    time.sleep(2)
                continue

            if not messages:
                metrics.empty_polls += 1
                continue

            for msg in messages:
                if _shutdown_requested:
                    logger.info("Shutdown requested; stopping queue poller queue=%s", queue_name)
                    break

                while len(in_flight) >= max_in_flight and not _shutdown_requested:
                    wait(in_flight, timeout=1.0, return_when=FIRST_COMPLETED)
                    _drain_completed_futures(queue_name, in_flight, metrics)
                    _maybe_log_queue_metrics(queue_name, metrics, in_flight_count=len(in_flight))

                if _shutdown_requested:
                    break

                metrics.messages_received += 1
                in_flight.add(executor.submit(_process_message_timed, sqs, queue_url, msg, queue_name))

        # Drain in-flight work before exiting.
        while in_flight:
            wait(in_flight, timeout=1.0, return_when=FIRST_COMPLETED)
            _drain_completed_futures(queue_name, in_flight, metrics)
            _maybe_log_queue_metrics(queue_name, metrics, in_flight_count=len(in_flight))

    _maybe_log_queue_metrics(queue_name, metrics, in_flight_count=0, force=True)
    logger.info("Queue poller exited queue=%s", queue_name)


def run_worker() -> None:
    """Long-poll configured SQS queue(s), route by job_type, delete on success."""
    assert_database_revision_at_head(component="worker")
    queue_configs = _resolve_queue_configs()
    if not queue_configs:
        logger.error(
            "No worker queue configured for WORKER_POOL=%s. "
            "Set one of SQS_INGEST_QUEUE_URL / SQS_EVENTS_FAST_LANE_QUEUE_URL / "
            "SQS_INVENTORY_RECONCILE_QUEUE_URL / SQS_EXPORT_REPORT_QUEUE_URL.",
            settings.WORKER_POOL,
        )
        sys.exit(1)

    queue_clients: dict[str, tuple[Any, str]] = {}
    for queue_name, queue_url in queue_configs:
        region = parse_queue_region(queue_url)
        logger.info(
            "Starting worker pool=%s queue=%s url=%s region=%s",
            settings.WORKER_POOL,
            queue_name,
            queue_url,
            region,
        )
        queue_clients[queue_name] = (
            boto3.client("sqs", region_name=region),
            queue_url,
        )

    max_in_flight = _max_in_flight_per_queue()
    logger.info("Worker concurrency guardrail max_in_flight_per_queue=%s", max_in_flight)

    poller_threads: dict[str, threading.Thread] = {}
    for queue_name, (sqs, queue_url) in queue_clients.items():
        thread = threading.Thread(
            target=_run_queue_poller,
            args=(queue_name, sqs, queue_url),
            kwargs={"max_in_flight": max_in_flight},
            name=f"queue-poller-{queue_name}",
            daemon=True,
        )
        thread.start()
        poller_threads[queue_name] = thread

    while not _shutdown_requested:
        for queue_name, thread in poller_threads.items():
            if not thread.is_alive():
                logger.error("Queue poller stopped unexpectedly queue=%s. Triggering shutdown.", queue_name)
                _handle_shutdown(signal.SIGTERM, None)
                break
        time.sleep(1)

    for queue_name, thread in poller_threads.items():
        thread.join()
        logger.info("Queue poller joined queue=%s", queue_name)

    logger.info("Worker shut down gracefully.")


def _process_message(sqs: Any, queue_url: str, msg: dict, queue_name: str = "unknown") -> None:
    """Process a single SQS message."""
    receipt_handle = msg["ReceiptHandle"]
    body_raw = msg.get("Body", "")
    if not isinstance(body_raw, str):
        body_raw = str(body_raw)
    message_id = msg.get("MessageId", "unknown")
    receive_count = _approx_receive_count(msg)

    # --- Parse JSON ---
    try:
        job: dict = json.loads(body_raw)
    except json.JSONDecodeError as e:
        _quarantine_contract_violation(
            sqs,
            source_queue_url=queue_url,
            source_queue_name=queue_name,
            msg=msg,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_INVALID_JSON,
            reason_detail=f"json_error={str(e)[:200]}",
        )
        return

    # --- Validate fields ---
    missing = _validate_job(job)
    if missing:
        missing_list = ",".join(sorted(missing))
        _quarantine_contract_violation(
            sqs,
            source_queue_url=queue_url,
            source_queue_name=queue_name,
            msg=msg,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_MISSING_FIELDS,
            reason_detail=f"missing_required_fields={missing_list}",
            job=job,
        )
        return

    # Normalize job_type for routing (remediation_run detected by shape if job_type unclear)
    job_type = (job.get("job_type") or "").strip() if isinstance(job.get("job_type"), str) else job.get("job_type")
    if not job_type and job.get("run_id") and job.get("action_id") and job.get("mode"):
        job_type = REMEDIATION_RUN_JOB_TYPE
    tenant_id = job["tenant_id"]
    account_id = job.get("account_id")
    region = job.get("region")

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
            region,
        )

    # --- Get handler ---
    handler = get_job_handler(job_type)
    if handler is None:
        _quarantine_contract_violation(
            sqs,
            source_queue_url=queue_url,
            source_queue_name=queue_name,
            msg=msg,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNKNOWN_JOB_TYPE,
            reason_detail=f"job_type={job_type}",
            job=job,
        )
        return

    schema_version = _resolve_schema_version(job)
    if schema_version is None:
        _quarantine_contract_violation(
            sqs,
            source_queue_url=queue_url,
            source_queue_name=queue_name,
            msg=msg,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION,
            reason_detail=f"invalid_schema_version={job.get('schema_version')!r}",
            job=job,
        )
        return

    if not _is_schema_version_supported(job_type, schema_version):
        supported = ",".join(str(version) for version in sorted(_supported_schema_versions(job_type)))
        _quarantine_contract_violation(
            sqs,
            source_queue_url=queue_url,
            source_queue_name=queue_name,
            msg=msg,
            body_raw=body_raw,
            reason_code=CONTRACT_VIOLATION_UNSUPPORTED_SCHEMA_VERSION,
            reason_detail=(
                f"job_type={job_type} schema_version={schema_version} "
                f"supported_versions={supported or 'none'}"
            ),
            job=job,
        )
        return
    job["schema_version"] = schema_version

    # --- Execute handler ---
    stop_heartbeat = threading.Event()

    def _visibility_heartbeat() -> None:
        interval_seconds = 120
        while not stop_heartbeat.wait(interval_seconds):
            try:
                sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=300,
                )
            except ClientError as exc:
                logger.warning(
                    "[%s] Visibility heartbeat failed; execution may be retried by SQS: %s",
                    message_id,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.warning("[%s] Unexpected heartbeat error: %s", message_id, exc)

    heartbeat_thread = threading.Thread(
        target=_visibility_heartbeat,
        name=f"sqs-heartbeat-{message_id}",
        daemon=True,
    )
    heartbeat_thread.start()

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
            region,
        )
        handler(job)
        _safe_delete_message(sqs, queue_url, receipt_handle)
        logger.info(f"[{message_id}] Job completed and message deleted.")
    except Exception as e:
        error_code = _get_error_code(e)
        
        if _is_permission_error(e):
            # Permission errors: log clearly, let SQS retry → DLQ
            # Future: could notify API to update account status
            logger.error(
                f"[{message_id}] Permission error ({error_code}) for account={account_id}. "
                f"Message will retry via SQS (eventually DLQ). Error: {e}"
            )
            if _is_assume_role_failure(e):
                _maybe_quarantine_account(job, receive_count=receive_count, error_code=error_code)
        elif _is_transient_error(e):
            # Transient errors: log, let SQS retry
            logger.warning(
                f"[{message_id}] Transient error ({error_code}) for job_type={job_type}. "
                f"Message will retry via SQS. Error: {e}"
            )
        else:
            # Other errors: log full traceback, let SQS retry → DLQ
            logger.exception(
                f"[{message_id}] Handler failed ({error_code}) for job_type={job_type}. "
                f"Message will retry via SQS (eventually DLQ)."
            )
        # Don't delete; visibility timeout expires and message retries
    finally:
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=1.0)


def _safe_delete_message(sqs: Any, queue_url: str, receipt_handle: str) -> None:
    """Delete message with retry, logging errors but not raising."""
    try:
        _delete_message(sqs, queue_url, receipt_handle)
    except ClientError as e:
        logger.error(f"Failed to delete message after retries: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run_worker()
