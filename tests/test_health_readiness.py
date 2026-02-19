from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import ready as ready_endpoint
from backend.services import health_checks


def test_build_readiness_report_ready_when_db_and_sqs_are_healthy() -> None:
    queue_urls = {
        "ingest": "https://sqs.us-east-1.amazonaws.com/123/ingest",
        "events_fast_lane": "https://sqs.us-east-1.amazonaws.com/123/events",
        "inventory_reconcile": "https://sqs.us-east-1.amazonaws.com/123/inventory",
        "export_report": "https://sqs.us-east-1.amazonaws.com/123/export",
    }

    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.side_effect = [
        {"Attributes": {"QueueArn": "arn:1", "ApproximateNumberOfMessages": "0", "ApproximateNumberOfMessagesNotVisible": "1", "ApproximateAgeOfOldestMessage": "4"}},
        {"Attributes": {"QueueArn": "arn:2", "ApproximateNumberOfMessages": "2", "ApproximateNumberOfMessagesNotVisible": "0", "ApproximateAgeOfOldestMessage": "8"}},
        {"Attributes": {"QueueArn": "arn:3", "ApproximateNumberOfMessages": "1", "ApproximateNumberOfMessagesNotVisible": "0", "ApproximateAgeOfOldestMessage": "12"}},
        {"Attributes": {"QueueArn": "arn:4", "ApproximateNumberOfMessages": "0", "ApproximateNumberOfMessagesNotVisible": "0", "ApproximateAgeOfOldestMessage": "20"}},
    ]

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=True)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch("backend.services.health_checks.boto3.client", return_value=sqs_client):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is True
    assert report["status"] == "ok"
    assert report["dependencies"]["database"]["ready"] is True
    assert report["dependencies"]["sqs"]["ready"] is True
    assert report["slo"]["queue_lag_seconds_max"] == 20.0
    assert report["slo"]["queue_lag_seconds_p95"] == 20.0


def test_build_readiness_report_fails_when_required_queue_missing() -> None:
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


def test_build_readiness_report_fails_when_database_ping_fails() -> None:
    queue_urls = {
        "ingest": "https://sqs.us-east-1.amazonaws.com/123/ingest",
        "events_fast_lane": "https://sqs.us-east-1.amazonaws.com/123/events",
        "inventory_reconcile": "https://sqs.us-east-1.amazonaws.com/123/inventory",
        "export_report": "https://sqs.us-east-1.amazonaws.com/123/export",
    }
    sqs_client = MagicMock()
    sqs_client.get_queue_attributes.return_value = {
        "Attributes": {
            "QueueArn": "arn:ok",
            "ApproximateNumberOfMessages": "0",
            "ApproximateNumberOfMessagesNotVisible": "0",
            "ApproximateAgeOfOldestMessage": "0",
        }
    }

    with patch("backend.services.health_checks.ping_db", new=AsyncMock(return_value=False)):
        with patch("backend.services.health_checks.required_sqs_queue_urls", return_value=(queue_urls, [])):
            with patch("backend.services.health_checks.boto3.client", return_value=sqs_client):
                report = asyncio.run(health_checks.build_readiness_report())

    assert report["ready"] is False
    assert report["dependencies"]["database"]["ready"] is False
    assert report["dependencies"]["sqs"]["ready"] is True


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
