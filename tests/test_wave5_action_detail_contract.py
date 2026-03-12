"""
Wave 5 contract/regression tests for Test 13 action detail behavior.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers.actions import _action_to_detail_response


def _make_action(*, description: str | None = "Risk details") -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.tenant_id = uuid.uuid4()
    action.action_type = "sg_restrict_public_ports"
    action.target_id = "target-1"
    action.account_id = "123456789012"
    action.region = "eu-north-1"
    action.score = 91
    action.score_components = {"severity": {"normalized": 1.0, "points": 35}, "score": 91}
    action.priority = 100
    action.status = "open"
    action.title = "Security group allows risky ingress"
    action.description = description
    action.control_id = "EC2.53"
    action.resource_id = "sg-123"
    action.resource_type = "AwsEc2SecurityGroup"
    action.created_at = datetime.now(timezone.utc)
    action.updated_at = datetime.now(timezone.utc)

    finding = MagicMock()
    finding.id = uuid.uuid4()
    finding.finding_id = "finding-1"
    finding.severity_label = "HIGH"
    finding.title = "Finding title"
    finding.resource_id = "sg-123"
    finding.account_id = "123456789012"
    finding.region = "eu-north-1"
    finding.updated_at = datetime.now(timezone.utc)

    link = MagicMock()
    link.finding = finding
    action.action_finding_links = [link]
    return action


def test_action_detail_contract_includes_explanation_fields() -> None:
    response = _action_to_detail_response(_make_action(description="Risk details"))
    assert response.score == 91
    assert response.score_components == {"severity": {"normalized": 1.0, "points": 35}, "score": 91}
    assert response.context_incomplete is True
    assert response.what_is_wrong == "Risk details"
    assert response.what_the_fix_does
    assert "security-group" in response.what_the_fix_does.lower()
    assert response.implementation_artifacts == []
    assert response.graph_context.status == "unavailable"
    assert response.graph_context.availability_reason == "relationship_context_unavailable"


def test_action_detail_contract_uses_title_fallback_when_description_missing() -> None:
    response = _action_to_detail_response(_make_action(description=None))
    assert response.what_is_wrong == "Security group allows risky ingress"
    assert response.what_the_fix_does


def test_get_action_requires_auth_without_tenant_context(client: TestClient) -> None:
    response = client.get(f"/api/actions/{uuid.uuid4()}")
    assert response.status_code == 401


def test_get_action_not_found_contract_with_authenticated_tenant(client: TestClient) -> None:
    tenant_id = uuid.uuid4()

    tenant_row = MagicMock()
    tenant_row.scalar_one_or_none.return_value = MagicMock()
    action_row = MagicMock()
    action_row.scalar_one_or_none.return_value = None

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[tenant_row, action_row])

    user = MagicMock()
    user.tenant_id = tenant_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(f"/api/actions/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "Action not found"
    assert "No action found with ID" in body["detail"]["detail"]
