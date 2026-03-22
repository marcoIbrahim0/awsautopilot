"""Phase 3.5.1 attack-path view regressions."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers.actions import _attack_path_action_scan_limit, _enrich_attack_path_records
from backend.services.action_attack_path_view import build_action_attack_path_view
from backend.services.attack_paths import build_shared_attack_path_records


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
        "compensating_controls": {
            "normalized": 0.1,
            "points": 1,
            "signals": ["mitigating-control:cloudfront"],
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


def _account_action(*, toxic_context_incomplete: bool = True) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    relationship = {
        "complete": True,
        "confidence": 0.96,
        "account_id": "123456789012",
        "region": None,
        "resource_id": "123456789012",
        "resource_type": "AwsAccount",
        "resource_key": "account:123456789012",
    }
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-account-1",
        severity_label="CRITICAL",
        title="Account finding title",
        resource_id="123456789012",
        account_id="123456789012",
        region=None,
        updated_at=observed_at,
        raw_json={"relationship_context": relationship},
    )
    components = {
        "context_incomplete": toxic_context_incomplete,
        "relationship_context": relationship,
        "toxic_combinations": {
            "context_incomplete": toxic_context_incomplete,
            "context_incomplete_rule_ids": ["public_exposure_privilege_sensitive_data"],
            "matched_rule_ids": [],
            "points": 0,
        },
        "severity": {"points": 40, "signals": ["severity:CRITICAL"]},
        "privilege_level": {"normalized": 1.0, "points": 15, "signals": ["keyword:root"]},
        "score": 70,
    }
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type="iam_root_access_key_absent",
        target_id="account-target-1",
        account_id="123456789012",
        region=None,
        score=70,
        score_components=components,
        priority=70,
        status="open",
        title="Remove root access keys",
        description="The AWS account has root access key risk.",
        control_id="IAM.4",
        resource_id="123456789012",
        resource_type="AwsAccount",
        owner_type="team",
        owner_key="platform-security",
        owner_label="Platform Security",
        created_at=observed_at,
        updated_at=observed_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _missing_relationship_action() -> SimpleNamespace:
    action = _action(context_incomplete=True)
    action.score_components = {**action.score_components, "relationship_context": {"complete": False, "confidence": 0.0}}
    return action


def _graph_context(*, truncated: bool = False, status: str = "available") -> dict[str, object]:
    return {
        "status": status,
        "availability_reason": None if status == "available" else "relationship_context_unavailable",
        "path_signature": "path:test-graph",
        "entry_points": [],
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


def _account_graph_context(*, truncated: bool = False, status: str = "available") -> dict[str, object]:
    return {
        "status": status,
        "availability_reason": None if status == "available" else "relationship_context_unavailable",
        "path_signature": "path:test-account",
        "entry_points": [],
        "source": "finding_relationship_context+inventory_assets",
        "connected_assets": [
            {
                "label": "123456789012",
                "resource_id": "123456789012",
                "resource_type": "AwsAccount",
                "resource_key": "account:123456789012",
                "relationship": "anchor",
                "finding_count": 3,
                "action_count": 2,
                "inventory_services": ["iam", "config"],
            }
        ],
        "identity_path": [
            {
                "node_type": "account",
                "label": "123456789012",
                "value": "123456789012",
                "source": "action.account_id",
            }
        ],
        "blast_radius_neighborhood": [
            {
                "scope": "anchor",
                "label": "123456789012",
                "resource_id": "123456789012",
                "resource_type": "AwsAccount",
                "resource_key": "account:123456789012",
                "finding_count": 3,
                "open_action_count": 2,
                "inventory_service_count": 2,
                "controls": ["IAM.4", "Config.1"],
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


def test_attack_path_view_prefers_graph_native_entry_points() -> None:
    graph = _graph_context()
    graph["entry_points"] = [
        {
            "node_id": "entry:security-graph",
            "kind": "entry_point",
            "label": "Public exposure",
            "detail": "Internet Exposure",
            "badges": [],
        }
    ]
    payload = build_action_attack_path_view(
        _action(),
        graph_context=graph,
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
        sla={"state": "on_track"},
    )

    assert payload["entry_points"][0]["label"] == "Public exposure"
    assert payload["path_nodes"][0]["node_id"] == "entry:security-graph"


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
        _missing_relationship_action(),
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


def test_attack_path_view_account_scope_ignores_toxic_context_incomplete_marker() -> None:
    payload = build_action_attack_path_view(
        _account_action(),
        graph_context=_account_graph_context(),
        business_impact=_business_impact(),
        recommendation=_recommendation(),
        score_factors=_score_factors(),
        execution_guidance=_execution_guidance(),
    )

    assert payload["status"] == "available"
    assert payload["availability_reason"] is None
    assert payload["path_nodes"]
    assert payload["entry_points"]
    assert payload["target_assets"][0]["label"] == "123456789012"


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
                        "backend.routers.actions._load_action_attack_path_graph_context",
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
    assert body["path_id"].startswith("path:")


def test_list_attack_paths_returns_ranked_items(client: TestClient) -> None:
    action = _action()
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id

    session = MagicMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    actions_result = MagicMock()
    actions_result.scalars.return_value.all.return_value = [action]
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[tenant_result, actions_result, accounts_result])

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
            "backend.routers.actions.list_materialized_attack_paths",
            new=AsyncMock(
                return_value=(
                    [
                        {
                            "id": "path:abc123",
                            "status": "available",
                            "rank": 78,
                            "confidence": 0.92,
                            "entry_points": [{"node_id": "entry-1", "kind": "entry_point", "label": "Public exposure"}],
                            "target_assets": [{"node_id": "target-1", "kind": "target_asset", "label": "prod-bucket"}],
                            "summary": "Critical technical risk intersects with Critical business criticality.",
                            "business_impact_summary": "Critical technical risk intersects with Critical business criticality.",
                            "recommended_fix_summary": "Block public access on customer data bucket",
                            "owner_labels": [action.owner_label],
                            "linked_action_ids": [str(action.id)],
                            "freshness": {"score": 0.98, "observed_at": "2026-03-12T12:00:00+00:00"},
                            "rank_factors": [{"name": "exploitability", "label": "Exploitability", "direction": "positive", "score": 0.8, "weight": 0.22, "weighted_impact": 0.176, "explanation": "signals"}],
                            "remediation_summary": {
                                "linked_actions_total": 1,
                                "open_actions": 1,
                                "in_progress_actions": 0,
                                "resolved_actions": 0,
                                "highest_priority_open": 86,
                                "coverage_summary": "1 linked action remains open and 0 already resolved.",
                            },
                            "runtime_signals": {
                                "workload_presence": "present",
                                "publicly_reachable": True,
                                "sensitive_target_count": 1,
                                "identity_hops": 1,
                                "confidence": 0.92,
                                "summary": "1 entry point and 1 connected asset inform this path.",
                            },
                            "closure_targets": {
                                "open_action_ids": [str(action.id)],
                                "in_progress_action_ids": [],
                                "resolved_action_ids": [],
                                "summary": "1 open linked action remains before this path can materially drop.",
                            },
                            "governance_summary": {
                                "provider_count": 1,
                                "drifted_count": 0,
                                "in_sync_count": 1,
                                "linked_items": ["jira:SEC-1"],
                                "summary": "External workflow links are present across 1 provider and currently aligned.",
                            },
                            "access_scope": {
                                "scope": "tenant_scoped",
                                "evidence_visibility": "full",
                                "restricted_sections": [],
                                "export_allowed": True,
                            },
                        }
                    ],
                    1,
                    False,
                )
            ),
        ):
            response = client.get("/api/actions/attack-paths")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["selected_view"] is None
    assert body["available_views"][0]["key"] == "highest_blast_radius"
    assert body["items"][0]["status"] == "available"
    assert body["items"][0]["linked_action_ids"] == [str(action.id)]
    assert body["items"][0]["rank_factors"][0]["name"] == "exploitability"
    assert body["items"][0]["freshness"]["score"] == 0.98
    assert body["items"][0]["remediation_summary"]["open_actions"] == 1
    assert body["items"][0]["runtime_signals"]["publicly_reachable"] is True
    assert body["items"][0]["governance_summary"]["provider_count"] == 1


def test_get_attack_path_returns_shared_detail_payload(client: TestClient) -> None:
    action = _action()
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id

    session = MagicMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    actions_result = MagicMock()
    actions_result.scalars.return_value.all.return_value = [action]
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[tenant_result, actions_result, accounts_result])

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
            "backend.routers.actions.get_materialized_attack_path",
            new=AsyncMock(
                return_value=(
                    {
                        "id": "path:abc123",
                        "status": "available",
                        "rank": 78,
                        "confidence": 0.92,
                        "freshness": {"score": 0.98, "observed_at": "2026-03-12T12:00:00+00:00"},
                        "rank_factors": [{"name": "exploitability", "label": "Exploitability", "direction": "positive", "score": 0.8, "weight": 0.22, "weighted_impact": 0.176, "explanation": "signals"}],
                        "path_nodes": [
                            {"node_id": "entry-1", "kind": "entry_point", "label": "Public exposure"},
                            {"node_id": "target-1", "kind": "target_asset", "label": "prod-bucket"},
                        ],
                        "path_edges": [{"source_node_id": "entry-1", "target_node_id": "target-1", "label": "can reach"}],
                        "entry_points": [{"node_id": "entry-1", "kind": "entry_point", "label": "Public exposure"}],
                        "target_assets": [{"node_id": "target-1", "kind": "target_asset", "label": "prod-bucket"}],
                        "business_impact": {"summary": "Critical technical risk intersects with Critical business criticality.", "criticality_tier": "critical", "criticality_score": 75},
                        "summary": "Critical technical risk intersects with Critical business criticality.",
                        "risk_reasons": ["Exploit signals increase likelihood of path execution."],
                        "owners": [{"key": action.owner_key, "label": action.owner_label}],
                        "recommended_fix": {"summary": "Block public access on customer data bucket", "action_type": action.action_type},
                        "linked_actions": [{"id": str(action.id), "title": action.title, "priority": action.priority, "status": action.status, "owner_label": action.owner_label}],
                        "remediation_summary": {
                            "linked_actions_total": 1,
                            "open_actions": 1,
                            "in_progress_actions": 0,
                            "resolved_actions": 0,
                            "highest_priority_open": 86,
                            "coverage_summary": "1 linked action remains open and 0 already resolved.",
                        },
                        "runtime_signals": {
                            "workload_presence": "present",
                            "publicly_reachable": True,
                            "sensitive_target_count": 1,
                            "identity_hops": 1,
                            "confidence": 0.92,
                            "summary": "1 entry point and 1 connected asset inform this path.",
                        },
                        "exposure_validation": {
                            "status": "verified",
                            "summary": "Persisted graph evidence resolves a bounded entry point and target path.",
                            "observed_at": "2026-03-12T12:00:00+00:00",
                        },
                        "code_context": {
                            "owner_label": action.owner_label,
                            "service_owner_key": action.owner_key,
                            "repository_count": 1,
                            "implementation_artifact_count": 1,
                            "summary": "1 linked repo target and 1 implementation artifact are available.",
                        },
                        "linked_repositories": [
                            {
                                "provider": "generic_git",
                                "repository": "acme/platform",
                                "base_branch": "main",
                                "root_path": "infra",
                                "source_run_id": "run-1",
                            }
                        ],
                        "implementation_artifacts": [
                            {
                                "run_id": "run-1",
                                "run_status": "success",
                                "run_mode": "pr_only",
                                "artifact_key": "pr_payload",
                                "kind": "pr_payload",
                                "label": "Provider-agnostic PR payload",
                                "description": "Draft PR payload",
                                "href": "/remediation-runs/run-1",
                                "executable": False,
                                "generated_at": "2026-03-12T12:00:00+00:00",
                                "closure_status": "pending",
                                "metadata": {"repository": "acme/platform"},
                            }
                        ],
                        "closure_targets": {
                            "open_action_ids": [str(action.id)],
                            "in_progress_action_ids": [],
                            "resolved_action_ids": [],
                            "summary": "1 open linked action remains before this path can materially drop.",
                        },
                        "external_workflow_summary": {
                            "provider_count": 1,
                            "drifted_count": 1,
                            "in_sync_count": 0,
                            "linked_items": ["jira:SEC-1"],
                            "summary": "1 linked external workflow item is drifted across 1 provider.",
                        },
                        "exception_summary": {
                            "active_count": 1,
                            "expiring_count": 0,
                            "summary": "1 active exception currently governs linked actions on this path.",
                        },
                        "evidence_exports": {
                            "evidence_item_count": 1,
                            "implementation_artifact_count": 1,
                            "export_ready": True,
                            "summary": "1 evidence item and 1 implementation artifact are available for closure review.",
                        },
                        "access_scope": {
                            "scope": "tenant_scoped",
                            "evidence_visibility": "full",
                            "restricted_sections": [],
                            "export_allowed": True,
                        },
                        "evidence": [{"type": "finding", "id": "finding-1", "label": "Finding title", "updated_at": "2026-03-12T12:00:00+00:00"}],
                        "provenance": [{"source": "security_graph_nodes+security_graph_edges", "kind": "graph"}],
                        "truncated": False,
                        "availability_reason": None,
                        "computed_at": "2026-03-22T12:00:00+00:00",
                        "stale_after": "2026-03-22T12:05:00+00:00",
                        "is_stale": False,
                        "refresh_status": "ready",
                    },
                    False,
                )
            ),
        ):
            response = client.get("/api/actions/attack-paths/path:abc123")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "path:abc123"
    assert body["path_nodes"]
    assert body["path_edges"]
    assert body["linked_actions"][0]["id"] == str(action.id)
    assert body["evidence"][0]["id"] == "finding-1"
    assert body["remediation_summary"]["coverage_summary"] == "1 linked action remains open and 0 already resolved."
    assert body["runtime_signals"]["publicly_reachable"] is True
    assert body["code_context"]["repository_count"] == 1
    assert body["external_workflow_summary"]["drifted_count"] == 1
    assert body["evidence_exports"]["export_ready"] is True


def test_get_attack_path_allows_missing_owner_key(client: TestClient) -> None:
    action = _action()
    action.owner_key = None
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id

    session = MagicMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    actions_result = MagicMock()
    actions_result.scalars.return_value.all.return_value = [action]
    accounts_result = MagicMock()
    accounts_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(side_effect=[tenant_result, actions_result, accounts_result])

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
            "backend.routers.actions.get_materialized_attack_path",
            new=AsyncMock(
                return_value=(
                    {
                        "id": "path:ownerless",
                        "status": "available",
                        "rank": 50,
                        "confidence": 0.9,
                        "rank_factors": [],
                        "freshness": {"score": 0.98, "observed_at": "2026-03-12T12:00:00+00:00"},
                        "path_nodes": [],
                        "path_edges": [],
                        "entry_points": [],
                        "target_assets": [],
                        "business_impact": {"summary": "Business criticality is unknown for the linked action set.", "criticality_tier": "unknown", "criticality_score": 0},
                        "summary": "Business criticality is unknown for the linked action set.",
                        "risk_reasons": [],
                        "owners": [{"key": None, "label": "Unassigned"}],
                        "recommended_fix": {"summary": "Block public access on customer data bucket", "action_type": action.action_type},
                        "linked_actions": [{"id": str(action.id), "title": action.title, "priority": action.priority, "status": action.status, "owner_label": "Unassigned"}],
                        "evidence": [],
                        "provenance": [],
                        "linked_repositories": [],
                        "implementation_artifacts": [],
                        "truncated": False,
                        "availability_reason": None,
                        "computed_at": "2026-03-22T12:00:00+00:00",
                        "stale_after": "2026-03-22T12:05:00+00:00",
                        "is_stale": False,
                        "refresh_status": "ready",
                    },
                    False,
                )
            ),
        ):
            response = client.get("/api/actions/attack-paths/path:ownerless")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["owners"][0]["key"] is None
    assert body["owners"][0]["label"] == "Unassigned"


def test_enrich_attack_path_records_fail_closes_on_optional_loader_errors() -> None:
    action = _action()
    record = {
        "id": "path:abc123",
        "status": "available",
        "confidence": 0.92,
        "linked_actions": [{"id": str(action.id), "status": action.status}],
        "linked_action_ids": [str(action.id)],
        "representative_action": action,
        "representative_graph_context": _graph_context(),
        "evidence": [],
        "freshness": {"score": 0.98, "observed_at": "2026-03-12T12:00:00+00:00"},
        "rank_factors": [],
        "risk_reasons": [],
        "owners": [],
        "recommended_fix": {"summary": action.title, "action_type": action.action_type},
    }

    async def run() -> list[dict[str, object]]:
        with patch("backend.routers.actions._load_attack_path_exceptions", new=AsyncMock(side_effect=SQLAlchemyError("missing exceptions"))):
            with patch("backend.routers.actions._load_attack_path_runs", new=AsyncMock(side_effect=SQLAlchemyError("missing runs"))):
                with patch("backend.routers.actions._load_attack_path_sync_state", new=AsyncMock(side_effect=SQLAlchemyError("missing sync"))):
                    return await _enrich_attack_path_records(
                        MagicMock(),
                        tenant_uuid=uuid.uuid4(),
                        records=[record],
                        now=datetime.now(timezone.utc),
                    )

    enriched = asyncio.run(run())
    payload = enriched[0]
    assert payload["exception_summary"]["active_count"] == 0
    assert payload["external_workflow_summary"]["provider_count"] == 0
    assert payload["linked_repositories"] == []
    assert payload["implementation_artifacts"] == []
    assert payload["access_scope"]["scope"] == "tenant_scoped"


def test_build_shared_attack_path_records_groups_actions_and_keeps_explainable_rank_factors() -> None:
    action_one = _action()
    action_two = _action()
    action_two.id = uuid.uuid4()
    action_two.title = "Second linked action"
    action_two.priority = 72
    action_two.score = 72
    action_two.owner_label = "Platform Security"

    async def run() -> list[dict[str, object]]:
        with patch(
            "backend.services.attack_paths.build_attack_path_graph_context",
            new=AsyncMock(return_value={**_graph_context(), "path_signature": "path:shared"}),
        ):
            return await build_shared_attack_path_records(MagicMock(), tenant_id=uuid.uuid4(), actions=[action_one, action_two])

    records = asyncio.run(run())
    assert len(records) == 1
    record = records[0]
    assert record["id"] == "path:shared"
    assert sorted(record["linked_action_ids"]) == sorted([str(action_one.id), str(action_two.id)])
    factor_names = {item["name"] for item in record["rank_factors"]}
    assert "exploitability" in factor_names
    assert "compensating_controls" in factor_names
    assert "freshness_penalty" in factor_names
    assert "confidence_penalty" in factor_names
    assert record["remediation_summary"]["linked_actions_total"] == 2


def test_attack_path_action_scan_limit_bounds_unfiltered_list_requests() -> None:
    assert _attack_path_action_scan_limit(
        action_id=None,
        account_id=None,
        owner_key=None,
        resource_id=None,
        limit=50,
        offset=0,
    ) == 20


def test_attack_path_action_scan_limit_collapses_direct_lookups_to_one_action() -> None:
    assert _attack_path_action_scan_limit(
        action_id=str(uuid.uuid4()),
        account_id=None,
        owner_key=None,
        resource_id=None,
        limit=50,
        offset=0,
    ) == 1


def test_list_attack_paths_uses_materialized_read_model(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = tenant_id

    session = MagicMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    session.execute = AsyncMock(return_value=tenant_result)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        user = MagicMock()
        user.id = uuid.uuid4()
        user.tenant_id = tenant_id
        return user

    item = {
        "id": "path:materialized",
        "status": "available",
        "rank": 91,
        "confidence": 0.94,
        "entry_points": [{"node_id": "entry-1", "kind": "entry_point", "label": "Public exposure"}],
        "target_assets": [{"node_id": "target-1", "kind": "target_asset", "label": "prod-bucket"}],
        "summary": "Materialized shared attack path.",
        "business_impact_summary": "Critical customer-facing asset.",
        "recommended_fix_summary": "Block public access and rotate keys.",
        "owner_labels": ["Payments API"],
        "linked_action_ids": [str(uuid.uuid4())],
        "rank_factors": [
            {
                "name": "blast_radius",
                "label": "Blast radius",
                "direction": "positive",
                "score": 0.75,
                "weight": 0.2,
                "weighted_impact": 0.15,
                "explanation": "More linked actions broaden the path.",
            }
        ],
        "freshness": {"score": 0.9, "observed_at": "2026-03-22T12:00:00+00:00"},
        "remediation_summary": {"linked_actions_total": 1, "coverage_summary": "1 linked action remains open."},
        "runtime_signals": {
            "workload_presence": "present",
            "publicly_reachable": True,
            "sensitive_target_count": 1,
            "identity_hops": 1,
            "confidence": 0.94,
            "summary": "1 entry point informs this path.",
        },
        "closure_targets": {
            "open_action_ids": ["action-1"],
            "in_progress_action_ids": [],
            "resolved_action_ids": [],
            "summary": "1 open linked action remains.",
        },
        "governance_summary": {
            "provider_count": 1,
            "drifted_count": 0,
            "in_sync_count": 1,
            "linked_items": ["jira:SEC-1"],
            "summary": "Workflow links are aligned.",
        },
        "access_scope": {
            "scope": "tenant_scoped",
            "evidence_visibility": "full",
            "restricted_sections": [],
            "export_allowed": True,
        },
        "computed_at": "2026-03-22T12:00:00+00:00",
        "stale_after": "2026-03-22T12:05:00+00:00",
        "is_stale": True,
    }

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        with patch(
            "backend.routers.actions.list_materialized_attack_paths",
            new=AsyncMock(return_value=([item], 1, True)),
        ) as list_mock:
            with patch(
                "backend.routers.actions.maybe_schedule_attack_path_refresh",
                return_value=True,
            ) as schedule_mock:
                with patch(
                    "backend.routers.actions.build_shared_attack_path_records",
                    new=AsyncMock(side_effect=AssertionError("legacy builder should not run")),
                ):
                    response = client.get("/api/actions/attack-paths")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == "path:materialized"
    assert body["items"][0]["is_stale"] is True
    list_mock.assert_awaited_once()
    schedule_mock.assert_called_once()


def test_get_attack_path_bootstraps_materialized_model_when_empty(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = tenant_id

    session = MagicMock()
    tenant_result = MagicMock()
    tenant_result.scalar_one_or_none.return_value = tenant
    session.execute = AsyncMock(return_value=tenant_result)
    session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        user = MagicMock()
        user.id = uuid.uuid4()
        user.tenant_id = tenant_id
        return user

    detail_payload = {
        "id": "path:bootstrap",
        "status": "available",
        "rank": 88,
        "rank_factors": [],
        "confidence": 0.9,
        "freshness": {"score": 1.0, "observed_at": "2026-03-22T12:00:00+00:00"},
        "path_nodes": [],
        "path_edges": [],
        "entry_points": [],
        "target_assets": [],
        "summary": "Bootstrap materialized detail.",
        "business_impact": {"summary": "Critical", "criticality_tier": "critical", "matrix_position": None},
        "risk_reasons": [],
        "owners": [],
        "recommended_fix": {"summary": "Fix it", "strategy_key": None, "mode": None},
        "linked_actions": [],
        "evidence": [],
        "provenance": [],
        "remediation_summary": None,
        "runtime_signals": None,
        "exposure_validation": None,
        "code_context": None,
        "linked_repositories": [],
        "implementation_artifacts": [],
        "closure_targets": None,
        "external_workflow_summary": None,
        "exception_summary": None,
        "evidence_exports": None,
        "access_scope": None,
        "truncated": False,
        "availability_reason": None,
        "computed_at": "2026-03-22T12:00:00+00:00",
        "stale_after": "2026-03-22T12:05:00+00:00",
        "is_stale": False,
        "refresh_status": "ready",
    }

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        with patch(
            "backend.routers.actions.get_materialized_attack_path",
            new=AsyncMock(side_effect=[(None, False), (detail_payload, False)]),
        ) as get_mock:
            with patch(
                "backend.routers.actions.has_materialized_attack_paths",
                new=AsyncMock(return_value=False),
            ) as has_mock:
                with patch(
                    "backend.routers.actions.materialize_attack_paths",
                    new=AsyncMock(return_value={"paths_materialized": 1}),
                ) as materialize_mock:
                    response = client.get("/api/actions/attack-paths/path:bootstrap")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    assert response.json()["id"] == "path:bootstrap"
    assert get_mock.await_count == 2
    has_mock.assert_awaited_once()
    materialize_mock.assert_awaited_once()
    session.commit.assert_awaited_once()
