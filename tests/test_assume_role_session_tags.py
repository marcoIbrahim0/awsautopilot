from __future__ import annotations

from unittest.mock import MagicMock, patch
from unittest.mock import PropertyMock

from backend.services.aws import assume_role, settings


def _credentials_response() -> dict:
    return {
        "Credentials": {
            "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": "2026-01-30T12:00:00Z",
        }
    }


def test_assume_role_passes_source_identity_when_provided() -> None:
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _credentials_response()

    with patch("boto3.client", return_value=mock_sts), patch("boto3.Session"):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            source_identity="security-autopilot-api",
        )

    assert mock_sts.assume_role.call_args.kwargs["SourceIdentity"] == "security-autopilot-api"


def test_assume_role_passes_tags_when_provided() -> None:
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _credentials_response()
    tags = [
        {"Key": "ServiceComponent", "Value": "api"},
        {"Key": "TenantId", "Value": "tenant-123"},
    ]

    with patch("boto3.client", return_value=mock_sts), patch("boto3.Session"):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            tags=tags,
        )

    assert mock_sts.assume_role.call_args.kwargs["Tags"] == tags


def test_assume_role_omits_source_identity_when_none() -> None:
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _credentials_response()

    with patch("boto3.client", return_value=mock_sts), patch("boto3.Session"):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
        )

    assert "SourceIdentity" not in mock_sts.assume_role.call_args.kwargs


def test_assume_role_omits_tags_when_none() -> None:
    mock_sts = MagicMock()
    mock_sts.assume_role.return_value = _credentials_response()

    with patch("boto3.client", return_value=mock_sts), patch("boto3.Session"):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
        )

    assert "Tags" not in mock_sts.assume_role.call_args.kwargs


def test_assume_role_uses_source_identity_as_session_name_and_omits_audit_fields_for_execution_role_sessions() -> None:
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": (
            "arn:aws:sts::029037611564:assumed-role/"
            "security-autopilot-dev-lambda-api/security-autopilot-dev-api"
        )
    }
    mock_sts.assume_role.return_value = _credentials_response()
    tags = [
        {"Key": "ServiceComponent", "Value": "api"},
        {"Key": "TenantId", "Value": "tenant-123"},
    ]

    with (
        patch("boto3.client", return_value=mock_sts),
        patch("boto3.Session"),
        patch(
            "backend.services.aws.settings.AWS_REGION",
            "eu-north-1",
        ),
        patch.object(
            type(settings),
            "saas_execution_role_arns_list",
            new_callable=PropertyMock,
            return_value=["arn:aws:iam::029037611564:role/security-autopilot-dev-lambda-api"],
        ),
    ):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            session_name="security-autopilot-session",
            source_identity="security-autopilot-api",
            tags=tags,
        )

    assert mock_sts.assume_role.call_args.kwargs["RoleArn"] == "arn:aws:iam::123456789012:role/TestRole"
    assert mock_sts.assume_role.call_args.kwargs["RoleSessionName"] == "security-autopilot-api"
    assert "SourceIdentity" not in mock_sts.assume_role.call_args.kwargs
    assert "Tags" not in mock_sts.assume_role.call_args.kwargs
