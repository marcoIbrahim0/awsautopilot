"""Phase 3 P0.3 toxic-combination prioritization tests."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers import actions as actions_router
from backend.services.finding_relationship_context import build_finding_relationship_context
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


def _produced_relationship_context(
    *,
    resource_id: str,
    resource_type: str,
    account_id: str = "123456789012",
    region: str | None = "eu-north-1",
) -> dict:
    return {
        "relationship_context": build_finding_relationship_context(
            account_id=account_id,
            region=region,
            resource_id=resource_id,
            resource_type=resource_type,
        )
    }


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


def _internet_anchor_action(*, raw_json: dict | None = None, resource_id: str = "resource-1") -> SimpleNamespace:
    return _action_from_finding(
        _finding(
            control_id="Custom.1",
            severity_normalized=75,
            severity_label="HIGH",
            title="Internet-facing service is open to 0.0.0.0/0",
            description="Public network access is enabled for this service endpoint.",
            finding_id=f"finding-anchor-{resource_id}",
            resource_id=resource_id,
            resource_type="CustomResource",
            raw_json=raw_json,
        ),
        action_type="pr_only",
    )


def _same_resource_sensitive_action(*, raw_json: dict | None = None, resource_id: str = "resource-1") -> SimpleNamespace:
    return _action_from_finding(
        _finding(
            control_id="Custom.2",
            severity_normalized=50,
            severity_label="MEDIUM",
            title="Sensitive records are stored without encryption",
            description="Sensitive customer records require stronger protection.",
            finding_id=f"finding-sensitive-{resource_id}",
            resource_id=resource_id,
            resource_type="CustomResource",
            raw_json=raw_json,
        ),
        action_type="pr_only",
    )


def _unrelated_security_group_action(*, raw_json: dict | None = None) -> SimpleNamespace:
    return _action_from_finding(
        _finding(
            control_id="EC2.53",
            severity_normalized=90,
            severity_label="CRITICAL",
            title="Public SSH admin port open to 0.0.0.0/0",
            description="Critical exposure on an internet-facing security group.",
            finding_id="finding-sg-open",
            resource_id="sg-0123456789abcdef0",
            resource_type="AwsEc2SecurityGroup",
            raw_json=raw_json,
        ),
        action_type="sg_restrict_public_ports",
    )


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    user.id = uuid.uuid4()
    return user


def test_toxic_combination_positive_match_boosts_exposed_resource_action() -> None:
    public_bucket = _public_bucket_action(
        raw_json=_produced_relationship_context(
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        )
    )
    root_key = _root_key_action(
        raw_json=_produced_relationship_context(
            resource_id="123456789012",
            resource_type="AwsAccount",
            region=None,
        )
    )
    base_score = public_bucket.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket, root_key])
    matched = apply_toxic_combination_overlays([public_bucket, root_key])

    assert overlay["points"] == 15
    assert "public_exposure_privilege_sensitive_data" in overlay["matched_rule_ids"]
    assert matched == 1
    assert public_bucket.score == base_score + 15
    assert public_bucket.priority == base_score + 15
    assert public_bucket.score_components["toxic_combinations"]["points"] == 15
    assert "context is incomplete" in root_key.score_components["toxic_combinations"]["explanation"].lower()


def test_toxic_combination_partial_match_requires_all_signals() -> None:
    public_bucket = _public_bucket_action(
        raw_json=_produced_relationship_context(
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        )
    )
    base_score = public_bucket.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket])
    apply_toxic_combination_overlays([public_bucket])

    assert overlay["points"] == 0
    assert "privilege_weakness" in overlay["missing_signals"]
    assert public_bucket.score == base_score
    assert public_bucket.score_components["toxic_combinations"]["points"] == 0
    assert "missing" in public_bucket.score_components["toxic_combinations"]["explanation"].lower()


def test_toxic_combination_unrelated_findings_do_not_boost() -> None:
    public_bucket = _public_bucket_action(
        raw_json=_produced_relationship_context(
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        )
    )
    unrelated_sg = _unrelated_security_group_action(
        raw_json=_produced_relationship_context(
            resource_id="sg-0123456789abcdef0",
            resource_type="AwsEc2SecurityGroup",
        )
    )
    public_bucket_base_score = public_bucket.score
    unrelated_sg_base_score = unrelated_sg.score

    overlay = evaluate_toxic_combination_overlay(public_bucket, [public_bucket, unrelated_sg])
    apply_toxic_combination_overlays([public_bucket, unrelated_sg])

    assert overlay["points"] == 0
    assert public_bucket.score == public_bucket_base_score
    assert unrelated_sg.score == unrelated_sg_base_score
    assert "privilege_weakness" in overlay["missing_signals"]


def test_toxic_combination_account_scoped_anchor_never_promotes() -> None:
    public_bucket = _public_bucket_action(
        raw_json=_produced_relationship_context(
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        )
    )
    root_key = _root_key_action(
        raw_json=_produced_relationship_context(
            resource_id="123456789012",
            resource_type="AwsAccount",
            region=None,
        )
    )
    base_score = root_key.score

    overlay = evaluate_toxic_combination_overlay(root_key, [public_bucket, root_key])
    apply_toxic_combination_overlays([public_bucket, root_key])

    assert overlay["points"] == 0
    assert overlay["context_incomplete"] is True
    assert root_key.score == base_score
    assert root_key.score_components["toxic_combinations"]["points"] == 0


def test_toxic_combination_same_resource_and_account_support_can_promote_anchor() -> None:
    anchor = _internet_anchor_action(
        raw_json=_produced_relationship_context(resource_id="resource-1", resource_type="CustomResource")
    )
    sensitive = _same_resource_sensitive_action(
        raw_json=_produced_relationship_context(resource_id="resource-1", resource_type="CustomResource")
    )
    root_key = _root_key_action(
        raw_json=_produced_relationship_context(
            resource_id="123456789012",
            resource_type="AwsAccount",
            region=None,
        )
    )
    base_score = anchor.score

    overlay = evaluate_toxic_combination_overlay(anchor, [anchor, sensitive, root_key])
    apply_toxic_combination_overlays([anchor, sensitive, root_key])

    assert overlay["points"] == 15
    assert overlay["context_incomplete"] is False
    assert overlay["matched_rule_ids"] == ["public_exposure_privilege_sensitive_data"]
    assert anchor.score == base_score + 15


def test_actions_api_batch_view_exposes_boosted_priority(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    public_bucket = _public_bucket_action(
        raw_json=_produced_relationship_context(
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        )
    )
    public_bucket.tenant_id = tenant_id
    root_key = _root_key_action(
        raw_json=_produced_relationship_context(
            resource_id="123456789012",
            resource_type="AwsAccount",
            region=None,
        )
    )
    root_key.tenant_id = tenant_id
    apply_toxic_combination_overlays([public_bucket, root_key])

    grouped_row = SimpleNamespace(
        id=str(group_id),
        action_type=public_bucket.action_type,
        account_id=public_bucket.account_id,
        region=public_bucket.region,
        score=public_bucket.score,
        priority=public_bucket.priority,
        updated_at=public_bucket.updated_at,
        control_id=public_bucket.control_id,
        action_count=1,
        finding_count=1,
        open_count=1,
        in_progress_count=0,
        resolved_count=0,
        suppressed_count=0,
    )
    execute_count = {"value": 0}

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        execute_count["value"] += 1
        result = MagicMock()
        if execute_count["value"] == 1:
            result.scalar.return_value = 1
            return result
        if execute_count["value"] == 2:
            result.all.return_value = [grouped_row]
            return result
        if execute_count["value"] == 3:
            result.all.return_value = [(str(group_id), public_bucket)]
            return result
        return result

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return _mock_user(tenant_id)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            response = client.get("/api/actions", params={"group_by": "batch"})

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["score"] == public_bucket.score
    assert body["items"][0]["priority"] == public_bucket.priority
    toxic_factor = next(item for item in body["items"][0]["score_factors"] if item["factor_name"] == "toxic_combinations")
    assert toxic_factor["contribution"] == 15
