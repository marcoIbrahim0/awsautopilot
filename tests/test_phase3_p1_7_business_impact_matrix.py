"""Phase 3 P1.7 business-impact matrix coverage."""
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
from backend.routers.actions import (
    _action_to_detail_response,
    _action_to_list_item,
    _business_impact_rank_value,
)
from backend.services.action_business_impact import build_business_impact_for_finding
from backend.services.action_scoring import score_action_finding


def _finding(
    *,
    control_id: str = "S3.2",
    severity_normalized: int = 75,
    severity_label: str = "HIGH",
    title: str = "Bucket is publicly accessible from 0.0.0.0/0",
    description: str = "Public read access is enabled for this bucket.",
    finding_id: str = "finding-1",
    resource_id: str = "arn:aws:s3:::archive-bucket",
    resource_type: str = "AwsS3Bucket",
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc)
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
        raw_json={},
        account_id="123456789012",
        region="us-east-1",
        updated_at=observed_at,
        created_at=observed_at,
        sh_updated_at=observed_at,
        last_observed_at=observed_at,
    )


def _action_from_finding(finding: SimpleNamespace) -> SimpleNamespace:
    score = score_action_finding(finding)
    components = dict(score.components)
    components["business_impact"] = build_business_impact_for_finding(finding, technical_score=score.score)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type="s3_bucket_block_public_access",
        target_id=f"123456789012|us-east-1|{finding.resource_id}|{finding.control_id}",
        account_id="123456789012",
        region="us-east-1",
        score=score.score,
        score_components=components,
        priority=score.score,
        status="open",
        title=finding.title,
        description=finding.description,
        control_id=finding.control_id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        owner_type="unassigned",
        owner_key="unassigned",
        owner_label="Unassigned",
        updated_at=finding.updated_at,
        created_at=finding.created_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _rows_result(rows: list[object]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    return user


def test_business_impact_matrix_is_deterministic_and_explicit_when_criticality_is_missing() -> None:
    finding = _finding()
    score = score_action_finding(finding)

    first = build_business_impact_for_finding(finding, technical_score=score.score)
    second = build_business_impact_for_finding(finding, technical_score=score.score)

    assert first == second
    assert first["criticality"]["status"] == "unknown"
    assert first["criticality"]["tier"] == "unknown"
    assert first["matrix_position"]["cell"] == "high:unknown"
    assert "explicit unknown criticality" in first["summary"].lower()


def test_business_impact_payload_is_present_in_list_and_detail_contracts() -> None:
    finding = _finding(
        title="Customer portal billing API bucket is publicly accessible from 0.0.0.0/0",
        description="Supports customer checkout and subscription workflows.",
        finding_id="finding-business-critical",
    )
    action = _action_from_finding(finding)

    list_item = _action_to_list_item(action)
    detail_item = _action_to_detail_response(action)

    assert list_item.business_impact.matrix_position.cell == "high:high"
    assert detail_item.business_impact.matrix_position.cell == "high:high"
    assert list_item.business_impact.criticality.status == "known"
    assert detail_item.business_impact.criticality.score >= 40


def test_criticality_changes_rerank_actions_with_same_technical_score() -> None:
    unknown_action = _action_from_finding(_finding())
    known_action = _action_from_finding(
        _finding(
            title="Customer portal billing API bucket is publicly accessible from 0.0.0.0/0",
            description="Supports customer checkout and subscription workflows.",
            finding_id="finding-ranked",
        )
    )

    assert unknown_action.score == known_action.score
    assert _business_impact_rank_value(known_action) > _business_impact_rank_value(unknown_action)


def test_actions_list_api_exposes_business_impact_fields_and_matrix_ordering(client: TestClient) -> None:
    high_impact = _action_from_finding(
        _finding(
            title="Customer portal billing API bucket is publicly accessible from 0.0.0.0/0",
            description="Supports customer checkout and subscription workflows.",
            finding_id="finding-high-impact",
        )
    )
    low_impact = _action_from_finding(_finding(finding_id="finding-low-impact"))
    tenant_id = high_impact.tenant_id
    low_impact.tenant_id = tenant_id
    executed_sql: list[str] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        executed_sql.append(str(statement))
        if len(executed_sql) == 1:
            result = MagicMock()
            result.scalar.return_value = 2
            return result
        return _rows_result([(high_impact, 1), (low_impact, 1)])

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return _mock_user(tenant_id)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
            with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
                with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                    response = client.get("/api/actions")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["business_impact"]["matrix_position"]["cell"] == "high:high"
    assert body["items"][1]["business_impact"]["criticality"]["status"] == "unknown"
    assert body["items"][0]["business_impact"]["matrix_position"]["rank"] > body["items"][1]["business_impact"]["matrix_position"]["rank"]


def test_action_detail_api_exposes_matrix_position_and_unknown_criticality(client: TestClient) -> None:
    action = _action_from_finding(_finding())
    tenant_id = action.tenant_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = MagicMock()
        session.execute = AsyncMock(side_effect=[_scalar_result(action), _scalar_result(None)])
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return _mock_user(tenant_id)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_state_for_response", new=AsyncMock(return_value={})):
                with patch("backend.routers.actions._load_action_implementation_artifacts", new=AsyncMock(return_value=[])):
                    with patch(
                        "backend.routers.actions._load_action_graph_context",
                        new=AsyncMock(return_value=actions_router._default_graph_context_payload()),
                    ):
                        response = client.get(f"/api/actions/{action.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["business_impact"]["criticality"]["status"] == "unknown"
    assert body["business_impact"]["matrix_position"]["cell"] == "high:unknown"
    assert "explicit unknown criticality" in body["business_impact"]["summary"].lower()
