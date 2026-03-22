from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.database import get_db
from backend.main import app
from backend.services.remediation_profile_resolver import RESOLVER_DECISION_VERSION_V1
from backend.services.root_key_resolution_adapter import ROOT_KEY_EXECUTION_AUTHORITY_PATH


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
    action.target_id = "target-1"
    action.resource_id = "resource-1"
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
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9"
    action.resource_id = "arn:aws:s3:::source-bucket"

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch(
        "backend.routers.actions.collect_runtime_risk_signals",
        return_value={
            "s3_access_logging_destination_safe": True,
            "s3_access_logging_destination_bucket_reachable": True,
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
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
        },
        {
            "profile_id": "s3_enable_access_logging_review_destination_safety",
            "support_tier": "review_required_bundle",
            "recommended": False,
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


def test_s3_2_options_expose_manual_fallback_metadata_when_preservation_is_required(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_block_public_access")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch(
        "backend.routers.actions.collect_runtime_risk_signals",
        return_value={
            "s3_bucket_policy_public": True,
            "s3_bucket_website_configured": True,
            "access_path_evidence_available": True,
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    strategies = {item["strategy_id"]: item for item in response.json()["strategies"]}
    strategy = strategies["s3_bucket_block_public_access_standard"]
    assert strategy["recommended_profile_id"] == "s3_bucket_block_public_access_manual_preservation"
    assert strategy["blocked_reasons"] == [
        "Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access.",
        "Bucket policy is currently public; direct public-access preservation must be reviewed manually.",
    ]
    assert strategy["preservation_summary"] == {
        "single_profile_compatible": False,
        "strategy_only_supported": True,
        "family": "s3_bucket_block_public_access",
        "selected_branch": "s3_bucket_block_public_access_manual_preservation",
        "bucket_policy_public": True,
        "website_configured": True,
        "existing_bucket_policy_statement_count": None,
        "existing_bucket_policy_json_captured": False,
        "access_path_evidence_available": True,
        "executable_preservation_allowed": False,
        "manual_preservation_required": True,
        "family_strategy": "s3_bucket_block_public_access_standard",
    }
    profile_map = {profile["profile_id"]: profile for profile in strategy["profiles"]}
    assert profile_map["s3_bucket_block_public_access_standard"]["support_tier"] == "manual_guidance_only"
    assert profile_map["s3_bucket_block_public_access_manual_preservation"]["recommended"] is True
    assert profile_map["s3_bucket_block_public_access_manual_preservation"]["support_tier"] == "manual_guidance_only"


def test_s3_2_preview_keeps_legacy_oac_strategy_compatible_but_downgrades_without_preservation_evidence(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_block_public_access")
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
            "access_path_evidence_available": True,
            "evidence": {"existing_bucket_policy_statement_count": 2},
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_migrate_cloudfront_oac_private",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["strategy_id"] == "s3_migrate_cloudfront_oac_private"
    assert resolution["profile_id"] == "s3_migrate_cloudfront_oac_private_manual_preservation"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["blocked_reasons"] == [
        "Existing bucket policy statements were detected, but their JSON was not captured for safe preservation."
    ]
    assert resolution["rejected_profiles"] == [
        {
            "profile_id": "s3_migrate_cloudfront_oac_private",
            "reason": "branch_unavailable",
            "detail": "Existing bucket policy statements were detected, but their JSON was not captured for safe preservation.",
        }
    ]
    assert resolution["preservation_summary"]["existing_bucket_policy_json_captured"] is False
    assert resolution["preservation_summary"]["manual_preservation_required"] is True


def test_s3_2_preview_keeps_standard_strategy_executable_when_bucket_is_private_and_website_disabled(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_block_public_access")
    action.tenant_id = tenant.id
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
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
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": True,
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_bucket_block_public_access_standard",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_bucket_block_public_access_standard"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert resolution["preservation_summary"]["executable_preservation_allowed"] is True


def test_s3_9_options_recommend_review_branch_when_destination_safety_is_not_proven(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_access_logging")
    action.tenant_id = tenant.id
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9"
    action.resource_id = "arn:aws:s3:::source-bucket"

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch(
        "backend.routers.actions.collect_runtime_risk_signals",
        return_value={
            "s3_access_logging_destination_safe": False,
            "s3_access_logging_destination_bucket_reachable": False,
            "s3_access_logging_destination_safety_reason": (
                "Destination log bucket 'security-autopilot-access-logs-123456789012' could not be verified "
                "from this account context (AccessDenied)."
            ),
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    strategy = next(
        item for item in response.json()["strategies"] if item["strategy_id"] == "s3_enable_access_logging_guided"
    )
    assert strategy["recommended_profile_id"] == "s3_enable_access_logging_review_destination_safety"
    assert strategy["blocked_reasons"] == [
        "Destination log bucket 'security-autopilot-access-logs-123456789012' could not be verified from this account context (AccessDenied)."
    ]
    profile_map = {profile["profile_id"]: profile for profile in strategy["profiles"]}
    assert profile_map["s3_enable_access_logging_guided"]["support_tier"] == "review_required_bundle"
    assert profile_map["s3_enable_access_logging_review_destination_safety"]["recommended"] is True
    assert strategy["preservation_summary"]["destination_safety_proven"] is False


def test_s3_15_preview_switches_to_customer_managed_profile_and_downgrades_without_dependency_proof(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_encryption_kms")
    action.tenant_id = tenant.id
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15"
    action.resource_id = "arn:aws:s3:::kms-bucket"
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
            "s3_customer_kms_key_valid": True,
            "s3_customer_kms_dependency_proven": False,
            "s3_customer_kms_dependency_error": "Customer-managed KMS key policy/grant evidence is under-specified.",
            "context": {"kms_key_options": []},
            "evidence": {"customer_kms_grant_count": 0},
        },
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_enable_sse_kms_guided",
                    "strategy_inputs": json.dumps(
                        {
                            "kms_key_mode": "custom",
                            "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
                        }
                    ),
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_enable_sse_kms_customer_managed"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["resolved_inputs"]["kms_key_mode"] == "custom"
    assert resolution["blocked_reasons"] == [
        "Customer-managed KMS key policy/grant evidence is under-specified."
    ]
    assert resolution["preservation_summary"]["kms_key_mode"] == "custom"
    assert resolution["preservation_summary"]["customer_managed_dependency_proven"] is False


def test_s3_15_preview_keeps_aws_managed_branch_executable_by_default(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_encryption_kms")
    action.tenant_id = tenant.id
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15"
    action.resource_id = "arn:aws:s3:::kms-bucket"
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
        return_value={"context": {"kms_key_options": []}},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_enable_sse_kms_guided",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_enable_sse_kms_guided"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert resolution["resolved_inputs"]["kms_key_mode"] == "aws_managed"


def test_s3_15_preview_customer_profile_surfaces_missing_defaults_when_key_arn_is_unset(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_encryption_kms")
    action.tenant_id = tenant.id
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15"
    action.resource_id = "arn:aws:s3:::kms-bucket"
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
            "s3_customer_kms_dependency_proven": False,
            "s3_customer_kms_dependency_error": "Customer-managed KMS branch requires an approved kms_key_arn.",
            "context": {"kms_key_options": []},
        },
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_enable_sse_kms_guided",
                    "profile_id": "s3_enable_sse_kms_customer_managed",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_enable_sse_kms_customer_managed"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["missing_inputs"] == ["kms_key_arn"]
    assert resolution["missing_defaults"] == ["s3_encryption.kms_key_arn"]
    assert resolution["blocked_reasons"] == ["Customer-managed KMS branch requires an approved kms_key_arn."]


def test_s3_5_preview_requires_policy_preservation_evidence_for_executable_output(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_require_ssl")
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
            "s3_policy_analysis_possible": True,
            "evidence": {"existing_bucket_policy_statement_count": 2},
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_enforce_ssl_strict_deny",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_enforce_ssl_strict_deny"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "Existing bucket policy statements were detected, but their JSON was not captured for safe merge."
    ]
    assert resolution["preservation_summary"]["merge_safe_policy_available"] is False
    assert resolution["preservation_summary"]["executable_policy_merge_allowed"] is False


def test_s3_11_preview_requires_lifecycle_document_capture_for_existing_rules(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("s3_bucket_lifecycle_configuration")
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
            "s3_lifecycle_analysis_possible": True,
            "evidence": {"existing_lifecycle_rule_count": 2},
        },
    ), patch(
        "backend.routers.actions.evaluate_strategy_impact",
        return_value={"checks": [], "warnings": [], "recommendation": None, "evidence": {}},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "s3_enable_abort_incomplete_uploads",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "s3_enable_abort_incomplete_uploads"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "Existing lifecycle rules were detected, but the lifecycle document was not captured for additive review."
    ]
    assert resolution["preservation_summary"]["existing_lifecycle_configuration_captured"] is False
    assert resolution["preservation_summary"]["additive_merge_safe"] is False


def test_cloudtrail_options_use_tenant_defaults_and_downgrade_kms_branch(client: TestClient) -> None:
    tenant = _mock_tenant(
        {
            "cloudtrail": {
                "default_bucket_name": "tenant-cloudtrail-logs",
                "default_kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/cloudtrail",
            }
        }
    )
    user = _mock_user(tenant.id)
    action = _mock_action("cloudtrail_enabled")
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
        return_value={"cloudtrail_log_bucket_reachable": True},
    ):
        try:
            response = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    strategy = next(
        item for item in response.json()["strategies"] if item["strategy_id"] == "cloudtrail_enable_guided"
    )
    assert strategy["recommended_profile_id"] == "cloudtrail_enable_guided"
    assert strategy["profiles"] == [
        {
            "profile_id": "cloudtrail_enable_guided",
            "support_tier": "review_required_bundle",
            "recommended": True,
            "requires_inputs": True,
            "supports_exception_flow": False,
            "exception_only": False,
        }
    ]
    assert strategy["missing_defaults"] == []
    assert strategy["blocked_reasons"] == [
        "CloudTrail KMS-encrypted delivery is review-only until KMS dependency proof is implemented."
    ]
    assert strategy["preservation_summary"]["trail_bucket_name_resolved"] is True
    assert strategy["preservation_summary"]["log_bucket_reachable"] is True
    assert strategy["preservation_summary"]["kms_delivery_requested"] is True


def test_cloudtrail_preview_uses_tenant_bucket_default_when_bucket_is_proven(client: TestClient) -> None:
    tenant = _mock_tenant({"cloudtrail": {"default_bucket_name": "tenant-cloudtrail-logs"}})
    user = _mock_user(tenant.id)
    action = _mock_action("cloudtrail_enabled")
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
        return_value={"cloudtrail_log_bucket_reachable": True},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={"mode": "pr_only", "strategy_id": "cloudtrail_enable_guided"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["profile_id"] == "cloudtrail_enable_guided"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["resolved_inputs"] == {
        "trail_name": "security-autopilot-trail",
        "trail_bucket_name": "tenant-cloudtrail-logs",
        "create_bucket_policy": True,
        "multi_region": True,
    }
    assert resolution["blocked_reasons"] == []


def test_config_options_honor_delivery_mode_preference_for_recommendation(client: TestClient) -> None:
    tenant = _mock_tenant(
        {
            "config": {
                "delivery_mode": "centralized_delivery",
                "default_bucket_name": "org-config-bucket",
            }
        }
    )
    user = _mock_user(tenant.id)
    action = _mock_action("aws_config_enabled")
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
            "config_delivery_bucket_reachable": True,
            "config_central_bucket_policy_valid": True,
        },
    ):
        try:
            response = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    strategies = {item["strategy_id"]: item for item in response.json()["strategies"]}
    assert strategies["config_enable_account_local_delivery"]["recommended"] is False
    assert strategies["config_enable_centralized_delivery"]["recommended"] is True
    assert strategies["config_enable_centralized_delivery"]["profiles"] == [
        {
            "profile_id": "config_enable_centralized_delivery",
            "support_tier": "deterministic_bundle",
            "recommended": True,
            "requires_inputs": True,
            "supports_exception_flow": False,
            "exception_only": False,
        }
    ]


def test_config_preview_uses_tenant_defaults_and_downgrades_unproven_centralized_branch(client: TestClient) -> None:
    tenant = _mock_tenant(
        {
            "config": {
                "delivery_mode": "centralized_delivery",
                "default_bucket_name": "org-config-bucket",
                "default_kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/config",
            }
        }
    )
    user = _mock_user(tenant.id)
    action = _mock_action("aws_config_enabled")
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
            "config_delivery_bucket_reachable": False,
            "config_delivery_bucket_error": "HeadBucketFailed",
            "config_central_bucket_policy_valid": False,
            "config_central_bucket_policy_error": "Centralized delivery bucket access is denied for this account context.",
            "config_kms_policy_valid": False,
            "config_kms_policy_error": "DescribeKeyFailed",
        },
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={"mode": "pr_only", "strategy_id": "config_enable_centralized_delivery"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    resolution = body["resolution"]
    assert resolution["profile_id"] == "config_enable_centralized_delivery"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["resolved_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "existing_bucket_name": "org-config-bucket",
        "delivery_bucket": "org-config-bucket",
        "encrypt_with_kms": True,
        "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/config",
    }
    assert resolution["blocked_reasons"] == [
        "HeadBucketFailed",
        "Centralized delivery bucket access is denied for this account context.",
        "DescribeKeyFailed",
    ]
    assert body["after_state"]["delivery_bucket"] == "org-config-bucket"
    assert body["impact_summary"] is None


def test_iam_4_options_expose_guidance_only_profile_metadata(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("iam_root_access_key_absent")
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
    strategies = {item["strategy_id"]: item for item in response.json()["strategies"]}
    assert set(strategies) >= {
        "iam_root_key_disable",
        "iam_root_key_delete",
        "iam_root_key_keep_exception",
    }
    for strategy_id in (
        "iam_root_key_disable",
        "iam_root_key_delete",
        "iam_root_key_keep_exception",
    ):
        strategy = strategies[strategy_id]
        assert strategy["recommended_profile_id"] == strategy_id
        assert strategy["profiles"] == [
            {
                "profile_id": strategy_id,
                "support_tier": "manual_guidance_only",
                "recommended": True,
                "requires_inputs": strategy["requires_inputs"],
                "supports_exception_flow": strategy["supports_exception_flow"],
                "exception_only": strategy["exception_only"],
            }
        ]
        assert strategy["blocked_reasons"] == [
            "IAM.4 execution is handled exclusively by /api/root-key-remediation-runs."
        ]
        assert ROOT_KEY_EXECUTION_AUTHORITY_PATH in strategy["decision_rationale"]


def test_iam_4_preview_returns_guidance_only_resolution_metadata(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("iam_root_access_key_absent")
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
        return_value={"iam_root_account_mfa_enrolled": True},
    ):
        try:
            response = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "strategy_id": "iam_root_key_delete",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    resolution = response.json()["resolution"]
    assert resolution["strategy_id"] == "iam_root_key_delete"
    assert resolution["profile_id"] == "iam_root_key_delete"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["blocked_reasons"] == [
        "IAM.4 execution is handled exclusively by /api/root-key-remediation-runs."
    ]
    assert resolution["preservation_summary"] == {
        "single_profile_compatible": True,
        "strategy_only_supported": True,
        "guidance_only": True,
        "generic_execution_allowed": False,
        "execution_authority": ROOT_KEY_EXECUTION_AUTHORITY_PATH,
        "runbook_url": "docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md",
    }
    assert ROOT_KEY_EXECUTION_AUTHORITY_PATH in resolution["decision_rationale"]
    assert resolution["decision_version"] == RESOLVER_DECISION_VERSION_V1


def test_direct_fix_preview_without_strategy_returns_out_of_scope_message(client: TestClient) -> None:
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

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
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
    assert body["will_apply"] is False
    assert "out of scope" in body["message"].lower()
    assert body["resolution"] is None
