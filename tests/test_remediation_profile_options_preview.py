from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.services.remediation_profile_resolver import RESOLVER_DECISION_VERSION_V1


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.tenant_id = tenant_id
    return user


def _mock_tenant(remediation_settings: dict | None = None) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.remediation_settings = remediation_settings
    return tenant


def _mock_action(action_type: str) -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.tenant_id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "us-east-1"
    return action


def _mock_account(role_write_arn: str | None = "arn:aws:iam::123456789012:role/WriteRole") -> MagicMock:
    account = MagicMock()
    account.account_id = "123456789012"
    account.role_read_arn = "arn:aws:iam::123456789012:role/ReadRole"
    account.role_write_arn = role_write_arn
    account.external_id = "ext-123"
    return account


def _mock_async_session(*scalar_results: object) -> MagicMock:
    results: list[MagicMock] = []
    for value in scalar_results:
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    return session


def test_remediation_options_include_wave2_profile_metadata(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_access_logging")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert "mode_options" in body
    assert "recommendation" in body
    assert body["strategies"]

    strategy = body["strategies"][0]
    assert strategy["strategy_id"] == "s3_enable_access_logging_guided"
    assert strategy["profiles"] == [
        {
            "profile_id": "s3_enable_access_logging_guided",
            "support_tier": "deterministic_bundle",
            "recommended": True,
            "requires_inputs": True,
            "supports_exception_flow": False,
            "exception_only": False,
        }
    ]
    assert strategy["recommended_profile_id"] == "s3_enable_access_logging_guided"
    assert strategy["missing_defaults"] == ["s3_access_logs.default_target_bucket_name"]
    assert strategy["blocked_reasons"] == []
    assert "decision_rationale" in strategy
    for existing_field in (
        "label",
        "mode",
        "risk_level",
        "requires_inputs",
        "input_schema",
        "dependency_checks",
        "warnings",
        "context",
    ):
        assert existing_field in strategy


def test_remediation_preview_defaults_profile_to_strategy_id(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("sg_restrict_public_ports")
    action.tenant_id = tenant.id
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch(
        "backend.routers.actions.collect_runtime_risk_signals",
        return_value={
            "evidence": {
                "security_group_id": "sg-0123456789abcdef0",
                "public_admin_ipv4_ports": [22],
                "public_admin_ipv6_ports": [],
            }
        },
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "sg_restrict_public_ports_guided",
                    "strategy_inputs": json.dumps({"access_mode": "close_and_revoke"}),
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    for existing_field in (
        "compliant",
        "message",
        "will_apply",
        "impact_summary",
        "before_state",
        "after_state",
        "diff_lines",
    ):
        assert existing_field in body
    assert body["resolution"]["strategy_id"] == "sg_restrict_public_ports_guided"
    assert body["resolution"]["profile_id"] == "sg_restrict_public_ports_guided"
    assert body["resolution"]["support_tier"] == "deterministic_bundle"
    assert body["resolution"]["decision_version"] == RESOLVER_DECISION_VERSION_V1


def test_remediation_preview_preserves_explicit_profile_id(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("sg_restrict_public_ports")
    action.tenant_id = tenant.id
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.actions.collect_runtime_risk_signals", return_value={}):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "sg_restrict_public_ports_guided",
                    "profile_id": "sg_restrict_public_ports_guided",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    assert response.json()["resolution"]["profile_id"] == "sg_restrict_public_ports_guided"


def test_remediation_preview_rejects_invalid_profile_id(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("sg_restrict_public_ports")
    action.tenant_id = tenant.id
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(
            f"/api/actions/{action.id}/remediation-preview",
            params={
                "mode": "pr_only",
                "strategy_id": "sg_restrict_public_ports_guided",
                "profile_id": "not-a-valid-profile",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "Invalid profile_id"


def test_direct_fix_preview_without_strategy_keeps_existing_behavior(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_block_public_access")
    action.tenant_id = tenant.id
    account = _mock_account()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    preview_result = MagicMock(
        compliant=False,
        message="S3 Block Public Access not configured; will enable.",
        will_apply=True,
        before_state={},
        after_state={},
        diff_lines=[],
    )

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.actions.assume_role", return_value=MagicMock()):
        with patch(
            "backend.routers.actions.run_remediation_preview_bridge",
            return_value=preview_result,
        ):
            try:
                response = client.get(
                    f"/api/actions/{action.id}/remediation-preview",
                    params={"mode": "direct_fix"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["compliant"] is False
    assert body["will_apply"] is True
    assert body["message"] == "S3 Block Public Access not configured; will enable."
    assert body["resolution"] is None
