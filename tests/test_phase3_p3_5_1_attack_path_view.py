"""Phase 3.5.1 attack-path view regressions."""
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
from backend.services.action_attack_path_view import build_action_attack_path_view


def _relationship_context(*, confidence: float = 0.92) -> dict[str, object]:
    return {
        "complete": True,
        "confidence": confidence,
        "account_id": "123456789012",
        "region": "us-east-1",
        "resource_id": "arn:aws:s3:::prod-sensitive-bucket",
        "resource_type": "AwsS3Bucket",
        "resource_key": "s3:prod-sensitive-bucket",
    }


def _action(*, context_incomplete: bool = False) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-1",
        severity_label="HIGH",
        title="Finding title",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        account_id="123456789012",
        region="us-east-1",
        updated_at=observed_at,
        raw_json={"relationship_context": _relationship_context()},
    )
    components = {
        "context_incomplete": context_incomplete,
        "relationship_context": _relationship_context(),
        "severity": {"points": 35, "signals": ["severity:HIGH"]},
        "internet_exposure": {"normalized": 1.0, "points": 20, "signals": ["keyword:publicly accessible"]},
        "privilege_level": {"normalized": 0.6, "points": 9, "signals": ["keyword:iam"]},
        "data_sensitivity": {"normalized": 0.8, "points": 12, "signals": ["keyword:customer data"]},
        "exploit_signals": {
            "normalized": 0.67,
            "points": 10,
            "signals": ["threat_intel:cisa_kev:CVE-2026-9001"],
            "applied_threat_signals": [
                {
                    "source": "cisa_kev",
                    "identifier": "CVE-2026-9001",
                    "cve_id": "CVE-2026-9001",
                    "timestamp": "2026-03-12T11:00:00+00:00",
                    "base_points": 10,
                    "applied_points": 10,
                    "final_contribution": 10,
                    "decay_applied": 0.99,
                }
            ],
        },
        "business_impact": {
            "criticality": {
                "status": "known",
                "score": 75,
                "tier": "critical",
                "weight": 4,
                "dimensions": [
                    {
                        "dimension": "customer_facing",
                        "label": "Customer-facing",
                        "weight": 25,
                        "matched": True,
                        "contribution": 25,
                        "signals": ["keyword:customer"],
                    }
                ],
            }
        },
        "score": 86,
    }
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type="s3_bucket_block_public_access",
        target_id="target-1",
        account_id="123456789012",
        region="us-east-1",
        score=86,
        score_components=components,
        priority=86,
        status="open",
        title="Block public access on customer data bucket",
        description="Customer data bucket is publicly accessible and actively exploited.",
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        owner_type="service",
        owner_key="payments-api",
        owner_label="Payments API",
        created_at=observed_at,
        updated_at=observed_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _graph_context(*, truncated: bool = False, status: str = "available") -> dict[str, object]:
    return {
        "status": status,
        "availability_reason": None if status == "available" else "relationship_context_unavailable",
        "source": "finding_relationship_context+inventory_assets",
        "connected_assets": [
            {
                "label": "arn:aws:s3:::prod-sensitive-bucket",
                "resource_id": "arn:aws:s3:::prod-sensitive-bucket",
                "resource_type": "AwsS3Bucket",
                "resource_key": "s3:prod-sensitive-bucket",
                "relationship": "anchor",
                "finding_count": 2,
                "action_count": 1,
                "inventory_services": ["s3"],
            }
        ],
        "identity_path": [
            {
                "node_type": "principal",
                "label": "arn:aws:iam::123456789012:role/AppRole",
                "value": "arn:aws:iam::123456789012:role/AppRole",
                "source": "finding.raw_json.principal",
            }
        ],
        "blast_radius_neighborhood": [
            {
                "scope": "anchor",
                "label": "arn:aws:s3:::prod-sensitive-bucket",
                "resource_id": "arn:aws:s3:::prod-sensitive-bucket",
                "resource_type": "AwsS3Bucket",
                "resource_key": "s3:prod-sensitive-bucket",
                "finding_count": 2,
                "open_action_count": 1,
                "inventory_service_count": 1,
                "controls": ["S3.2"],
            }
        ],
        "truncated_sections": ["connected_assets"] if truncated else [],
        "limits": {
            "max_related_findings": 24,
            "max_related_actions": 24,
            "max_inventory_assets": 24,
            "max_connected_assets": 6,
            "max_identity_nodes": 6,
            "max_blast_radius_neighbors": 6,
        },
    }


def _business_impact() -> dict[str, object]:
    return {
        "technical_risk_score": 86,
        "technical_risk_tier": "critical",
        "criticality": {"tier": "critical"},
        "matrix_position": {"cell": "critical:critical"},
        "summary": "Critical technical risk intersects with Critical business criticality.",
    }


def _recommendation() -> dict[str, object]:
    return {
        "mode": "pr_only",
        "default_mode": "pr_only",
        "advisory": True,
        "enforced_by_policy": None,
        "rationale": "High risk and high criticality default to PR-only.",
    }


def _score_factors() -> list[dict[str, object]]:
    return [
        {
            "factor_name": "exploit_signals",
            "contribution": 10,
            "explanation": "Exploit signals contributed 10 points using trusted threat intel.",
            "provenance": [{"source": "cisa_kev"}],
        },
        {
            "factor_name": "internet_exposure",
            "contribution": 20,
            "explanation": "Internet exposure contributed 20 points using: keyword:publicly accessible.",
            "provenance": [],
        },
    ]


def _execution_guidance() -> list[dict[str, object]]:
    return [
        {
            "strategy_id": "s3_bucket_block_public_access_standard",
            "label": "Generate PR bundle",
            "mode": "pr_only",
            "recommended": True,
            "blast_radius": "resource",
            "blast_radius_summary": "Changes stay scoped to the affected bucket.",
            "pre_checks": [],
            "expected_outcome": "PR bundle applies bucket-level public access protections.",
            "post_checks": [],
            "rollback": {
                "summary": "Revert the generated infrastructure change.",
                "command": "git revert <commit>",
                "notes": [],
            },
        }
    ]


def test_attack_path_view_available_state_returns_bounded_story() -> None:
    payload = build_action_attack_path_view(
        _action(),
        graph_context=_graph_context(),
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
        sla={"state": "on_track"},
    )

    assert payload["status"] == "available"
    assert payload["summary"]
    assert payload["path_nodes"]
    assert payload["path_edges"]
    assert payload["entry_points"][0]["label"] == "Actively exploited path"
    assert payload["target_assets"][0]["label"] == "arn:aws:s3:::prod-sensitive-bucket"
    assert payload["recommendation_summary"] == "Safest next step: Generate PR bundle via PR only."
    assert payload["confidence"] == 0.92
    assert payload["truncated"] is False


def test_attack_path_view_partial_state_marks_truncated_context() -> None:
    payload = build_action_attack_path_view(
        _action(),
        graph_context=_graph_context(truncated=True),
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
        sla={"state": "expiring"},
    )

    assert payload["status"] == "partial"
    assert payload["truncated"] is True
    assert payload["availability_reason"] == "bounded_context_truncated"
    assert "truncated or unresolved" in payload["summary"]


def test_attack_path_view_unavailable_state_is_explicit() -> None:
    payload = build_action_attack_path_view(
        _action(),
        graph_context=_graph_context(status="unavailable"),
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
    )

    assert payload["status"] == "unavailable"
    assert payload["path_nodes"] == []
    assert payload["path_edges"] == []
    assert payload["entry_points"] == []
    assert payload["target_assets"] == []
    assert payload["availability_reason"] == "relationship_context_unavailable"


def test_attack_path_view_context_incomplete_state_is_fail_closed() -> None:
    payload = build_action_attack_path_view(
        _action(context_incomplete=True),
        graph_context=_graph_context(status="unavailable"),
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
    )

    assert payload["status"] == "context_incomplete"
    assert payload["path_nodes"] == []
    assert payload["path_edges"] == []
    assert "fail-closed" in payload["summary"]


def test_get_action_returns_attack_path_view_payload(client: TestClient) -> None:
    action = _action()
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id
    account = MagicMock()
    account.tenant_id = tenant_id
    account.account_id = action.account_id

    session = MagicMock()
    result_tenant = MagicMock()
    result_tenant.scalar_one_or_none.return_value = tenant
    result_action = MagicMock()
    result_action.scalar_one_or_none.return_value = action
    result_account = MagicMock()
    result_account.scalar_one_or_none.return_value = account
    session.execute = AsyncMock(side_effect=[result_tenant, result_action, result_account])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        user = MagicMock()
        user.id = uuid.uuid4()
        user.tenant_id = tenant_id
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        with patch(
            "backend.routers.actions.get_exception_state_for_response",
            new=AsyncMock(return_value={}),
        ):
            with patch(
                "backend.routers.actions._load_action_implementation_artifacts",
                new=AsyncMock(return_value=[]),
            ):
                with patch(
                    "backend.routers.actions._load_action_graph_context",
                    new=AsyncMock(return_value=_graph_context()),
                ):
                    with patch(
                        "backend.routers.actions.build_action_execution_guidance",
                        return_value=_execution_guidance(),
                    ):
                        response = client.get(f"/api/actions/{action.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["attack_path_view"]["status"] == "available"
    assert body["attack_path_view"]["path_nodes"]
    assert body["attack_path_view"]["entry_points"]
    assert body["attack_path_view"]["target_assets"]
