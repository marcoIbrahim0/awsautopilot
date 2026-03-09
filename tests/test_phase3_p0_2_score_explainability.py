"""Phase 3 P0.2 explainable score factor tests."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.routers.actions import _action_to_detail_response, _action_to_list_item, _group_actions_into_batches
from backend.services.action_scoring import build_score_factors, score_action_finding


def _finding(
    *,
    control_id: str = "S3.2",
    severity_normalized: int = 75,
    severity_label: str = "HIGH",
    title: str = "Bucket is publicly accessible from 0.0.0.0/0",
    description: str = "Public read access is enabled for this bucket.",
    finding_id: str = "finding-1",
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    observed_at = updated_at or datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_id=finding_id,
        control_id=control_id,
        severity_normalized=severity_normalized,
        severity_label=severity_label,
        title=title,
        description=description,
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
        raw_json={"ProductFields": {"aws/securityhub/SeverityLabel": severity_label}},
        account_id="123456789012",
        region="eu-north-1",
        sh_updated_at=observed_at,
        last_observed_at=observed_at,
        updated_at=observed_at,
        created_at=observed_at,
    )


def _action_from_finding(finding: SimpleNamespace) -> SimpleNamespace:
    score = score_action_finding(finding)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type="s3_bucket_block_public_access",
        target_id=f"123456789012|eu-north-1|{finding.resource_id}|S3.2",
        account_id="123456789012",
        region="eu-north-1",
        score=score.score,
        score_components=score.components,
        priority=score.score,
        status="open",
        title=finding.title,
        description=finding.description,
        control_id=finding.control_id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        updated_at=finding.updated_at,
        created_at=finding.created_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def test_score_factors_are_non_empty_and_total_matches_stored_score() -> None:
    finding = _finding()
    score = score_action_finding(finding)

    factors = build_score_factors(score.components, stored_score=score.score)

    assert factors
    assert sum(item["contribution"] for item in factors) == score.score
    assert all(item["factor_name"] for item in factors)
    assert all(item["evidence_source"] for item in factors)
    assert all(item["explanation"] for item in factors)


def test_score_factors_do_not_leak_secret_like_values() -> None:
    finding = _finding(
        control_id="IAM.4",
        severity_normalized=100,
        severity_label="CRITICAL",
        title="Root credentials should not keep long-lived keys",
        description=(
            "Root credentials remain active. SecretAccessKey=AKIAEXAMPLE "
            "password=hunter2 token=abc123"
        ),
        finding_id="finding-secret-safe",
    )

    score = score_action_finding(finding)
    payload = json.dumps(build_score_factors(score.components, stored_score=score.score))

    assert "AKIAEXAMPLE" not in payload
    assert "hunter2" not in payload
    assert "abc123" not in payload


def test_action_list_and_detail_contract_include_score_factors() -> None:
    finding = _finding()
    action = _action_from_finding(finding)

    list_item = _action_to_list_item(action)
    detail_item = _action_to_detail_response(action)

    assert list_item.score_factors
    assert detail_item.score_factors
    assert sum(item.contribution for item in list_item.score_factors) == list_item.score
    assert sum(item.contribution for item in detail_item.score_factors) == detail_item.score


def test_batch_grouping_uses_representative_score_factors() -> None:
    low_risk = _action_from_finding(_finding(finding_id="finding-low"))
    high_risk = _action_from_finding(
        _finding(
            title="Bucket is publicly accessible and internet-facing from 0.0.0.0/0",
            description="Public read access is enabled and actively exploited indicators are present.",
            finding_id="finding-high",
            updated_at=datetime(2026, 3, 9, 12, 5, tzinfo=timezone.utc),
        )
    )

    grouped = _group_actions_into_batches([low_risk, high_risk])

    assert len(grouped) == 1
    assert grouped[0].score_factors
    assert sum(item.contribution for item in grouped[0].score_factors) == grouped[0].score
