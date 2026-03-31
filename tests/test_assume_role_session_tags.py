from __future__ import annotations

from unittest.mock import MagicMock, patch
from unittest.mock import PropertyMock

from backend.services.aws import assume_role, settings

TEST_AWS_ACCESS_KEY_ID = "AKIA" + "IOSFODNN7EXAMPLE"


def _credentials_response() -> dict:
    return {
        "Credentials": {
            "AccessKeyId": TEST_AWS_ACCESS_KEY_ID,
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


def test_assume_role_can_reuse_ambient_target_account_session_when_opted_in() -> None:
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:iam::123456789012:user/local-operator",
        "Account": "123456789012",
    }

    with (
        patch("boto3.client", return_value=mock_sts),
        patch("boto3.Session") as mock_session,
        patch.object(settings, "ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION", True, create=True),
    ):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            source_identity="security-autopilot-api",
            tags=[{"Key": "TenantId", "Value": "tenant-123"}],
        )

    mock_sts.assume_role.assert_not_called()
    mock_session.assert_called_once_with(region_name=settings.AWS_REGION)


def test_assume_role_does_not_reuse_ambient_session_for_different_account() -> None:
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:iam::999999999999:user/local-operator",
        "Account": "999999999999",
    }
    mock_sts.assume_role.return_value = _credentials_response()

    with (
        patch("boto3.client", return_value=mock_sts),
        patch("boto3.Session"),
        patch.object(settings, "ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION", True, create=True),
    ):
        assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            source_identity="security-autopilot-api",
        )

    assert mock_sts.assume_role.call_args.kwargs["RoleArn"] == "arn:aws:iam::123456789012:role/TestRole"


def test_assume_role_can_use_configured_local_target_account_profile() -> None:
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:iam::029037611564:user/local-operator",
        "Account": "029037611564",
    }
    mock_profile_session = MagicMock()
    mock_profile_sts = MagicMock()
    mock_profile_sts.get_caller_identity.return_value = {
        "Arn": "arn:aws:iam::123456789012:root",
        "Account": "123456789012",
    }
    mock_profile_session.client.return_value = mock_profile_sts

    with (
        patch("boto3.client", return_value=mock_sts),
        patch("boto3.Session", return_value=mock_profile_session) as mock_boto_session,
        patch.object(settings, "ALLOW_LOCAL_TARGET_ACCOUNT_AMBIENT_SESSION", True, create=True),
        patch.object(settings, "LOCAL_TARGET_ACCOUNT_AWS_PROFILE", "test28-root", create=True),
    ):
        session = assume_role(
            role_arn="arn:aws:iam::123456789012:role/TestRole",
            external_id="ext-123",
            source_identity="security-autopilot-api",
        )

    assert session is mock_profile_session
    mock_sts.assume_role.assert_not_called()
    mock_boto_session.assert_called_once_with(profile_name="test28-root", region_name=settings.AWS_REGION)
