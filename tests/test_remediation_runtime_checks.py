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
        policy_status_error_code: str | None = None,
        head_bucket_error_code: str | None = None,
        lifecycle_document: dict[str, Any] | None = None,
        lifecycle_error_code: str | None = None,
        policy_public: bool | None = None,
        website_error_code: str | None = "NoSuchWebsiteConfiguration",
        website_document: dict[str, Any] | None = None,
        public_access_block_error_code: str | None = None,
        encryption_error_code: str | None = None,
        versioning_status: str = "Enabled",
    ) -> None:
        self._policy_json = policy_json
        self._error_code = error_code
        self._policy_status_error_code = policy_status_error_code
        self._head_bucket_error_code = head_bucket_error_code
        self._lifecycle_document = lifecycle_document
        self._lifecycle_error_code = lifecycle_error_code
        self._policy_public = policy_public
        self._website_error_code = website_error_code
        self._website_document = website_document
        self._public_access_block_error_code = public_access_block_error_code
        self._encryption_error_code = encryption_error_code
        self._versioning_status = versioning_status

    def get_bucket_policy(self, *, Bucket: str) -> dict[str, Any]:
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": "simulated failure"}},
                "GetBucketPolicy",
            )
        policy = self._policy_json
        if policy is None:
            policy = json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "DenyInsecureTransport",
                            "Effect": "Deny",
                            "Principal": "*",
                            "Action": "s3:*",
                            "Resource": [
                                f"arn:aws:s3:::{Bucket}",
                                f"arn:aws:s3:::{Bucket}/*",
                            ],
                            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                        }
                    ],
                }
            )
        return {"Policy": policy}

    def get_bucket_policy_status(self, *, Bucket: str) -> dict[str, Any]:
        if self._policy_status_error_code:
            raise ClientError(
                {"Error": {"Code": self._policy_status_error_code, "Message": "simulated failure"}},
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
        if self._lifecycle_document is not None:
            return self._lifecycle_document
        return {
            "Rules": [
                {
                    "ID": "abort-incomplete-multipart",
                    "Status": "Enabled",
                    "Filter": {},
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
                }
            ]
        }

    def get_bucket_website(self, *, Bucket: str) -> dict[str, Any]:
        if self._website_error_code:
            raise ClientError(
                {"Error": {"Code": self._website_error_code, "Message": "simulated failure"}},
                "GetBucketWebsite",
            )
        return self._website_document or {}

    def head_bucket(self, *, Bucket: str) -> dict[str, Any]:
        if self._head_bucket_error_code:
            raise ClientError(
                {"Error": {"Code": self._head_bucket_error_code, "Message": "simulated failure"}},
                "HeadBucket",
            )
        return {}

    def get_public_access_block(self, *, Bucket: str) -> dict[str, Any]:
        if self._public_access_block_error_code:
            raise ClientError(
                {"Error": {"Code": self._public_access_block_error_code, "Message": "simulated failure"}},
                "GetPublicAccessBlock",
            )
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_encryption(self, *, Bucket: str) -> dict[str, Any]:
        if self._encryption_error_code:
            raise ClientError(
                {"Error": {"Code": self._encryption_error_code, "Message": "simulated failure"}},
                "GetBucketEncryption",
            )
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "aws:kms",
                            "KMSMasterKeyID": "alias/aws/s3",
                        }
                    }
                ]
            }
        }

    def get_bucket_versioning(self, *, Bucket: str) -> dict[str, Any]:
        return {"Status": self._versioning_status}


class _BucketAwareFakeS3Client(_FakeS3Client):
    def __init__(
        self,
        *,
        head_bucket_error_codes: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._head_bucket_error_codes = head_bucket_error_codes or {}

    def head_bucket(self, *, Bucket: str) -> dict[str, Any]:
        code = self._head_bucket_error_codes.get(Bucket)
        if code:
            raise ClientError(
                {"Error": {"Code": code, "Message": "simulated failure"}},
                "HeadBucket",
            )
        return super().head_bucket(Bucket=Bucket)


class _FakeSession:
    def __init__(self, clients: dict[str, Any] | _FakeS3Client) -> None:
        if isinstance(clients, dict):
            self._clients = clients
        else:
            self._clients = {"s3": clients}

    def client(self, service_name: str, **kwargs) -> Any:
        client = self._clients.get(service_name)
        if client is None and service_name == "s3control":
            client = _FakeS3ControlClient(block_public_policy=True)
            self._clients[service_name] = client
        assert client is not None, f"Unexpected service_name: {service_name}"
        return client


class _FakeS3ControlClient:
    def __init__(self, *, block_public_policy: bool | None = True, error_code: str | None = None) -> None:
        self._block_public_policy = block_public_policy
        self._error_code = error_code

    def get_public_access_block(self, *, AccountId: str) -> dict[str, Any]:
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": "simulated failure"}},
                "GetPublicAccessBlock",
            )
        if self._block_public_policy is None:
            raise ClientError(
                {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration", "Message": "simulated failure"}},
                "GetPublicAccessBlock",
            )
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicPolicy": self._block_public_policy,
            }
        }


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
    def __init__(self, *, trail_name: str, multi_region: bool, bucket_name: str | None = None) -> None:
        self._trail_name = trail_name
        self._multi_region = multi_region
        self._bucket_name = bucket_name

    def describe_trails(self, **kwargs) -> dict[str, Any]:
        return {
            "trailList": [
                {
                    "Name": self._trail_name,
                    "IsMultiRegionTrail": self._multi_region,
                    "S3BucketName": self._bucket_name,
                }
            ]
        }


def _make_action(
    target_id: str = "my-bucket",
    *,
    action_type: str = "s3_bucket_require_ssl",
    region: str = "us-east-1",
    account_id: str = "123456789012",
    resource_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        action_type=action_type,
        target_id=target_id,
        resource_id=resource_id,
        region=region,
        account_id=account_id,
    )


def _make_account() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id="tenant-1",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="tenant-ext-id",
        account_id="123456789012",
    )


def _strict_ssl_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enforce_ssl_strict_deny"}


def _snapshot_strategy() -> dict[str, Any]:
    return {"strategy_id": "snapshot_block_all_sharing"}


def _s3_9_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enable_access_logging_guided"}


def _s3_kms_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enable_sse_kms_guided"}


def _config_strategy(strategy_id: str = "config_enable_centralized_delivery") -> dict[str, Any]:
    return {"strategy_id": strategy_id}


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
    session = _FakeSession(
        _FakeS3Client(error_code="AccessDenied", policy_status_error_code="AccessDenied")
    )
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


def test_collect_runtime_risk_signals_s35_access_denied_but_status_no_such_policy_normalizes_to_zero_policy(
    monkeypatch,
) -> None:
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

    assert signals["s3_policy_analysis_possible"] is True
    assert signals["access_path_evidence_available"] is True
    assert "s3_policy_analysis_error" not in signals
    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_statement_count"] == 0
    assert evidence["s3_ssl_deny_present"] is False
    assert "existing_bucket_policy_capture_error" not in evidence
    assert "access_path_evidence_reason" not in signals


def test_collect_runtime_risk_signals_s35_captures_public_policy_and_bpa_state(monkeypatch) -> None:
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadWebsiteObjects",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::bucket/*",
            }
        ],
    }
    session = _FakeSession(
        {
            "s3": _FakeS3Client(policy_json=json.dumps(existing_policy), policy_public=True),
            "s3control": _FakeS3ControlClient(block_public_policy=True),
        }
    )
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

    assert signals["s3_bucket_policy_public"] is True
    assert signals["s3_bucket_block_public_policy_enabled"] is True
    assert signals["s3_account_block_public_policy_enabled"] is True
    assert signals["s3_effective_block_public_policy_enabled"] is True


def test_collect_runtime_risk_signals_s3_2_oac_captures_public_website_and_bpa_state(monkeypatch) -> None:
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadWebsiteObjects",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::bucket/*",
            }
        ],
    }
    session = _FakeSession(
        {
            "s3": _FakeS3Client(
                policy_json=json.dumps(existing_policy),
                policy_public=True,
                website_error_code=None,
                website_document={"IndexDocument": {"Suffix": "index.html"}},
            ),
            "s3control": _FakeS3ControlClient(block_public_policy=True),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="s3_bucket_block_public_access"),
        strategy={"strategy_id": "s3_migrate_cloudfront_oac_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_bucket_policy_public"] is True
    assert signals["s3_bucket_website_configured"] is True
    assert signals["s3_bucket_block_public_policy_enabled"] is True
    assert signals["s3_account_block_public_policy_enabled"] is True
    assert signals["s3_effective_block_public_policy_enabled"] is True
    assert signals["evidence"]["existing_bucket_policy_statement_count"] == 1
    assert "existing_bucket_website_configuration_json" in signals["evidence"]


def test_collect_runtime_risk_signals_s35_marks_missing_target_bucket(monkeypatch) -> None:
    session = _FakeSession(
        {
            "s3": _FakeS3Client(
                head_bucket_error_code="NoSuchBucket",
                error_code="NoSuchBucket",
                policy_status_error_code="NoSuchBucket",
            ),
            "s3control": _FakeS3ControlClient(block_public_policy=True),
        }
    )
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

    assert signals["s3_target_bucket_missing"] is True
    assert signals["s3_target_bucket_creation_possible"] is True
    assert signals["context"]["default_inputs"]["create_bucket_if_missing"] is True


def test_collect_runtime_risk_signals_s35_uses_resource_id_fallback_for_bucket_scope(monkeypatch) -> None:
    existing_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Sid": "AllowRead", "Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"},
        ],
    }
    session = _FakeSession(_FakeS3Client(policy_json=json.dumps(existing_policy)))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.5",
            resource_id="arn:aws:s3:::fallback-ssl-bucket",
        ),
        strategy=_strict_ssl_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_policy_analysis_possible"] is True
    assert signals["evidence"]["target_bucket"] == "fallback-ssl-bucket"


def test_collect_runtime_risk_signals_s35_without_bucket_identifiers_keeps_missing_bucket_failure(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client())
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.5",
            resource_id="AWS::::Account:123456789012",
        ),
        strategy=_strict_ssl_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_ssl_policy_generation_ok"] is False
    assert signals["s3_ssl_policy_generation_error"] == "Could not derive bucket name from action target."


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


def test_collect_runtime_risk_signals_s3_2_uses_resource_id_fallback_for_bucket_scope(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(policy_public=False, website_error_code="NoSuchWebsiteConfiguration"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.2",
            action_type="s3_bucket_block_public_access",
            resource_id="arn:aws:s3:::fallback-bpa-bucket",
        ),
        strategy=_s3_2_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_bucket_policy_public"] is False
    assert signals["s3_bucket_website_configured"] is False
    assert signals["access_path_evidence_available"] is True
    assert signals["evidence"]["target_bucket"] == "fallback-bpa-bucket"


def test_collect_runtime_risk_signals_s3_2_oac_access_denied_but_status_no_such_policy_sets_zero_count(
    monkeypatch,
) -> None:
    session = _FakeSession(
        _FakeS3Client(error_code="AccessDenied", website_error_code="NoSuchWebsiteConfiguration")
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action(action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy={"strategy_id": "s3_migrate_cloudfront_oac_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_statement_count"] == 0
    assert "existing_bucket_policy_capture_error" not in evidence
    assert "existing_bucket_policy_json" not in evidence
    assert signals["s3_bucket_policy_public"] is False


def test_collect_runtime_risk_signals_s3_2_oac_proves_bucket_when_head_bucket_is_denied_but_policy_reads_work(
    monkeypatch,
) -> None:
    session = _FakeSession(
        _FakeS3Client(
            policy_public=False,
            website_error_code="NoSuchWebsiteConfiguration",
            head_bucket_error_code="403",
        )
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action(action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy={"strategy_id": "s3_migrate_cloudfront_oac_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_target_bucket_verification_available"] is True
    assert signals["s3_target_bucket_exists"] is True
    assert signals["s3_target_bucket_missing"] is False
    assert "s3_target_bucket_verification_reason" not in signals
    assert "s3_target_bucket_reason" not in signals
    assert signals["s3_bucket_policy_public"] is False
    assert signals["s3_bucket_website_configured"] is False
    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_statement_count"] == 1
    assert isinstance(evidence["existing_bucket_policy_json"], str)


def test_collect_runtime_risk_signals_s3_2_oac_access_denied_with_status_denied_keeps_capture_error(
    monkeypatch,
) -> None:
    session = _FakeSession(
        _FakeS3Client(
            error_code="AccessDenied",
            policy_status_error_code="AccessDenied",
            website_error_code="NoSuchWebsiteConfiguration",
        )
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action(action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy={"strategy_id": "s3_migrate_cloudfront_oac_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    evidence = signals["evidence"]
    assert evidence["existing_bucket_policy_capture_error"] == "AccessDenied"
    assert "existing_bucket_policy_statement_count" not in evidence
    assert signals["access_path_evidence_available"] is False
    assert "Unable to inspect bucket policy status (AccessDenied)." in signals["access_path_evidence_reason"]


def test_collect_runtime_risk_signals_s3_2_website_strategy_captures_simple_website_configuration(
    monkeypatch,
) -> None:
    website_document = {
        "IndexDocument": {"Suffix": "index.html"},
        "ErrorDocument": {"Key": "error.html"},
    }
    session = _FakeSession(
        _FakeS3Client(
            policy_public=True,
            website_error_code=None,
            website_document=website_document,
            error_code="NoSuchBucketPolicy",
        )
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action(action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::website-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::website-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy={"strategy_id": "s3_migrate_website_cloudfront_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_bucket_website_configured"] is True
    assert signals["s3_bucket_website_translation_supported"] is True
    assert "s3_bucket_website_translation_reason" not in signals
    assert signals["evidence"]["existing_bucket_website_configuration_json"] == json.dumps(
        website_document,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_collect_runtime_risk_signals_s3_2_website_strategy_marks_routing_rules_review_only(
    monkeypatch,
) -> None:
    website_document = {
        "IndexDocument": {"Suffix": "index.html"},
        "RoutingRules": [{"Condition": {"KeyPrefixEquals": "docs/"}, "Redirect": {"ReplaceKeyPrefixWith": "kb/"}}],
    }
    session = _FakeSession(
        _FakeS3Client(
            policy_public=True,
            website_error_code=None,
            website_document=website_document,
            error_code="NoSuchBucketPolicy",
        )
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    action = _make_action(action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::website-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::website-bucket"
    signals = collect_runtime_risk_signals(
        action=action,
        strategy={"strategy_id": "s3_migrate_website_cloudfront_private"},
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_bucket_website_configured"] is True
    assert signals["s3_bucket_website_translation_supported"] is False
    assert "RoutingRules" in signals["s3_bucket_website_translation_reason"]


def test_collect_runtime_risk_signals_snapshot_does_not_mark_access_path_unavailable(monkeypatch) -> None:
    def _raise_access_denied(**kwargs):
        raise RuntimeError("Access denied")

    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        _raise_access_denied,
    )

    action = _make_action(
        target_id="123456789012|us-east-1|arn:aws:ec2:us-east-1:123456789012:snapshot/snap-12345678|EC2.182",
        action_type="ebs_snapshot_block_public_access",
    )
    signals = collect_runtime_risk_signals(
        action=action,
        strategy=_snapshot_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert "access_path_evidence_available" not in signals


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


def test_collect_runtime_risk_signals_s3_11_missing_target_bucket_sets_create_defaults(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(head_bucket_error_code="404"))
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::missing-lifecycle-bucket|S3.11",
            action_type="s3_bucket_lifecycle_configuration",
            resource_id="arn:aws:s3:::missing-lifecycle-bucket",
        ),
        strategy=_s3_11_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_target_bucket_exists"] is False
    assert signals["s3_target_bucket_missing"] is True
    assert signals["s3_target_bucket_creation_possible"] is True
    assert "missing-lifecycle-bucket" in signals["s3_target_bucket_reason"]
    assert signals["context"]["default_inputs"]["create_bucket_if_missing"] is True
    assert signals["s3_target_bucket_name"] == "missing-lifecycle-bucket"


def test_collect_runtime_risk_signals_s3_15_marks_target_bucket_unverified_when_read_probe_is_unavailable(
    monkeypatch,
) -> None:
    def _raise_access_denied(**kwargs):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "Access denied. Check role ARN and trust policy.",
                }
            },
            "AssumeRole",
        )

    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        _raise_access_denied,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::missing-kms-bucket|S3.15",
            action_type="s3_bucket_encryption_kms",
            resource_id="arn:aws:s3:::missing-kms-bucket",
        ),
        strategy=_s3_kms_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_target_bucket_probe_error"] == (
        "Target bucket existence could not be verified because ReadRole runtime probe is unavailable."
    )
    assert signals["s3_target_bucket_verification_available"] is False
    assert signals["s3_target_bucket_creation_possible"] is False
    assert "missing-kms-bucket" in signals["s3_target_bucket_verification_reason"]
    assert "existing-bucket remediation path executable" in signals["s3_target_bucket_verification_reason"]
    assert signals["s3_target_bucket_reason"] == signals["s3_target_bucket_verification_reason"]
    default_inputs = signals.get("context", {}).get("default_inputs", {})
    assert "create_bucket_if_missing" not in default_inputs


def test_collect_runtime_risk_signals_s3_11_uses_resource_id_fallback_for_bucket_scope(monkeypatch) -> None:
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
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.11",
            action_type="s3_bucket_lifecycle_configuration",
            resource_id="arn:aws:s3:::fallback-lifecycle-bucket",
        ),
        strategy=_s3_11_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_lifecycle_analysis_possible"] is True
    assert signals["evidence"]["target_bucket"] == "fallback-lifecycle-bucket"
    assert signals["evidence"]["existing_lifecycle_rule_count"] == 1


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
    assert signals["support_bucket_probe"]["safe"] is True
    assert signals["evidence"]["target_bucket"] == "source-bucket"
    assert signals["evidence"]["log_bucket_name"] == "dedicated-access-log-bucket"


def test_collect_runtime_risk_signals_s3_9_missing_source_bucket_sets_create_defaults(monkeypatch) -> None:
    session = _FakeSession(
        _BucketAwareFakeS3Client(head_bucket_error_codes={"source-bucket": "404"})
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9",
            action_type="s3_bucket_access_logging",
            resource_id="arn:aws:s3:::source-bucket",
        ),
        strategy=_s3_9_strategy(),
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        account=_make_account(),
    )

    assert signals["s3_target_bucket_exists"] is False
    assert signals["s3_target_bucket_missing"] is True
    assert signals["s3_target_bucket_creation_possible"] is True
    assert signals["context"]["default_inputs"]["create_bucket_if_missing"] is True
    assert signals["s3_access_logging_destination_safe"] is True
    assert signals["s3_access_logging_destination_bucket_reachable"] is True
    assert signals["evidence"]["target_bucket"] == "source-bucket"
    assert signals["evidence"]["log_bucket_name"] == "dedicated-access-log-bucket"


def test_collect_runtime_risk_signals_s3_9_auto_generates_log_bucket_name(monkeypatch) -> None:
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
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_bucket_reachable"] is True
    assert signals["s3_access_logging_destination_safe"] is True
    assert signals["evidence"]["log_bucket_name"] == "source-bucket-access-logs"
    assert signals["evidence"]["log_bucket_name_auto_generated"] is True


def test_collect_runtime_risk_signals_s3_9_uses_resource_id_fallback_for_source_bucket(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client())
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.9",
            action_type="s3_bucket_access_logging",
            resource_id="arn:aws:s3:::fallback-source-bucket",
        ),
        strategy=_s3_9_strategy(),
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_bucket_reachable"] is True
    assert signals["s3_access_logging_destination_safe"] is True
    assert signals["evidence"]["target_bucket"] == "fallback-source-bucket"
    assert signals["evidence"]["log_bucket_name"] == "dedicated-access-log-bucket"


def test_collect_runtime_risk_signals_s3_9_auto_generated_destination_marks_managed_creation(
    monkeypatch,
) -> None:
    session = _FakeSession(_FakeS3Client(head_bucket_error_code="404"))
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
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_creation_planned"] is True
    assert signals["evidence"]["log_bucket_name"] == "source-bucket-access-logs"
    assert signals["evidence"]["log_bucket_name_auto_generated"] is True


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


def test_collect_runtime_risk_signals_s3_9_without_bucket_scope_or_input_fails_closed(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client())
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|AWS::::Account:123456789012|S3.9",
            action_type="s3_bucket_access_logging",
            resource_id="",
        ),
        strategy=_s3_9_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_access_logging_destination_safe"] is False
    assert signals["s3_access_logging_destination_safety_reason"] == (
        "Destination log bucket could not be resolved for S3 access logging."
    )
    assert "evidence" not in signals or "log_bucket_name" not in signals["evidence"]


def test_collect_runtime_risk_signals_s3_9_marks_absent_destination_for_managed_creation(monkeypatch) -> None:
    session = _FakeSession(_FakeS3Client(head_bucket_error_code="404"))
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
    assert signals["s3_access_logging_destination_safe"] is True
    assert signals["s3_access_logging_destination_creation_planned"] is True
    assert signals["helper_bucket_creation_planned"] is True
    assert signals["support_bucket_probe"]["safe"] is True


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
            ),
            "s3": _FakeS3Client(),
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


def test_collect_runtime_risk_signals_s3_kms_missing_target_bucket_sets_create_defaults(monkeypatch) -> None:
    session = _FakeSession(
        {
            "kms": _FakeKmsClient(aliases=[]),
            "s3": _FakeS3Client(head_bucket_error_code="404"),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(
            target_id="123456789012|us-east-1|arn:aws:s3:::missing-kms-bucket|S3.15",
            action_type="s3_bucket_encryption_kms",
            resource_id="arn:aws:s3:::missing-kms-bucket",
        ),
        strategy=_s3_kms_strategy(),
        strategy_inputs={},
        account=_make_account(),
    )

    assert signals["s3_target_bucket_exists"] is False
    assert signals["s3_target_bucket_missing"] is True
    assert signals["s3_target_bucket_creation_possible"] is True
    assert signals["context"]["default_inputs"]["create_bucket_if_missing"] is True
    assert signals["s3_target_bucket_name"] == "missing-kms-bucket"


def test_collect_runtime_risk_signals_s3_kms_custom_key_captures_dependency_proof(monkeypatch) -> None:
    session = _FakeSession(
        {
            "kms": _FakeKmsClient(
                aliases=[],
                key_policy='{"Version":"2012-10-17","Statement":[]}',
                grants=[{"GrantId": "grant-1"}],
            ),
            "s3": _FakeS3Client(),
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
            "s3": _FakeS3Client(),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="aws_config_enabled"),
        strategy=_config_strategy("config_enable_account_local_delivery"),
        strategy_inputs={},
        account=_make_account(),
    )

    default_inputs = signals["context"]["default_inputs"]
    assert default_inputs["recording_scope"] == "keep_existing"
    assert default_inputs["delivery_bucket"] == "security-autopilot-config-123456789012-us-east-1"
    assert default_inputs["delivery_bucket_mode"] == "create_new"
    assert "existing_bucket_name" not in default_inputs
    assert signals["config_delivery_bucket_reachable"] is True


def test_collect_runtime_risk_signals_config_centralized_prefers_reachable_existing_bucket(monkeypatch) -> None:
    session = _FakeSession(
        {
            "config": _FakeConfigClient(recorder_exists=True, delivery_bucket="existing-config-bucket"),
            "s3": _FakeS3Client(),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="aws_config_enabled"),
        strategy=_config_strategy(strategy_id="config_enable_centralized_delivery"),
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
            "cloudtrail": _FakeCloudTrailClient(
                trail_name="existing-trail",
                multi_region=False,
                bucket_name="existing-cloudtrail-logs",
            ),
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
        strategy_inputs={},
        account=_make_account(),
    )

    default_inputs = signals["context"]["default_inputs"]
    assert default_inputs["trail_name"] == "existing-trail"
    assert default_inputs["trail_bucket_name"] == "existing-cloudtrail-logs"
    assert default_inputs["create_bucket_if_missing"] is False
    assert default_inputs["create_bucket_policy"] is True
    assert default_inputs["multi_region"] is False
    assert signals["cloudtrail_existing_trail_present"] is True
    assert signals["cloudtrail_existing_trail_name"] == "existing-trail"
    assert signals["cloudtrail_existing_trail_multi_region"] is False
    assert signals["cloudtrail_resolved_bucket_source"] == "existing_trail"
    assert signals["support_bucket_probe"]["safe"] is True
    assert signals["evidence"]["cloudtrail_existing_trail_name"] == "existing-trail"
    assert signals["evidence"]["cloudtrail_existing_trail_bucket_name"] == "existing-cloudtrail-logs"


def test_collect_runtime_risk_signals_cloudtrail_marks_absent_trail_when_none_exist(monkeypatch) -> None:
    class _NoTrailCloudTrailClient:
        def describe_trails(self, **kwargs) -> dict[str, Any]:
            return {"trailList": []}

    session = _FakeSession(
        {
            "cloudtrail": _NoTrailCloudTrailClient(),
            "s3": _FakeS3Client(head_bucket_error_code="404"),
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
    assert default_inputs["trail_name"] == "security-autopilot-trail"
    assert default_inputs["trail_bucket_name"] == "security-autopilot-trail-logs-123456789012-us-east-1"
    assert default_inputs["create_bucket_if_missing"] is True
    assert default_inputs["create_bucket_policy"] is True
    assert default_inputs["multi_region"] is True
    assert signals["cloudtrail_existing_trail_present"] is False
    assert signals["cloudtrail_resolved_bucket_source"] == "safe_default"
    assert signals["cloudtrail_bucket_available_for_creation"] is True
    assert signals["evidence"]["cloudtrail_generated_trail_bucket_name"] == (
        "security-autopilot-trail-logs-123456789012-us-east-1"
    )
    assert signals["evidence"]["trail_bucket_name"] == "security-autopilot-trail-logs-123456789012-us-east-1"


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
    assert signals["support_bucket_probe"]["safe"] is True
    assert signals["evidence"]["trail_bucket_name"] == "tenant-cloudtrail-logs"


def test_collect_runtime_risk_signals_cloudtrail_create_if_missing_marks_bucket_available(monkeypatch) -> None:
    session = _FakeSession(
        {
            "cloudtrail": _FakeCloudTrailClient(trail_name="existing-trail", multi_region=True),
            "s3": _FakeS3Client(head_bucket_error_code="404"),
        }
    )
    monkeypatch.setattr(
        "backend.services.remediation_runtime_checks.assume_role",
        lambda **kwargs: session,
    )

    signals = collect_runtime_risk_signals(
        action=_make_action(action_type="cloudtrail_enabled"),
        strategy=_cloudtrail_strategy(),
        strategy_inputs={
            "trail_bucket_name": "new-cloudtrail-logs",
            "create_bucket_if_missing": True,
        },
        account=_make_account(),
    )

    assert signals["cloudtrail_log_bucket_reachable"] is False
    assert signals["cloudtrail_bucket_available_for_creation"] is True
    assert signals.get("cloudtrail_bucket_creation_conflict") is not True


def test_collect_runtime_risk_signals_cloudtrail_create_if_missing_rejects_existing_bucket(monkeypatch) -> None:
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
        strategy_inputs={
            "trail_bucket_name": "existing-cloudtrail-logs",
            "create_bucket_if_missing": True,
        },
        account=_make_account(),
    )

    assert signals["cloudtrail_bucket_creation_conflict"] is True
    assert "already exists" in signals["cloudtrail_bucket_creation_error"]


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
