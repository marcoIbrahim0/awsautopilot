from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import RemediationRunMode, RemediationRunStatus
from backend.services.remediation_profile_resolver import RESOLVER_DECISION_VERSION_V1


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "detail-resolution@example.com"
    return user


def _mock_tenant() -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    return tenant


def _mock_action() -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.title = "Restrict public admin ports"
    action.account_id = "123456789012"
    action.region = "us-east-1"
    action.status = "resolved"
    return action


def _mock_run(
    tenant_id: uuid.UUID,
    action: MagicMock,
    *,
    mode: RemediationRunMode,
    status: RemediationRunStatus,
    artifacts: dict | None,
) -> MagicMock:
    now = datetime.now(timezone.utc)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant_id
    run.action_id = action.id
    run.mode = mode
    run.status = status
    run.outcome = "Run finished"
    run.logs = "generated bundle\nreviewed bundle"
    run.started_at = now
    run.completed_at = now
    run.created_at = now
    run.updated_at = now
    run.approved_by_user_id = uuid.uuid4()
    run.action = action
    run.artifacts = artifacts
    return run


def _mock_async_session(*scalar_results: object) -> MagicMock:
    results: list[MagicMock] = []
    for value in scalar_results:
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


def _get_run_detail(client, tenant: MagicMock, user: MagicMock, run: MagicMock):
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, run)

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        return client.get(f"/api/remediation-runs/{run.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)


def test_run_detail_uses_canonical_resolution_when_present(client) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    artifacts = {
        "resolution": {
            "strategy_id": "canonical_strategy",
            "profile_id": "canonical_profile",
            "support_tier": "review_required_bundle",
            "resolved_inputs": {"delivery_bucket": "canonical-bucket"},
            "missing_inputs": ["kms_key_arn"],
            "missing_defaults": ["cloudtrail.default_bucket_name"],
            "blocked_reasons": ["needs_manual_policy_review"],
            "rejected_profiles": [{"profile_id": "legacy_profile", "reason": "not_selected"}],
            "finding_coverage": {"summary": "canonical"},
            "preservation_summary": {"summary": "preserved"},
            "decision_rationale": "Canonical resolution persisted at create time.",
            "decision_version": RESOLVER_DECISION_VERSION_V1,
        },
        "selected_strategy": "legacy_strategy",
        "strategy_inputs": {"delivery_bucket": "legacy-bucket"},
        "risk_acknowledged": True,
        "pr_bundle": {
            "format": "terraform",
            "files": [{"path": "main.tf", "content": "terraform {}"}],
            "steps": ["review", "apply"],
            "metadata": {"generated_action_count": 1, "skipped_action_count": 0},
        },
    }
    run = _mock_run(
        tenant.id,
        action,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.success,
        artifacts=artifacts,
    )

    response = _get_run_detail(client, tenant, user, run)

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"]["strategy_id"] == "canonical_strategy"
    assert payload["resolution"]["profile_id"] == "canonical_profile"
    assert payload["resolution"]["missing_inputs"] == ["kms_key_arn"]
    assert payload["artifacts"] == artifacts
    assert payload["artifact_metadata"]["implementation_artifacts"][0]["key"] == "pr_bundle"


def test_run_detail_synthesizes_resolution_from_legacy_strategy_mirrors(client) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "risk_acknowledged": True,
    }
    run = _mock_run(
        tenant.id,
        action,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.success,
        artifacts=artifacts,
    )

    response = _get_run_detail(client, tenant, user, run)

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] == {
        "strategy_id": "config_enable_centralized_delivery",
        "profile_id": "config_enable_centralized_delivery",
        "support_tier": "review_required_bundle",
        "resolved_inputs": {"delivery_bucket": "central-config-bucket"},
        "missing_inputs": [],
        "missing_defaults": [],
        "blocked_reasons": [],
        "rejected_profiles": [],
        "finding_coverage": {},
        "preservation_summary": {},
        "decision_rationale": "Synthesized from legacy remediation run artifact mirrors.",
        "decision_version": RESOLVER_DECISION_VERSION_V1,
    }
    assert payload["artifacts"] == artifacts


def test_run_detail_leaves_resolution_null_for_direct_fix_legacy_runs(client) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    artifacts = {
        "selected_strategy": "s3_account_block_public_access_direct_fix",
        "strategy_inputs": {},
        "direct_fix": {"outcome": "Applied safely", "post_check_passed": True},
    }
    run = _mock_run(
        tenant.id,
        action,
        mode=RemediationRunMode.direct_fix,
        status=RemediationRunStatus.success,
        artifacts=artifacts,
    )

    response = _get_run_detail(client, tenant, user, run)

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] is None
    assert payload["artifacts"] == artifacts


def test_run_detail_leaves_resolution_null_without_strategy_backed_legacy_data(client) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    artifacts = {"pr_bundle_variant": "cloudfront_oac_private_s3"}
    run = _mock_run(
        tenant.id,
        action,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.success,
        artifacts=artifacts,
    )

    response = _get_run_detail(client, tenant, user, run)

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] is None
    assert payload["artifacts"] == artifacts


def test_run_detail_does_not_synthesize_single_resolution_for_group_legacy_runs(client) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "group_bundle": {
            "group_key": "config|123456789012|us-east-1|open",
            "action_ids": [str(action.id)],
            "action_count": 1,
        },
    }
    run = _mock_run(
        tenant.id,
        action,
        mode=RemediationRunMode.pr_only,
        status=RemediationRunStatus.success,
        artifacts=artifacts,
    )

    response = _get_run_detail(client, tenant, user, run)

    assert response.status_code == 200
    payload = response.json()
    assert payload["resolution"] is None
    assert payload["artifacts"] == artifacts
