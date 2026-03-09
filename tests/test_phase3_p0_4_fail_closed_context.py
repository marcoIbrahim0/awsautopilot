"""Phase 3 P0.4 fail-closed toxic-combination context tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.routers.actions import _action_to_detail_response
from backend.services.action_scoring import score_action_finding
from backend.services.toxic_combinations import apply_toxic_combination_overlays, evaluate_toxic_combination_overlay


def _finding(
    *,
    control_id: str,
    severity_normalized: int,
    severity_label: str,
    title: str,
    description: str,
    finding_id: str,
    resource_id: str,
    resource_type: str,
    raw_json: dict | None = None,
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
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
        account_id="123456789012",
        region="eu-north-1",
        updated_at=observed_at,
        created_at=observed_at,
        sh_updated_at=observed_at,
        last_observed_at=observed_at,
    )


def _action_from_finding(
    finding: SimpleNamespace,
    *,
    action_type: str,
    account_id: str = "123456789012",
    region: str | None = "eu-north-1",
) -> SimpleNamespace:
    score = score_action_finding(finding)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type=action_type,
        target_id=f"{account_id}|{region or 'global'}|{finding.resource_id}|{finding.control_id}",
        account_id=account_id,
        region=region,
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


def _relationship_context(*, confidence: int) -> dict:
    return {"relationship_context": {"complete": True, "confidence": confidence}}


def _public_bucket_action(*, raw_json: dict | None = None) -> SimpleNamespace:
    return _action_from_finding(
        _finding(
            control_id="S3.2",
            severity_normalized=75,
            severity_label="HIGH",
            title="Bucket is publicly accessible from 0.0.0.0/0",
            description="Public read access is enabled for this bucket.",
            finding_id="finding-public-bucket",
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
            raw_json=raw_json,
        ),
        action_type="s3_bucket_block_public_access",
    )


def _root_key_action(*, raw_json: dict | None = None) -> SimpleNamespace:
    return _action_from_finding(
        _finding(
            control_id="IAM.4",
            severity_normalized=100,
            severity_label="CRITICAL",
            title="Root credentials should not keep long-lived keys",
            description="Long-lived credentials remain active on the root user.",
            finding_id="finding-root-key",
            resource_id="123456789012",
            resource_type="AwsAccount",
            raw_json=raw_json,
        ),
        action_type="iam_root_access_key_absent",
        region=None,
    )


def test_missing_relationship_context_keeps_baseline_score_and_marks_detail_incomplete() -> None:
    public_bucket = _public_bucket_action()
    root_key = _root_key_action()
    base_score = public_bucket.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket, root_key])
    apply_toxic_combination_overlays([public_bucket, root_key])
    detail = _action_to_detail_response(public_bucket)

    assert overlay["points"] == 0
    assert overlay["context_incomplete"] is True
    assert public_bucket.score == base_score
    assert public_bucket.score_components["score_before_toxic_combinations"] == base_score
    assert public_bucket.score_components["context_incomplete"] is True
    assert detail.context_incomplete is True


def test_low_confidence_relationship_context_keeps_baseline_score() -> None:
    public_bucket = _public_bucket_action(raw_json=_relationship_context(confidence=40))
    root_key = _root_key_action(raw_json=_relationship_context(confidence=40))
    base_score = public_bucket.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket, root_key])
    apply_toxic_combination_overlays([public_bucket, root_key])

    assert overlay["points"] == 0
    assert overlay["context_incomplete"] is True
    assert public_bucket.score == base_score
    assert public_bucket.score_components["context_incomplete"] is True


def test_complete_relationship_context_still_allows_toxic_combination_promotion() -> None:
    public_bucket = _public_bucket_action(raw_json=_relationship_context(confidence=95))
    root_key = _root_key_action(raw_json=_relationship_context(confidence=95))
    base_score = public_bucket.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket, root_key])
    apply_toxic_combination_overlays([public_bucket, root_key])
    detail = _action_to_detail_response(public_bucket)

    assert overlay["points"] == 15
    assert overlay["context_incomplete"] is False
    assert public_bucket.score == base_score + 15
    assert public_bucket.score_components["context_incomplete"] is False
    assert detail.context_incomplete is False
