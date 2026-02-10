from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app


def _valid_event(event_name: str = "AuthorizeSecurityGroupIngress") -> dict:
    return {
        "id": "evt-1",
        "time": "2026-02-10T10:00:00Z",
        "source": "aws.ec2",
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {
            "eventName": event_name,
            "eventCategory": "Management",
            "requestParameters": {"groupId": "sg-123"},
        },
    }


def test_control_plane_events_503_secret_unset() -> None:
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = ""
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/events"
        client = TestClient(app)
        resp = client.post(
            "/api/internal/control-plane-events",
            json={
                "events": [
                    {
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "account_id": "123456789012",
                        "region": "us-east-1",
                        "event": _valid_event(),
                    }
                ]
            },
        )
    assert resp.status_code == 503
    assert "CONTROL_PLANE_EVENTS_SECRET" in resp.json().get("detail", "")


def test_control_plane_events_403_wrong_secret() -> None:
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/events"
        client = TestClient(app)
        resp = client.post(
            "/api/internal/control-plane-events",
            headers={"X-Control-Plane-Secret": "wrong"},
            json={
                "events": [
                    {
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "account_id": "123456789012",
                        "region": "us-east-1",
                        "event": _valid_event(),
                    }
                ]
            },
        )
    assert resp.status_code == 403


def test_control_plane_events_503_queue_unset() -> None:
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = ""
        client = TestClient(app)
        resp = client.post(
            "/api/internal/control-plane-events",
            headers={"X-Control-Plane-Secret": "secret123"},
            json={
                "events": [
                    {
                        "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                        "account_id": "123456789012",
                        "region": "us-east-1",
                        "event": _valid_event(),
                    }
                ]
            },
        )
    assert resp.status_code == 503
    assert "SQS_EVENTS_FAST_LANE_QUEUE_URL" in resp.json().get("detail", "")


def test_control_plane_events_200_enqueues_and_drops_unsupported() -> None:
    with patch("backend.routers.internal.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_EVENTS_SECRET = "secret123"
        mock_settings.SQS_EVENTS_FAST_LANE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/events"
        mock_settings.AWS_REGION = "us-east-1"

        with patch("backend.routers.internal.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs

            client = TestClient(app)
            resp = client.post(
                "/api/internal/control-plane-events",
                headers={"X-Control-Plane-Secret": "secret123"},
                json={
                    "events": [
                        {
                            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                            "account_id": "123456789012",
                            "region": "us-east-1",
                            "event": _valid_event(),
                        },
                        {
                            "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                            "account_id": "123456789012",
                            "region": "us-east-1",
                            "event": {
                                "id": "evt-2",
                                "time": "2026-02-10T10:00:00Z",
                                "source": "aws.s3",
                                "detail-type": "AWS API Call via CloudTrail",
                                "detail": {"eventName": "PutObject", "eventCategory": "Data"},
                            },
                        },
                    ]
                },
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["enqueued"] == 1
    assert body["dropped"] == 1
    assert mock_sqs.send_message.call_count == 1
