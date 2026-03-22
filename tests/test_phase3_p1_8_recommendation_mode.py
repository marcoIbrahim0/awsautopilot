"""Phase 3 P1.8 recommendation-mode regression coverage."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.services.action_recommendation import build_action_recommendation


def _components(
    *,
    data_sensitivity: float,
    context_incomplete: bool = False,
    internet_exposure: float = 0.0,
    privilege_level: float = 0.0,
    exploit_signals: float = 0.0,
) -> dict[str, object]:
    return {
        "data_sensitivity": {"normalized": data_sensitivity, "points": 0},
        "internet_exposure": {"normalized": internet_exposure, "points": 0},
        "privilege_level": {"normalized": privilege_level, "points": 0},
        "exploit_signals": {"normalized": exploit_signals, "points": 0},
        "context_incomplete": context_incomplete,
        "score": 0,
    }


def _make_action(
    *,
    action_type: str = "custom_action",
    score: int,
    data_sensitivity: float,
    title: str = "Matrix recommendation test",
    description: str = "Recommendation derivation test action.",
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-1",
        severity_label="HIGH",
        title="Finding title",
        resource_id="resource-1",
        account_id="123456789012",
        region="us-east-1",
        updated_at=observed_at,
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type=action_type,
        target_id="target-1",
        account_id="123456789012",
        region="us-east-1",
        score=score,
        score_components=_components(data_sensitivity=data_sensitivity),
        priority=score,
        status="open",
        title=title,
        description=description,
        control_id="TEST.1",
        resource_id="resource-1",
        resource_type="AwsTestResource",
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
        created_at=observed_at,
        updated_at=observed_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _mock_async_session(*scalar_results: object) -> MagicMock:
    results: list[MagicMock] = []
    for value in scalar_results:
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    return user


@pytest.mark.parametrize(
    ("score", "data_sensitivity", "expected_cell", "expected_mode"),
    [
        (10, 0.10, "risk_low__criticality_low", "pr_only"),
        (50, 0.10, "risk_medium__criticality_low", "pr_only"),
        (85, 0.10, "risk_high__criticality_low", "pr_only"),
        (10, 0.55, "risk_low__criticality_medium", "pr_only"),
        (50, 0.55, "risk_medium__criticality_medium", "pr_only"),
        (85, 0.55, "risk_high__criticality_medium", "pr_only"),
        (10, 0.85, "risk_low__criticality_high", "pr_only"),
        (50, 0.85, "risk_medium__criticality_high", "pr_only"),
        (85, 0.85, "risk_high__criticality_high", "exception_review"),
    ],
)
def test_every_matrix_cell_maps_to_one_default_mode(
    score: int,
    data_sensitivity: float,
    expected_cell: str,
    expected_mode: str,
) -> None:
    action = _make_action(score=score, data_sensitivity=data_sensitivity)

    recommendation = build_action_recommendation(action)

    assert recommendation["matrix_position"]["cell"] == expected_cell
    assert recommendation["default_mode"] == expected_mode
    assert recommendation["mode"] == expected_mode
    assert recommendation["advisory"] is True
    assert recommendation["enforced_by_policy"] is None
    assert expected_cell in recommendation["rationale"]


def test_pr_only_recommendation_stays_advisory_when_pr_only_is_available() -> None:
    action = _make_action(score=10, data_sensitivity=0.10)

    recommendation = build_action_recommendation(action, mode_options=["pr_only"])

    assert recommendation["default_mode"] == "pr_only"
    assert recommendation["mode"] == "pr_only"
    assert recommendation["advisory"] is True
    assert recommendation["enforced_by_policy"] is None
    assert "PR-only" in recommendation["rationale"]


def test_manual_high_risk_policy_overrides_default_mode() -> None:
    action = _make_action(score=10, data_sensitivity=0.10)

    recommendation = build_action_recommendation(action, manual_high_risk=True)

    assert recommendation["default_mode"] == "pr_only"
    assert recommendation["mode"] == "exception_review"
    assert recommendation["advisory"] is False
    assert recommendation["enforced_by_policy"] == "manual_high_risk_root_credentials_required"
    assert "Policy override applied" in recommendation["rationale"]


def test_pr_only_policy_overrides_default_mode() -> None:
    action = _make_action(action_type="pr_only", score=10, data_sensitivity=0.10)

    recommendation = build_action_recommendation(action)

    assert recommendation["default_mode"] == "pr_only"
    assert recommendation["mode"] == "exception_review"
    assert recommendation["advisory"] is False
    assert recommendation["enforced_by_policy"] == "unsupported_pr_only_action"


def test_get_action_exposes_recommendation_payload(client: TestClient) -> None:
    action = _make_action(score=10, data_sensitivity=0.10)
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id
    account = MagicMock()
    account.tenant_id = tenant_id
    account.account_id = action.account_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return _mock_user(tenant_id)

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
                    new=AsyncMock(
                        return_value={
                            "status": "unavailable",
                            "availability_reason": "relationship_context_unavailable",
                            "source": "relationship_context",
                            "connected_assets": [],
                            "identity_path": [],
                            "blast_radius_neighborhood": [],
                            "truncated_sections": [],
                            "limits": {
                                "max_related_findings": 25,
                                "max_related_actions": 25,
                                "max_inventory_assets": 50,
                                "max_connected_assets": 10,
                                "max_identity_nodes": 10,
                                "max_blast_radius_neighbors": 10,
                            },
                        }
                    ),
                ):
                    response = client.get(f"/api/actions/{action.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["mode"] == "pr_only"
    assert body["recommendation"]["default_mode"] == "pr_only"
    assert body["recommendation"]["advisory"] is True
    assert body["recommendation"]["matrix_position"]["cell"] == "risk_low__criticality_low"
    assert "Criticality evidence" in body["recommendation"]["rationale"]


def test_remediation_options_exposes_policy_override_recommendation(client: TestClient) -> None:
    action = _make_action(
        action_type="iam_root_access_key_absent",
        score=10,
        data_sensitivity=0.10,
        title="Root access key should be removed",
        description="Manual root remediation flow",
    )
    tenant_id = action.tenant_id
    tenant = MagicMock()
    tenant.id = tenant_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return _mock_user(tenant_id)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["manual_high_risk"] is True
    assert body["recommendation"]["default_mode"] == "pr_only"
    assert body["recommendation"]["mode"] == "exception_review"
    assert body["recommendation"]["advisory"] is False
    assert body["recommendation"]["enforced_by_policy"] == "manual_high_risk_root_credentials_required"
    assert "Policy override applied" in body["recommendation"]["rationale"]
    assert "Policy override applied" in body["recommendation"]["rationale"]
