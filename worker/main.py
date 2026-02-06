"""
Worker entry point. SQS consumer loop and job routing.
Run from project root: PYTHONPATH=. python -m worker.main
"""
from __future__ import annotations

import json
import logging
import signal
import sys
import time
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
    COMPUTE_ACTIONS_JOB_TYPE,
    GENERATE_BASELINE_REPORT_JOB_TYPE,
    GENERATE_EXPORT_JOB_TYPE,
    REMEDIATION_RUN_JOB_TYPE,
    WEEKLY_DIGEST_JOB_TYPE,
    parse_queue_region,
)
from worker.config import settings
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
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidIdentityToken",
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


# ---------------------------------------------------------------------------
# SQS helpers with retry
# ---------------------------------------------------------------------------
REQUIRED_JOB_FIELDS = {"tenant_id", "account_id", "region", "job_type"}
COMPUTE_ACTIONS_REQUIRED_FIELDS = {"tenant_id", "job_type"}
REMEDIATION_RUN_REQUIRED_FIELDS = {"job_type", "run_id", "tenant_id", "action_id", "mode", "created_at"}
GENERATE_EXPORT_REQUIRED_FIELDS = {"job_type", "export_id", "tenant_id", "created_at"}
GENERATE_BASELINE_REPORT_REQUIRED_FIELDS = {"job_type", "report_id", "tenant_id", "created_at"}
WEEKLY_DIGEST_REQUIRED_FIELDS = {"job_type", "tenant_id", "created_at"}


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
        VisibilityTimeout=30,
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
def run_worker() -> None:
    """Long-poll SQS, route by job_type, delete on success, retry on failure."""
    queue_url = settings.SQS_INGEST_QUEUE_URL
    if not queue_url:
        logger.error("SQS_INGEST_QUEUE_URL not set. Exiting.")
        sys.exit(1)

    region = parse_queue_region(queue_url)
    logger.info(f"Starting worker. Queue: {queue_url} | Region: {region}")

    sqs = boto3.client("sqs", region_name=region)

    consecutive_errors = 0
    max_consecutive_errors = 5

    while not _shutdown_requested:
        # --- Receive messages with retry ---
        try:
            messages = _receive_messages(sqs, queue_url)
            consecutive_errors = 0  # Reset on success
        except ClientError as e:
            consecutive_errors += 1
            error_code = _get_error_code(e)
            logger.error(f"SQS receive_message failed after retries: {error_code} - {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                logger.critical(f"Too many consecutive SQS errors ({consecutive_errors}). Backing off...")
                time.sleep(30)  # Long backoff before retrying
                consecutive_errors = 0
            else:
                time.sleep(2)  # Short backoff
            continue

        if not messages:
            continue

        for msg in messages:
            if _shutdown_requested:
                logger.info("Shutdown requested; stopping after current batch.")
                break

            _process_message(sqs, queue_url, msg)

    logger.info("Worker shut down gracefully.")


def _process_message(sqs: Any, queue_url: str, msg: dict) -> None:
    """Process a single SQS message."""
    receipt_handle = msg["ReceiptHandle"]
    body_raw = msg.get("Body", "")
    message_id = msg.get("MessageId", "unknown")

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

    # --- Get handler ---
    handler = get_job_handler(job_type)
    if handler is None:
        logger.warning(f"[{message_id}] Unknown job_type '{job_type}', deleting.")
        _safe_delete_message(sqs, queue_url, receipt_handle)
        return

    # --- Execute handler ---
    try:
        logger.info(
            "[%s] Processing job_type=%s tenant=%s account=%s region=%s",
            message_id,
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
