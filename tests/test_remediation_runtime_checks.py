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
    def __init__(self, s3_client: _FakeS3Client) -> None:
        self._s3_client = s3_client

    def client(self, service_name: str, **kwargs) -> _FakeS3Client:
        assert service_name == "s3"
        return self._s3_client


def _make_action(target_id: str = "my-bucket") -> SimpleNamespace:
    return SimpleNamespace(
        action_type="s3_bucket_require_ssl",
        target_id=target_id,
        region="us-east-1",
        account_id="123456789012",
    )


def _make_account() -> SimpleNamespace:
    return SimpleNamespace(
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        external_id="tenant-ext-id",
        account_id="123456789012",
    )


def _strict_ssl_strategy() -> dict[str, Any]:
    return {"strategy_id": "s3_enforce_ssl_strict_deny"}


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
