from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import ready as ready_endpoint
from backend.services import health_checks


def _queue_urls() -> dict[str, str]:
    return {
        "ingest": "https://sqs.us-east-1.amazonaws.com/123/ingest",
        "events_fast_lane": "https://sqs.us-east-1.amazonaws.com/123/events",
        "inventory_reconcile": "https://sqs.us-east-1.amazonaws.com/123/inventory",
        "export_report": "https://sqs.us-east-1.amazonaws.com/123/export",
    }


def _queue_attributes(queue_arn: str, visible: str = "0", in_flight: str = "0") -> dict[str, dict[str, str]]:
    return {
        "Attributes": {
            "QueueArn": queue_arn,
            "ApproximateNumberOfMessages": visible,
            "ApproximateNumberOfMessagesNotVisible": in_flight,
        }
    }


def _metric_datapoint(maximum: float, minute: int) -> dict[str, object]:
    return {
        "Timestamp": datetime(2026, 3, 9, 12, minute, tzinfo=timezone.utc),
        "Maximum": maximum,
    }


def _client_error(code: str, message: str, operation_name: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, operation_name)


def _boto3_client_factory(sqs_client: MagicMock, cloudwatch_client: MagicMock):
    def _client(service_name: str, region_name: str | None = None):
        assert region_name == "us-east-1"
        if service_name == "sqs":
            return sqs_client
        if service_name == "cloudwatch":
            return cloudwatch_client
        raise AssertionError(f"Unexpected boto3 client request: {service_name}")

    return _client


def test_build_readiness_report_ready_when_db_and_sqs_are_healthy() -> None:
    queue_urls = _queue_urls()
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.side_effect = [
        _queue_attributes("arn:1", visible="0", in_flight="1"),
        _queue_attributes("arn:2", visible="2", in_flight="0"),
        _queue_attributes("arn:3", visible="1", in_flight="0"),
        _queue_attributes("arn:4", visible="0", in_flight="0"),
    ]
    cloudwatch_client = MagicMock()
    cloudwatch_client.get_metric_statistics.side_effect = [
        {"Datapoints": [_metric_datapoint(4.0, 0)]},
        {"Datapoints": [_metric_datapoint(8.0, 1)]},
        {"Datapoints": [_metric_datapoint(12.0, 2)]},
        {"Datapoints": [_metric_datapoint(20.0, 3)]},
    ]

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch(
                "backend.services.health_checks.boto3.client",
                side_effect=_boto3_client_factory(sqs_client, cloudwatch_client),
            ):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is True
    assert report["status"] == "ok"
    assert report["dependencies"]["database"]["ready"] is True
    assert report["dependencies"]["sqs"]["ready"] is True
    assert report["dependencies"]["sqs"]["queues"]["export_report"]["oldest_message_age_seconds"] == 20.0
    assert report["slo"]["queue_lag_seconds_max"] == 20.0
    assert report["slo"]["queue_lag_seconds_p95"] == 20.0
    assert all(
        call.kwargs["AttributeNames"] == list(health_checks.SUPPORTED_SQS_ATTRIBUTE_NAMES)
        for call in sqs_client.get_queue_attributes.call_args_list
    )
    assert all(
        "ApproximateAgeOfOldestMessage" not in call.kwargs["AttributeNames"]
        for call in sqs_client.get_queue_attributes.call_args_list
    )


def test_build_readiness_report_fails_when_required_queue_url_missing() -> None:
    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch(
            "backend.services.health_checks.required_sqs_queue_urls",
            return_value=({}, ["ingest"]),
        ):
            report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is False
    assert report["status"] == "degraded"
    assert report["dependencies"]["sqs"]["ready"] is False
    assert "ingest" in report["dependencies"]["sqs"]["missing_queues"]


def test_build_readiness_report_fails_when_queue_access_is_denied() -> None:
    queue_urls = _queue_urls()
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.side_effect = _client_error(
        "AccessDenied",
        "denied",
        "GetQueueAttributes",
    )
    cloudwatch_client = MagicMock()

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch(
                "backend.services.health_checks.boto3.client",
                side_effect=_boto3_client_factory(sqs_client, cloudwatch_client),
            ):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is False
    assert report["status"] == "degraded"
    assert report["dependencies"]["sqs"]["ready"] is False
    assert "AccessDenied" in report["dependencies"]["sqs"]["errors"][0]
    assert report["dependencies"]["sqs"]["queues"]["ingest"]["ready"] is False
    cloudwatch_client.get_metric_statistics.assert_not_called()


def test_build_readiness_report_fails_when_queue_is_missing_in_sqs() -> None:
    queue_urls = _queue_urls()
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.side_effect = [
        _client_error(
            "AWS.SimpleQueueService.NonExistentQueue",
            "queue does not exist",
            "GetQueueAttributes",
        ),
        _queue_attributes("arn:2"),
        _queue_attributes("arn:3"),
        _queue_attributes("arn:4"),
    ]
    cloudwatch_client = MagicMock()
    cloudwatch_client.get_metric_statistics.side_effect = [
        {"Datapoints": [_metric_datapoint(8.0, 1)]},
        {"Datapoints": [_metric_datapoint(12.0, 2)]},
        {"Datapoints": [_metric_datapoint(20.0, 3)]},
    ]

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch(
                "backend.services.health_checks.boto3.client",
                side_effect=_boto3_client_factory(sqs_client, cloudwatch_client),
            ):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is False
    assert report["dependencies"]["sqs"]["ready"] is False
    assert report["dependencies"]["sqs"]["queues"]["ingest"]["ready"] is False
    assert "NonExistentQueue" in report["dependencies"]["sqs"]["errors"][0]


def test_build_readiness_report_keeps_ready_when_queue_lag_metric_is_partially_unavailable() -> None:
    queue_urls = _queue_urls()
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.side_effect = [
        _queue_attributes("arn:1"),
        _queue_attributes("arn:2"),
        _queue_attributes("arn:3"),
        _queue_attributes("arn:4"),
    ]
    cloudwatch_client = MagicMock()
    cloudwatch_client.get_metric_statistics.side_effect = [
        {"Datapoints": [_metric_datapoint(4.0, 0)]},
        _client_error("AccessDenied", "lag metric denied", "GetMetricStatistics"),
        {"Datapoints": []},
        {"Datapoints": [_metric_datapoint(20.0, 3)]},
    ]

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch(
                "backend.services.health_checks.boto3.client",
                side_effect=_boto3_client_factory(sqs_client, cloudwatch_client),
            ):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is True
    assert report["status"] == "ok"
    assert report["dependencies"]["sqs"]["ready"] is True
    assert report["dependencies"]["sqs"]["errors"] == []
    assert report["dependencies"]["sqs"]["queues"]["events_fast_lane"]["oldest_message_age_seconds"] is None
    assert (
        report["dependencies"]["sqs"]["queues"]["events_fast_lane"]["oldest_message_age_error"]
        == health_checks.QUEUE_LAG_METRIC_ACCESS_DENIED
    )
    assert report["dependencies"]["sqs"]["queues"]["inventory_reconcile"]["oldest_message_age_seconds"] is None
    assert "oldest_message_age_error" not in report["dependencies"]["sqs"]["queues"]["inventory_reconcile"]
    assert report["slo"]["queue_lag_seconds_max"] == 20.0
    assert report["slo"]["queue_lag_seconds_p95"] == 20.0


def test_build_readiness_report_fails_when_database_ping_fails() -> None:
    queue_urls = _queue_urls()
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.return_value = _queue_attributes("arn:ok")
    cloudwatch_client = MagicMock()
    cloudwatch_client.get_metric_statistics.return_value = {
        "Datapoints": [_metric_datapoint(0.0, 0)],
    }

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=False)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch(
                "backend.services.health_checks.boto3.client",
                side_effect=_boto3_client_factory(sqs_client, cloudwatch_client),
            ):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is False
    assert report["dependencies"]["database"]["ready"] is False
    assert report["dependencies"]["sqs"]["ready"] is True


def test_ready_endpoint_returns_200_when_dependency_report_is_ready() -> None:
    app = FastAPI()
    app.get("/ready")(ready_endpoint)
    app.get("/health/ready")(ready_endpoint)

    with patch(
        "backend.main.build_readiness_report",
        new=AsyncMock(return_value={"ready": True, "status": "ok"}),
    ):
        client = TestClient(app)
        response_primary = client.get("/ready")
        response_alias = client.get("/health/ready")

    assert response_primary.status_code == 200
    assert response_alias.status_code == 200


def test_ready_endpoint_returns_503_when_dependency_report_is_not_ready() -> None:
    app = FastAPI()
    app.get("/ready")(ready_endpoint)
    app.get("/health/ready")(ready_endpoint)

    with patch(
        "backend.main.build_readiness_report",
        new=AsyncMock(return_value={"ready": False, "status": "degraded"}),
    ):
        client = TestClient(app)
        response_primary = client.get("/ready")
        response_alias = client.get("/health/ready")

    assert response_primary.status_code == 503
    assert response_alias.status_code == 503
