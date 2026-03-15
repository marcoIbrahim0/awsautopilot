"""Unit tests for runtime signal collection in remediation runtime checks."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from botocore.exceptions import ClientError

from backend.services.remediation_runtime_checks import collect_runtime_risk_signals


class _FakeS3Client:
    def __init__(
        self,
        *,
        policy_json: str | None = None,
        error_code: str | None = None,
        head_bucket_error_code: str | None = None,
        lifecycle_document: dict[str, Any] | None = None,
        lifecycle_error_code: str | None = None,
        policy_public: bool | None = None,
        website_error_code: str | None = "NoSuchWebsiteConfiguration",
    ) -> None:
        self._policy_json = policy_json
        self._error_code = error_code
        self._head_bucket_error_code = head_bucket_error_code
        self._lifecycle_document = lifecycle_document
        self._lifecycle_error_code = lifecycle_error_code
        self._policy_public = policy_public
        self._website_error_code = website_error_code

    def get_bucket_policy(self, *, Bucket: str) -> dict[str, Any]:
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": "simulated failure"}},
                "GetBucketPolicy",
            )
        return {"Policy": self._policy_json}

    def get_bucket_policy_status(self, *, Bucket: str) -> dict[str, Any]:
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": "simulated failure"}},
                "GetBucketPolicyStatus",
            )
        if self._policy_public is None:
            raise ClientError(
                {"Error": {"Code": "NoSuchBucketPolicy", "Message": "simulated failure"}},
                "GetBucketPolicyStatus",
            )
        return {"PolicyStatus": {"IsPublic": self._policy_public}}

    def get_bucket_lifecycle_configuration(self, *, Bucket: str) -> dict[str, Any]:
        if self._lifecycle_error_code:
            raise ClientError(
                {"Error": {"Code": self._lifecycle_error_code, "Message": "simulated failure"}},
                "GetBucketLifecycleConfiguration",
            )
        assert self._lifecycle_document is not None
        return self._lifecycle_document

    def get_bucket_website(self, *, Bucket: str) -> dict[str, Any]:
        if self._website_error_code:
            raise ClientError(
                {"Error": {"Code": self._website_error_code, "Message": "simulated failure"}},
                "GetBucketWebsite",
            )
        return {}

    def head_bucket(self, *, Bucket: str) -> dict[str, Any]:
        if self._head_bucket_error_code:
            raise ClientError(
                {"Error": {"Code": self._head_bucket_error_code, "Message": "simulated failure"}},
                "HeadBucket",
            )
        return {}


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
    def __init__(
        self,
        aliases: list[dict[str, Any]],
        *,
        describe_key_error_code: str | None = None,
        key_state: str = "Enabled",
        key_policy: str | None = None,
        key_policy_error_code: str | None = None,
        grants: list[dict[str, Any]] | None = None,
        grants_error_code: str | None = None,
    ) -> None:
        self._aliases = aliases
        self._describe_key_error_code = describe_key_error_code
        self._key_state = key_state
        self._key_policy = key_policy
        self._key_policy_error_code = key_policy_error_code
        self._grants = grants or []
        self._grants_error_code = grants_error_code

    def list_aliases(self, **kwargs) -> dict[str, Any]:
        return {"Aliases": self._aliases, "Truncated": False}

    def describe_key(self, *, KeyId: str) -> dict[str, Any]:
        if self._describe_key_error_code:
            raise ClientError(
                {"Error": {"Code": self._describe_key_error_code, "Message": "simulated failure"}},
                "DescribeKey",
            )
        return {"KeyMetadata": {"KeyState": self._key_state}}

    def get_key_policy(self, *, KeyId: str, PolicyName: str) -> dict[str, Any]:
        if self._key_policy_error_code:
            raise ClientError(
                {"Error": {"Code": self._key_policy_error_code, "Message": "simulated failure"}},
                "GetKeyPolicy",
            )
        return {"Policy": self._key_policy or ""}

    def list_grants(self, **kwargs) -> dict[str, Any]:
        if self._grants_error_code:
            raise ClientError(
                {"Error": {"Code": self._grants_error_code, "Message": "simulated failure"}},
                "ListGrants",
            )
        return {"Grants": self._grants, "Truncated": False}


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


def _s3_9_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enable_access_logging_guided"}


def _s3_kms_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enable_sse_kms_guided"}


def _config_strategy() -> dict[str, Any]:
    return {"strategy_id": "config_enable_centralized_delivery"}


def _cloudtrail_strategy() -> dict[str, Any]:
    return {"strategy_id": "cloudtrail_enable_guided"}


def _s3_11_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enable_abort_incomplete_uploads"}


def _s3_2_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_bucket_block_public_access_standard"}


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


def test_collect_runtime_risk_signals_s3_2_captures_private_bucket_and_disabled_website(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(policy_public=False, website_error_code="NoSuchWebsiteConfiguration"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action()
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy=_s3_2_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_bucket_policy_public"] is False
    assert signals["s3_bucket_website_configured"] is False
    assert signals["access_path_evidence_available"] is True
    assert signals["evidence"]["target_bucket"] == "safe-bucket"


def test_collect_runtime_risk_signals_s3_11_captures_existing_lifecycle_document(monkeypatch) -> None:
    lifecycle_document = {
        "Rules": [
            {
                "ID": "AbortMultipartUploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        ]
    }
    session = _FakeSession(_FakeS3Client(lifecycle_document=lifecycle_document))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="s3_bucket_lifecycle_configuration"),
        strategy=_s3_11_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    evidence = signals["evidence"]
    assert signals["s3_lifecycle_analysis_possible"] is True
    assert evidence["existing_lifecycle_rule_count"] == 1
    parsed_lifecycle = json.loads(evidence["existing_lifecycle_configuration_json"])
    assert parsed_lifecycle["Rules"][0]["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] == 7


def test_collect_runtime_risk_signals_s3_11_sets_zero_rule_count_when_no_lifecycle_configuration(
    monkeypatch,
) -> None:
    session = _FakeSession(_FakeS3Client(lifecycle_error_code="NoSuchLifecycleConfiguration"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="s3_bucket_lifecycle_configuration"),
        strategy=_s3_11_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_lifecycle_analysis_possible"] is True
    assert signals["evidence"]["existing_lifecycle_rule_count"] == 0
    assert "existing_lifecycle_configuration_json" not in signals["evidence"]


def test_collect_runtime_risk_signals_s3_11_access_denied_marks_lifecycle_path_unavailable(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(lifecycle_error_code="AccessDenied"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="s3_bucket_lifecycle_configuration"),
        strategy=_s3_11_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_lifecycle_analysis_possible"] is False
    assert signals["s3_lifecycle_analysis_error"] == "AccessDenied"
    assert signals["evidence"]["existing_lifecycle_capture_error"] == "AccessDenied"


def test_collect_runtime_risk_signals_s3_9_proves_destination_safety(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client())
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9",
            action_type="s3_bucket_access_logging",
        ),
        strategy=_s3_9_strategy(),
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_bucket_reachable"] is True
    assert signals["s3_access_logging_destination_safe"] is True
    assert signals["evidence"]["target_bucket"] == "source-bucket"
    assert signals["evidence"]["log_bucket_name"] == "dedicated-access-log-bucket"


def test_collect_runtime_risk_signals_s3_9_marks_destination_unsafe_when_probe_fails(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(head_bucket_error_code="AccessDenied"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9",
            action_type="s3_bucket_access_logging",
        ),
        strategy=_s3_9_strategy(),
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_bucket_reachable"] is False
    assert signals["s3_access_logging_destination_safe"] is False
    assert "AccessDenied" in signals["s3_access_logging_destination_safety_reason"]


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


def test_collect_runtime_risk_signals_s3_kms_custom_key_captures_dependency_proof(monkeypatch) -> None:
    session = _FakeSession(
        {
            "kms": _FakeKmsClient(
                aliases=[],
                key_policy='{"Version":"2012-10-17","Statement":[]}',
                grants=[{"GrantId": "grant-1"}],
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
        strategy_inputs={
            "kms_key_mode": "custom",
            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
        },
        account=_make_account(),
    )

    assert signals["s3_customer_kms_key_valid"] is True
    assert signals["s3_customer_kms_dependency_proven"] is True
    assert signals["evidence"]["customer_kms_grant_count"] == 1
    assert signals["evidence"]["customer_kms_policy_json"].startswith('{"Version"')


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
    assert signals["cloudtrail_existing_trail_present"] is True
    assert signals["cloudtrail_existing_trail_name"] == "existing-trail"
    assert signals["cloudtrail_existing_trail_multi_region"] is False
    assert signals["evidence"]["cloudtrail_existing_trail_name"] == "existing-trail"


def test_collect_runtime_risk_signals_cloudtrail_marks_absent_trail_when_none_exist(monkeypatch) -> None:
    class _NoTrailCloudTrailClient:
        def describe_trails(self, **kwargs) -> dict[str, Any]:
            return {"trailList": []}

    session = _FakeSession({"cloudtrail": _NoTrailCloudTrailClient()})
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
    assert default_inputs["trail_name"] == "security-autopilot-trail"
    assert default_inputs["create_bucket_policy"] is True
    assert default_inputs["multi_region"] is True
    assert signals["cloudtrail_existing_trail_present"] is False


def test_collect_runtime_risk_signals_cloudtrail_validates_log_bucket_reachability(monkeypatch) -> None:
    session = _FakeSession(
        {
            "cloudtrail": _FakeCloudTrailClient(trail_name="existing-trail", multi_region=True),
            "s3": _FakeS3Client(),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="cloudtrail_enabled"),
        strategy=_cloudtrail_strategy(),
        strategy_inputs={"trail_bucket_name": "tenant-cloudtrail-logs"},
        account=_make_account(),
    )

    assert signals["cloudtrail_log_bucket_reachable"] is True
    assert signals["evidence"]["trail_bucket_name"] == "tenant-cloudtrail-logs"


def test_collect_runtime_risk_signals_cloudtrail_surfaces_log_bucket_probe_failure(monkeypatch) -> None:
    session = _FakeSession(
        {
            "cloudtrail": _FakeCloudTrailClient(trail_name="existing-trail", multi_region=True),
            "s3": _FakeS3Client(head_bucket_error_code="AccessDenied"),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="cloudtrail_enabled"),
        strategy=_cloudtrail_strategy(),
        strategy_inputs={"trail_bucket_name": "tenant-cloudtrail-logs"},
        account=_make_account(),
    )

    assert signals["cloudtrail_log_bucket_reachable"] is False
    assert signals["cloudtrail_log_bucket_error"] == (
        "CloudTrail log bucket 'tenant-cloudtrail-logs' could not be verified from this account context (AccessDenied)."
    )
