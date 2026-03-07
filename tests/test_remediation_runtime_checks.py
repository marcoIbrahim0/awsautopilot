"""Unit tests for runtime signal collection in remediation runtime checks."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from botocore.exceptions import ClientError

from backend.services.remediation_runtime_checks import collect_runtime_risk_signals


class _FakeS3Client:
    def __init__(self, *, policy_json: str | None = None, error_code: str | None = None) -> None:
        self._policy_json = policy_json
        self._error_code = error_code

    def get_bucket_policy(self, *, Bucket: str) -> dict[str, Any]:
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": "simulated failure"}},
                "GetBucketPolicy",
            )
        return {"Policy": self._policy_json}


class _FakeSession:
    def __init__(self, clients: dict[str, Any] | _FakeS3Client) -> None:
        if isinstance(clients, dict):
            self._clients = clients
        else:
            self._clients = {"s3": clients}

    def client(self, service_name: str, **kwargs) -> Any:
        client = self._clients.get(service_name)
        assert client is not None, f"Unexpected service_name: {service_name}"
        return client


class _FakeKmsClient:
    def __init__(self, aliases: list[dict[str, Any]]) -> None:
        self._aliases = aliases

    def list_aliases(self, **kwargs) -> dict[str, Any]:
        return {"Aliases": self._aliases, "Truncated": False}


class _FakeConfigClient:
    def __init__(
        self,
        *,
        recorder_exists: bool,
        delivery_bucket: str | None,
    ) -> None:
        self._recorder_exists = recorder_exists
        self._delivery_bucket = delivery_bucket

    def describe_configuration_recorders(self) -> dict[str, Any]:
        if not self._recorder_exists:
            return {"ConfigurationRecorders": []}
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "recordingGroup": {"allSupported": True},
                }
            ]
        }

    def describe_delivery_channels(self) -> dict[str, Any]:
        if not self._delivery_bucket:
            return {"DeliveryChannels": []}
        return {"DeliveryChannels": [{"s3BucketName": self._delivery_bucket}]}


class _FakeCloudTrailClient:
    def __init__(self, *, trail_name: str, multi_region: bool) -> None:
        self._trail_name = trail_name
        self._multi_region = multi_region

    def describe_trails(self, **kwargs) -> dict[str, Any]:
        return {
            "trailList": [
                {
                    "Name": self._trail_name,
                    "IsMultiRegionTrail": self._multi_region,
                }
            ]
        }


def _make_action(
    target_id: str = "my-bucket",
    *,
    action_type: str = "s3_bucket_require_ssl",
    region: str = "us-east-1",
    account_id: str = "123456789012",
) -> SimpleNamespace:
    return SimpleNamespace(
        action_type=action_type,
        target_id=target_id,
        region=region,
        account_id=account_id,
    )


def _make_account() -> SimpleNamespace:
    return SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="tenant-ext-id",
        account_id="123456789012",
    )


def _strict_ssl_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enforce_ssl_strict_deny"}


def _s3_kms_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_bucket_encryption_kms"}


def _config_strategy() -> dict[str, Any]:
    return {"strategy_id": "config_enable_centralized_delivery"}


def _cloudtrail_strategy() -> dict[str, Any]:
    return {"strategy_id": "cloudtrail_enable_guided"}


def test_collect_runtime_risk_signals_s35_captures_existing_bucket_policy(monkeypatch) -> None:
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Sid": "AllowRead", "Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"},
            {"Sid": "DenyDelete", "Effect": "Deny", "Principal": "*", "Action": "s3:DeleteObject"},
        ],
    }
    session = _FakeSession(_FakeS3Client(policy_json=json.dumps(existing_policy)))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(),
        strategy=_strict_ssl_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_statement_count"] == 2
    parsed_policy = json.loads(evidence["existing_bucket_policy_json"])
    assert len(parsed_policy["Statement"]) == 2
    assert signals["s3_policy_analysis_possible"] is True


def test_collect_runtime_risk_signals_s35_sets_zero_count_when_no_bucket_policy(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(error_code="NoSuchBucketPolicy"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(),
        strategy=_strict_ssl_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_statement_count"] == 0
    assert "existing_bucket_policy_json" not in evidence
    assert signals["s3_policy_analysis_possible"] is True


def test_collect_runtime_risk_signals_s35_access_denied_marks_policy_path_unavailable(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(error_code="AccessDenied"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(),
        strategy=_strict_ssl_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_policy_analysis_possible"] is False
    assert signals["access_path_evidence_available"] is False
    assert signals["evidence"]["existing_bucket_policy_capture_error"] == "AccessDenied"
    assert "Unable to inspect current bucket policy (AccessDenied)." in signals["access_path_evidence_reason"]


def test_collect_runtime_risk_signals_s3_kms_exposes_kms_key_options_context(monkeypatch) -> None:
    session = _FakeSession(
        {
            "kms": _FakeKmsClient(
                aliases=[
                    {
                        "AliasName": "alias/aws/s3",
                        "AliasArn": "arn:aws:kms:us-east-1:123456789012:alias/aws/s3",
                        "TargetKeyId": "11111111-2222-3333-4444-555555555555",
                    },
                    {
                        "AliasName": "alias/security-autopilot",
                        "AliasArn": "arn:aws:kms:us-east-1:123456789012:alias/security-autopilot",
                        "TargetKeyId": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    },
                ]
            )
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="s3_bucket_encryption_kms"),
        strategy=_s3_kms_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    context = signals["context"]
    assert isinstance(context.get("kms_key_options"), list)
    assert context["kms_key_options"][0]["value"] == "arn:aws:kms:us-east-1:123456789012:alias/aws/s3"
    assert context["kms_key_options"][1]["value"] == "arn:aws:kms:us-east-1:123456789012:alias/security-autopilot"


def test_collect_runtime_risk_signals_config_sets_contextual_default_inputs(monkeypatch) -> None:
    session = _FakeSession(
        {
            "config": _FakeConfigClient(recorder_exists=True, delivery_bucket="existing-config-bucket"),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="aws_config_enabled"),
        strategy=_config_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    default_inputs = signals["context"]["default_inputs"]
    assert default_inputs["recording_scope"] == "keep_existing"
    assert default_inputs["delivery_bucket_mode"] == "use_existing"
    assert default_inputs["existing_bucket_name"] == "existing-config-bucket"
    assert default_inputs["delivery_bucket"] == "existing-config-bucket"


def test_collect_runtime_risk_signals_cloudtrail_sets_contextual_default_inputs(monkeypatch) -> None:
    session = _FakeSession(
        {
            "cloudtrail": _FakeCloudTrailClient(trail_name="existing-trail", multi_region=False),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="cloudtrail_enabled"),
        strategy=_cloudtrail_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    default_inputs = signals["context"]["default_inputs"]
    assert default_inputs["trail_name"] == "existing-trail"
    assert default_inputs["create_bucket_policy"] is True
    assert default_inputs["multi_region"] is False
