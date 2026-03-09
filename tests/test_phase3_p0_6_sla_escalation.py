"""Phase 3 P0.6 tests for SLA windows and escalation hooks."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.routers import actions as actions_router
from backend.services.action_sla import build_action_escalation_context, compute_action_sla


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    user.id = uuid.uuid4()
    return user


def _mock_action(
    *,
    tenant_id: uuid.UUID,
    created_at: datetime,
    owner_type: str = "team",
    owner_key: str = "platform-team",
    owner_label: str = "Platform Team",
    score: int = 80,
    status: str = "open",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        tenant_id=tenant_id,
        action_type="s3_bucket_block_public_access",
        target_id="target-1",
        account_id="029037611564",
        region="eu-north-1",
        score=score,
        score_components={"severity": {"normalized": 0.75, "points": 26}, "score": score},
        priority=score,
        status=status,
        title="S3 bucket should block public access",
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-data",
        resource_type="AwsS3Bucket",
        owner_type=owner_type,
        owner_key=owner_key,
        owner_label=owner_label,
        created_at=created_at,
        updated_at=created_at + timedelta(hours=1),
        action_finding_links=[],
    )


def test_compute_action_sla_is_deterministic_for_expiring_and_overdue_states() -> None:
    created_at = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

    expiring = compute_action_sla(
        created_at=created_at,
        score=95,
        now=datetime(2026, 3, 1, 18, 0, tzinfo=timezone.utc),
    )
    assert expiring is not None
    assert expiring.risk_tier == "critical"
    assert expiring.due_in_hours == 24
    assert expiring.expiring_in_hours == 8
    assert expiring.due_at.isoformat() == "2026-03-02T00:00:00+00:00"
    assert expiring.expiring_at.isoformat() == "2026-03-01T16:00:00+00:00"
    assert expiring.state == "expiring"
    assert expiring.hours_until_due == 6
    assert expiring.escalation_eligible is True
    assert expiring.escalation_level == "warning"

    overdue = compute_action_sla(
        created_at=created_at,
        score=95,
        now=datetime(2026, 3, 2, 1, 0, tzinfo=timezone.utc),
    )
    assert overdue is not None
    assert overdue.state == "overdue"
    assert overdue.hours_overdue == 1
    assert overdue.escalation_level == "breach"


def test_escalation_context_only_applies_to_high_impact_actions_without_exception() -> None:
    created_at = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc)

    medium_context = build_action_escalation_context(
        action_id=uuid.uuid4(),
        action_type="cloudtrail_enabled",
        title="Enable CloudTrail",
        owner_type="service",
        owner_key="cloudtrail",
        owner_label="AWS CloudTrail",
        created_at=created_at,
        score=55,
        now=now,
        has_active_exception=False,
    )
    assert medium_context is None

    blocked_context = build_action_escalation_context(
        action_id=uuid.uuid4(),
        action_type="s3_bucket_block_public_access",
        title="Block S3 bucket public access",
        owner_type="team",
        owner_key="platform-team",
        owner_label="Platform Team",
        created_at=created_at,
        score=80,
        now=now,
        has_active_exception=True,
    )
    assert blocked_context is None

    high_context = build_action_escalation_context(
        action_id=uuid.UUID("00000000-0000-0000-0000-000000000099"),
        action_type="s3_bucket_block_public_access",
        title="Block S3 bucket public access",
        owner_type="team",
        owner_key="platform-team",
        owner_label="Platform Team",
        created_at=created_at,
        score=80,
        now=datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc),
        has_active_exception=False,
    )
    assert high_context is not None
    assert high_context["risk_tier"] == "high"
    assert high_context["sla_state"] == "overdue"
    assert high_context["owner_label"] == "Platform Team"
    assert high_context["escalation_level"] == "breach"


def test_actions_owner_queue_response_includes_sla_counters_and_item_state(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    fixed_now = datetime(2026, 3, 10, 0, 0, tzinfo=timezone.utc)
    action = _mock_action(
        tenant_id=tenant_id,
        created_at=fixed_now - timedelta(hours=50),
        score=80,
    )

    counter_result = MagicMock()
    counter_result.one.return_value = SimpleNamespace(
        open=4,
        expiring=1,
        overdue=2,
        blocked_fixes=1,
        expiring_exceptions=1,
    )
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    list_result = MagicMock()
    list_result.all.return_value = [(action, 1)]

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[counter_result, count_result, list_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch.object(actions_router.settings, "ACTIONS_EFFECTIVE_OPEN_VISIBILITY_ENABLED", False):
        with patch("backend.routers.actions.get_tenant", new=AsyncMock(return_value=MagicMock())):
            with patch("backend.routers.actions.get_exception_states_for_entities", new=AsyncMock(return_value={})):
                with patch.object(actions_router, "datetime", _FixedDateTime):
                    response = client.get(
                        "/api/actions",
                        params={
                            "owner_type": "team",
                            "owner_key": "platform-team",
                            "owner_queue": "expiring",
                        },
                    )

    assert response.status_code == 200
    body = response.json()
    assert body["owner_queue_counters"] == {
        "open": 4,
        "expiring": 1,
        "overdue": 2,
        "blocked_fixes": 1,
        "expiring_exceptions": 1,
    }
    assert body["items"][0]["sla"]["risk_tier"] == "high"
    assert body["items"][0]["sla"]["state"] == "expiring"
    assert body["items"][0]["sla"]["due_at"] == "2026-03-10T22:00:00+00:00"
