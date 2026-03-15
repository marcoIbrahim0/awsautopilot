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
    assert strategy["missing_defaults"] == []
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


def test_remediation_options_surface_real_ec2_53_profiles_and_tenant_recommendation(client: TestClient) -> None:
    tenant = _mock_tenant(
        {
            "sg_access_path_preference": "restrict_to_approved_admin_cidr",
            "approved_admin_cidrs": ["203.0.113.10/32"],
        }
    )
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
            "context": {"default_inputs": {"detected_public_ipv4_cidr": "198.51.100.15/32"}},
            "evidence": {
                "security_group_id": "sg-0123456789abcdef0",
                "public_admin_ipv4_ports": [22],
                "public_admin_ipv6_ports": [],
            },
        },
    ):
        try:
            response = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    strategy = next(
        item for item in response.json()["strategies"] if item["strategy_id"] == "sg_restrict_public_ports_guided"
    )
    assert [profile["profile_id"] for profile in strategy["profiles"]] == [
        "close_public",
        "close_and_revoke",
        "restrict_to_ip",
        "restrict_to_cidr",
        "ssm_only",
        "bastion_sg_reference",
    ]
    assert strategy["recommended_profile_id"] == "restrict_to_cidr"
    profile_map = {profile["profile_id"]: profile for profile in strategy["profiles"]}
    assert profile_map["restrict_to_cidr"]["recommended"] is True
    assert profile_map["restrict_to_cidr"]["support_tier"] == "deterministic_bundle"
    assert profile_map["restrict_to_ip"]["support_tier"] == "review_required_bundle"
    assert profile_map["ssm_only"]["support_tier"] == "manual_guidance_only"
    assert profile_map["bastion_sg_reference"]["support_tier"] == "manual_guidance_only"
    assert strategy["blocked_reasons"] == []
    assert "restrict_to_cidr" in strategy["decision_rationale"]


def test_remediation_preview_resolves_real_ec2_53_profile_from_legacy_access_mode(client: TestClient) -> None:
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
    assert body["resolution"]["profile_id"] == "close_and_revoke"
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
                    "profile_id": "close_public",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    assert response.json()["resolution"]["profile_id"] == "close_public"


def test_remediation_preview_downgrades_unsupported_ec2_53_profiles_explicitly(client: TestClient) -> None:
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
                    "profile_id": "ssm_only",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "ssm_only"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["blocked_reasons"] == [
        "Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented."
    ]


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
