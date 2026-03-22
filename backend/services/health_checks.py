"""
Dependency-aware health checks for API readiness.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.config import settings
from backend.database import ping_db
from backend.utils.sqs import parse_queue_region


REQUIRED_SQS_QUEUE_SETTINGS: tuple[tuple[str, str], ...] = (
    ("ingest", "SQS_INGEST_QUEUE_URL"),
    ("events_fast_lane", "SQS_EVENTS_FAST_LANE_QUEUE_URL"),
    ("inventory_reconcile", "SQS_INVENTORY_RECONCILE_QUEUE_URL"),
    ("export_report", "SQS_EXPORT_REPORT_QUEUE_URL"),
)
SUPPORTED_SQS_ATTRIBUTE_NAMES: tuple[str, ...] = (
    "QueueArn",
    "ApproximateNumberOfMessages",
    "ApproximateNumberOfMessagesNotVisible",
)
QUEUE_LAG_METRIC_NAMESPACE = "AWS/SQS"
QUEUE_LAG_METRIC_NAME = "ApproximateAgeOfOldestMessage"
QUEUE_LAG_METRIC_LOOKBACK_MINUTES = 5
QUEUE_LAG_METRIC_PERIOD_SECONDS = 60
QUEUE_LAG_METRIC_ACCESS_DENIED = "metric_access_denied"
QUEUE_LAG_METRIC_UNAVAILABLE = "metric_unavailable"

READINESS_SIMULATION_ENV = "READINESS_SIMULATION_MODE"
SIM_MODE_FAILURE = "dependency_failure"
SIM_MODE_RECOVERED = "recovered"


def required_sqs_queue_urls() -> tuple[dict[str, str], list[str]]:
    queue_urls: dict[str, str] = {}
    missing_queues: list[str] = []
    for queue_name, setting_name in REQUIRED_SQS_QUEUE_SETTINGS:
        queue_url = str(getattr(settings, setting_name, "") or "").strip()
        if not queue_url:
            missing_queues.append(queue_name)
            continue
        queue_urls[queue_name] = queue_url
    return queue_urls, missing_queues


def _parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # "Nearest rank" percentile keeps behavior deterministic for small sample sizes.
    rank = int(round((len(ordered) - 1) * 0.95))
    return float(ordered[max(0, min(rank, len(ordered) - 1))])


def _queue_name_from_url(queue_url: str) -> str:
    return (queue_url or "").rstrip("/").rsplit("/", 1)[-1].strip()


def _latest_metric_max(datapoints: list[dict[str, Any]]) -> float | None:
    if not datapoints:
        return None
    baseline = datetime.fromtimestamp(0, tz=timezone.utc)
    latest = max(datapoints, key=lambda item: item.get("Timestamp") or baseline)
    maximum = latest.get("Maximum")
    if maximum is None:
        return None
    return float(maximum)


def _queue_metric_error_marker(exc: Exception) -> str:
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code") or "").strip()
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedOperation"}:
            return QUEUE_LAG_METRIC_ACCESS_DENIED
    return QUEUE_LAG_METRIC_UNAVAILABLE


def _queue_oldest_message_age_seconds(
    cloudwatch_client: Any,
    queue_name: str,
    checked_at: datetime,
) -> tuple[float | None, str | None]:
    try:
        response = cloudwatch_client.get_metric_statistics(
            Namespace=QUEUE_LAG_METRIC_NAMESPACE,
            MetricName=QUEUE_LAG_METRIC_NAME,
            Dimensions=[{"Name": "QueueName", "Value": queue_name}],
            StartTime=checked_at - timedelta(minutes=QUEUE_LAG_METRIC_LOOKBACK_MINUTES),
            EndTime=checked_at,
            Period=QUEUE_LAG_METRIC_PERIOD_SECONDS,
            Statistics=["Maximum"],
        )
    except (ClientError, BotoCoreError, Exception) as exc:
        return None, _queue_metric_error_marker(exc)
    return _latest_metric_max(response.get("Datapoints") or []), None


def _simulation_mode() -> str:
    raw = str(os.getenv(READINESS_SIMULATION_ENV, "") or "").strip().lower()
    if raw in {"fail", "failure"}:
        return SIM_MODE_FAILURE
    if raw in {"recovered", "recover", "healthy", "ok"}:
        return SIM_MODE_RECOVERED
    if raw == SIM_MODE_FAILURE:
        return SIM_MODE_FAILURE
    if raw == SIM_MODE_RECOVERED:
        return SIM_MODE_RECOVERED
    return ""


def _simulated_readiness_report(mode: str, checked_at: str) -> dict[str, Any]:
    required_queues = [name for name, _ in REQUIRED_SQS_QUEUE_SETTINGS]

    if mode == SIM_MODE_FAILURE:
        return {
            "status": "degraded",
            "ready": False,
            "checked_at": checked_at,
            "simulation_mode": mode,
            "dependencies": {
                "database": {
                    "ready": False,
                    "error": "Simulated database dependency failure.",
                },
                "sqs": {
                    "ready": False,
                    "required_queues": required_queues,
                    "missing_queues": ["ingest"],
                    "errors": ["Simulated SQS dependency failure."],
                    "queues": {},
                },
            },
            "slo": {
                "queue_lag_seconds_p95": None,
                "queue_lag_seconds_max": None,
            },
        }

    simulated_queues = {
        queue_name: {
            "ready": True,
            "queue_url": f"simulated://{queue_name}",
            "region": settings.AWS_REGION,
            "queue_arn": f"arn:aws:sqs:{settings.AWS_REGION}:000000000000:{queue_name}",
            "visible_messages": 0,
            "in_flight_messages": 0,
            "oldest_message_age_seconds": 0,
        }
        for queue_name in required_queues
    }

    return {
        "status": "ok",
        "ready": True,
        "checked_at": checked_at,
        "simulation_mode": mode,
        "dependencies": {
            "database": {
                "ready": True,
                "error": None,
            },
            "sqs": {
                "ready": True,
                "required_queues": required_queues,
                "missing_queues": [],
                "errors": [],
                "queues": simulated_queues,
            },
        },
        "slo": {
            "queue_lag_seconds_p95": 0.0,
            "queue_lag_seconds_max": 0.0,
        },
    }


def _queue_snapshot(
    queue_urls: dict[str, str],
    checked_at: datetime,
) -> tuple[dict[str, dict[str, Any]], list[str], list[float]]:
    snapshots: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    oldest_message_seconds: list[float] = []
    sqs_clients: dict[str, Any] = {}
    cloudwatch_clients: dict[str, Any] = {}

    for queue_name, queue_url in queue_urls.items():
        queue_region = parse_queue_region(queue_url)
        sqs_client = sqs_clients.get(queue_region)
        if sqs_client is None:
            sqs_client = boto3.client("sqs", region_name=queue_region)
            sqs_clients[queue_region] = sqs_client

        try:
            attrs = (
                sqs_client.get_queue_attributes(
                    QueueUrl=queue_url,
                    AttributeNames=list(SUPPORTED_SQS_ATTRIBUTE_NAMES),
                ).get("Attributes")
                or {}
            )
        except (ClientError, BotoCoreError, Exception) as exc:
            snapshots[queue_name] = {
                "ready": False,
                "queue_url": queue_url,
                "region": queue_region,
                "oldest_message_age_seconds": None,
                "error": str(exc),
            }
            errors.append(f"{queue_name}: {exc}")
            continue

        oldest_message_age_seconds: float | None = None
        oldest_message_age_error: str | None = None
        metric_queue_name = _queue_name_from_url(queue_url)
        if metric_queue_name:
            try:
                cloudwatch_client = cloudwatch_clients.get(queue_region)
                if cloudwatch_client is None:
                    cloudwatch_client = boto3.client("cloudwatch", region_name=queue_region)
                    cloudwatch_clients[queue_region] = cloudwatch_client
                (
                    oldest_message_age_seconds,
                    oldest_message_age_error,
                ) = _queue_oldest_message_age_seconds(
                    cloudwatch_client,
                    metric_queue_name,
                    checked_at,
                )
            except (ClientError, BotoCoreError, Exception) as exc:
                oldest_message_age_error = _queue_metric_error_marker(exc)

        if oldest_message_age_seconds is not None:
            oldest_message_seconds.append(oldest_message_age_seconds)

        snapshots[queue_name] = {
            "ready": True,
            "queue_url": queue_url,
            "region": queue_region,
            "queue_arn": attrs.get("QueueArn"),
            "visible_messages": _parse_int(attrs.get("ApproximateNumberOfMessages"), 0),
            "in_flight_messages": _parse_int(attrs.get("ApproximateNumberOfMessagesNotVisible"), 0),
            "oldest_message_age_seconds": oldest_message_age_seconds,
        }
        if oldest_message_age_error:
            snapshots[queue_name]["oldest_message_age_error"] = oldest_message_age_error

    return snapshots, errors, oldest_message_seconds


async def build_readiness_report() -> dict[str, Any]:
    checked_at_dt = datetime.now(timezone.utc)
    checked_at = checked_at_dt.isoformat()
    simulation_mode = _simulation_mode()
    if simulation_mode:
        return _simulated_readiness_report(simulation_mode, checked_at)

    database_ready = await ping_db()
    queue_urls, missing_queues = required_sqs_queue_urls()

    sqs_snapshots: dict[str, dict[str, Any]] = {}
    sqs_errors: list[str] = []
    oldest_message_seconds: list[float] = []

    if missing_queues:
        sqs_errors.append(
            "Missing required queue URLs: "
            + ", ".join(sorted(missing_queues))
        )

    if queue_urls:
        sqs_snapshots, queue_errors, oldest_message_seconds = _queue_snapshot(
            queue_urls,
            checked_at_dt,
        )
        sqs_errors.extend(queue_errors)
    else:
        sqs_errors.append("No SQS queue URLs configured.")

    sqs_ready = (not missing_queues) and (not sqs_errors)
    ready = bool(database_ready and sqs_ready)

    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "checked_at": checked_at,
        "simulation_mode": None,
        "dependencies": {
            "database": {
                "ready": database_ready,
                "error": None if database_ready else "Database ping failed.",
            },
            "sqs": {
                "ready": sqs_ready,
                "required_queues": [name for name, _ in REQUIRED_SQS_QUEUE_SETTINGS],
                "missing_queues": missing_queues,
                "errors": sqs_errors,
                "queues": sqs_snapshots,
            },
        },
        "slo": {
            "queue_lag_seconds_p95": _p95(oldest_message_seconds),
            "queue_lag_seconds_max": (
                float(max(oldest_message_seconds))
                if oldest_message_seconds
                else None
            ),
        },
    }
