"""
Worker entry point. SQS consumer loop and job routing.
Run from project root: PYTHONPATH=. python -m worker.main
"""
from __future__ import annotations

import json
import logging
import signal
import sys
import threading
import time
import uuid
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
    INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE,
    RECONCILE_INVENTORY_SHARD_JOB_TYPE,
    RECONCILE_RECENTLY_TOUCHED_RESOURCES_JOB_TYPE,
    REMEDIATION_RUN_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
    parse_queue_region,
)
from backend.services.migration_guard import assert_database_revision_at_head
from backend.models.aws_account import AwsAccount
from backend.models.enums import AwsAccountStatus
from worker.config import settings
from worker.database import session_scope
from worker.jobs import get_job_handler

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
BACKFILL_FINDING_KEYS_REQUIRED_FIELDS = {
    "job_type",
    "created_at",
}
BACKFILL_ACTION_GROUPS_REQUIRED_FIELDS = {
    "job_type",
    "created_at",
}


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
    elif job_type in {EXECUTE_PR_BUNDLE_PLAN_JOB_TYPE, EXECUTE_PR_BUNDLE_APPLY_JOB_TYPE}:
        required = PR_BUNDLE_EXEC_REQUIRED_FIELDS
    elif job_type == INGEST_CONTROL_PLANE_EVENTS_JOB_TYPE:
        required = INGEST_CONTROL_PLANE_EVENT_REQUIRED_FIELDS
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

    if pool == "all":
        selected = [("events", all_configs.get("events", "")), ("inventory", all_configs.get("inventory", "")), ("legacy", all_configs.get("legacy", ""))]
        return [(name, url) for name, url in selected if url]

    if pool in {"legacy", "events", "inventory"}:
        url = all_configs.get(pool, "")
        return [(pool, url)] if url else []

    logger.warning("Unknown WORKER_POOL=%s. Falling back to legacy queue.", pool)
    url = all_configs.get("legacy", "")
    return [("legacy", url)] if url else []


def run_worker() -> None:
    """Long-poll configured SQS queue(s), route by job_type, delete on success."""
    assert_database_revision_at_head(component="worker")
    queue_configs = _resolve_queue_configs()
    if not queue_configs:
        logger.error(
            "No worker queue configured for WORKER_POOL=%s. "
            "Set one of SQS_INGEST_QUEUE_URL / SQS_EVENTS_FAST_LANE_QUEUE_URL / "
            "SQS_INVENTORY_RECONCILE_QUEUE_URL.",
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

    consecutive_errors: dict[str, int] = {queue_name: 0 for queue_name, _ in queue_configs}
    max_consecutive_errors = 5

    while not _shutdown_requested:
        for queue_name, (sqs, queue_url) in queue_clients.items():
            try:
                messages = _receive_messages(sqs, queue_url)
                consecutive_errors[queue_name] = 0
            except ClientError as e:
                consecutive_errors[queue_name] += 1
                error_code = _get_error_code(e)
                logger.error(
                    "SQS receive_message failed queue=%s after retries: %s - %s",
                    queue_name,
                    error_code,
                    e,
                )

                if consecutive_errors[queue_name] >= max_consecutive_errors:
                    logger.critical(
                        "Too many consecutive SQS errors queue=%s (%s). Backing off...",
                        queue_name,
                        consecutive_errors[queue_name],
                    )
                    time.sleep(30)
                    consecutive_errors[queue_name] = 0
                else:
                    time.sleep(2)
                continue

            if not messages:
                continue

            for msg in messages:
                if _shutdown_requested:
                    logger.info("Shutdown requested; stopping after current batch.")
                    break
                _process_message(sqs, queue_url, msg, queue_name=queue_name)

    logger.info("Worker shut down gracefully.")


def _process_message(sqs: Any, queue_url: str, msg: dict, queue_name: str = "unknown") -> None:
    """Process a single SQS message."""
    receipt_handle = msg["ReceiptHandle"]
    body_raw = msg.get("Body", "")
    message_id = msg.get("MessageId", "unknown")
    receive_count = _approx_receive_count(msg)

    # --- Parse JSON ---
    try:
        job: dict = json.loads(body_raw)
    except json.JSONDecodeError as e:
        logger.warning(f"[{message_id}] Invalid JSON, deleting. Error: {e}")
        _safe_delete_message(sqs, queue_url, receipt_handle)
        return

    # --- Validate fields ---
    missing = _validate_job(job)
    if missing:
        logger.warning(f"[{message_id}] Missing fields {missing}, deleting. Body: {body_raw[:200]}")
        _safe_delete_message(sqs, queue_url, receipt_handle)
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
            "[%s] Retried message queue=%s receive_count=%s job_type=%s tenant=%s account=%s region=%s",
            message_id,
            queue_name,
            receive_count,
            job_type,
            tenant_id,
            account_id,
            region,
        )

    # --- Get handler ---
    handler = get_job_handler(job_type)
    if handler is None:
        logger.warning(f"[{message_id}] Unknown job_type '{job_type}', deleting.")
        _safe_delete_message(sqs, queue_url, receipt_handle)
        return

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
            "[%s] Processing queue=%s receive_count=%s job_type=%s tenant=%s account=%s region=%s",
            message_id,
            queue_name,
            receive_count,
            job_type,
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
