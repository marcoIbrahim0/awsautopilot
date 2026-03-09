"""Phase 3 P0.1 scoring tests for context-driven action prioritization."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.services.action_scoring import score_action_finding, score_action_group


def _finding(
    *,
    control_id: str,
    severity_normalized: int,
    severity_label: str,
    title: str,
    description: str,
    finding_id: str,
    updated_at: datetime,
    resource_id: str = "resource-1",
    resource_type: str = "AwsS3Bucket",
    raw_json: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_id=finding_id,
        control_id=control_id,
        severity_normalized=severity_normalized,
        severity_label=severity_label,
        title=title,
        description=description,
        resource_id=resource_id,
        resource_type=resource_type,
        raw_json=raw_json or {},
        sh_updated_at=updated_at,
        last_observed_at=updated_at,
        updated_at=updated_at,
        created_at=updated_at,
    )


def test_root_key_score_formula_is_exact_and_deterministic() -> None:
    finding = _finding(
        control_id="IAM.4",
        severity_normalized=100,
        severity_label="CRITICAL",
        title="Root credentials should not keep long-lived keys",
        description="Long-lived credentials remain active on the root user.",
        finding_id="finding-root-1",
        updated_at=datetime(2026, 3, 9, 9, 0, tzinfo=timezone.utc),
        resource_id="123456789012",
        resource_type="AwsAccount",
    )

    first = score_action_finding(finding)
    second = score_action_finding(finding)

    assert first.score == 72
    assert first.score == second.score
    assert first.components == second.components
    assert first.components["severity"]["points"] == 35
    assert first.components["privilege_level"]["points"] == 15
    assert first.components["data_sensitivity"]["points"] == 9
    assert first.components["exploit_signals"]["points"] == 13
    assert first.components["compensating_controls"]["points"] == 0


def test_higher_risk_public_bucket_outranks_visibility_gap() -> None:
    high_risk = _finding(
        control_id="S3.2",
        severity_normalized=75,
        severity_label="HIGH",
        title="Bucket is publicly accessible from 0.0.0.0/0",
        description="Public read access is enabled for this bucket.",
        finding_id="finding-s3-public",
        updated_at=datetime(2026, 3, 9, 10, 0, tzinfo=timezone.utc),
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
    )
    low_risk = _finding(
        control_id="SecurityHub.1",
        severity_normalized=75,
        severity_label="HIGH",
        title="Security Hub disabled",
        description="Security Hub is not enabled in the target region.",
        finding_id="finding-sh-disabled",
        updated_at=datetime(2026, 3, 9, 10, 5, tzinfo=timezone.utc),
        resource_id="123456789012",
        resource_type="AwsAccount",
    )

    assert score_action_finding(high_risk).score > score_action_finding(low_risk).score


def test_compensating_controls_reduce_the_same_base_risk() -> None:
    base = _finding(
        control_id="S3.2",
        severity_normalized=75,
        severity_label="HIGH",
        title="Bucket is publicly accessible from 0.0.0.0/0",
        description="Public read access is enabled for this bucket.",
        finding_id="finding-s3-base",
        updated_at=datetime(2026, 3, 9, 11, 0, tzinfo=timezone.utc),
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
    )
    compensated = _finding(
        control_id="S3.2",
        severity_normalized=75,
        severity_label="HIGH",
        title="Bucket is publicly accessible from 0.0.0.0/0",
        description="Public read access is enabled for this bucket, but access is VPC only with an allowlist.",
        finding_id="finding-s3-compensated",
        updated_at=datetime(2026, 3, 9, 11, 5, tzinfo=timezone.utc),
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
    )

    uncompensated_score = score_action_finding(base)
    compensated_score = score_action_finding(compensated)

    assert compensated_score.score < uncompensated_score.score
    assert compensated_score.components["compensating_controls"]["points"] < 0


def test_group_scoring_is_stable_across_input_order() -> None:
    older = _finding(
        control_id="IAM.4",
        severity_normalized=100,
        severity_label="CRITICAL",
        title="Root credentials should not keep long-lived keys",
        description="Long-lived credentials remain active on the root user.",
        finding_id="finding-root-older",
        updated_at=datetime(2026, 3, 9, 8, 0, tzinfo=timezone.utc),
        resource_id="123456789012",
        resource_type="AwsAccount",
    )
    newer = _finding(
        control_id="IAM.4",
        severity_normalized=100,
        severity_label="CRITICAL",
        title="Root credentials should not keep long-lived keys",
        description="Long-lived credentials remain active on the root user.",
        finding_id="finding-root-newer",
        updated_at=datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc),
        resource_id="123456789012",
        resource_type="AwsAccount",
    )

    first = score_action_group([older, newer])
    second = score_action_group([newer, older])

    assert first.score == second.score
    assert first.components == second.components
    assert first.components["representative_finding_id"] == "finding-root-newer"


def test_score_is_bounded_to_zero_through_one_hundred() -> None:
    finding = _finding(
        control_id="EC2.53",
        severity_normalized=100,
        severity_label="CRITICAL",
        title="Public SSH admin port open to 0.0.0.0/0",
        description="Critical exposure on an internet-facing security group.",
        finding_id="finding-sg-max",
        updated_at=datetime(2026, 3, 9, 13, 0, tzinfo=timezone.utc),
        resource_id="sg-123",
        resource_type="AwsEc2SecurityGroup",
    )

    score = score_action_finding(finding)

    assert 0 <= score.score <= 100
    assert score.score == 92
