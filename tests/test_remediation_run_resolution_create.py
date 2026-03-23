from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.services.remediation_profile_resolver import RESOLVER_DECISION_VERSION_V1
from backend.utils.sqs import REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "resolver@example.com"
    return user


def _mock_tenant(remediation_settings: dict | None = None) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.remediation_settings = remediation_settings
    return tenant


def _mock_action(tenant_id: uuid.UUID, *, action_type: str) -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.tenant_id = tenant_id
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "us-east-1"
    action.target_id = "target-1"
    action.resource_id = "resource-1"
    return action


def _mock_account(role_write_arn: str | None = None) -> MagicMock:
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
        if isinstance(value, list):
            first = value[0] if value else None
            result.scalar_one_or_none.return_value = first
            result.scalars.return_value.first.return_value = first
            result.scalars.return_value.all.return_value = value
        else:
            result.scalar_one_or_none.return_value = value
            result.scalars.return_value.first.return_value = value
            result.scalars.return_value.all.return_value = [] if value is None else [value]
        result.scalar.return_value = value
        results.append(result)
    session = MagicMock()
    session.execute = AsyncMock(side_effect=results)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _install_refresh(session: MagicMock) -> None:
    async def _refresh(run_obj: MagicMock) -> None:
        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)


def _post_create(
    client: TestClient,
    session: MagicMock,
    user: MagicMock,
    payload: dict[str, object],
    *,
    runtime_signals: dict[str, object] | None = None,
    risk_snapshot: dict[str, object] | None = None,
    probe_result: tuple[bool | None, str | None] | None = None,
    direct_fix_types: set[str] | None = None,
) -> tuple[object, MagicMock]:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
    try:
        with ExitStack() as stack:
            mock_settings = stack.enter_context(patch("backend.routers.remediation_runs.settings"))
            mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
            stack.enter_context(patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs))
            if runtime_signals is not None:
                stack.enter_context(
                    patch("backend.routers.remediation_runs.collect_runtime_risk_signals", return_value=runtime_signals)
                )
            if risk_snapshot is not None:
                stack.enter_context(
                    patch("backend.routers.remediation_runs.evaluate_strategy_impact", return_value=risk_snapshot)
                )
            if probe_result is not None:
                stack.enter_context(
                    patch("backend.routers.remediation_runs.probe_direct_fix_permissions", return_value=probe_result)
                )
            if direct_fix_types is not None:
                stack.enter_context(
                    patch("backend.routers.remediation_runs.get_supported_direct_fix_action_types", return_value=direct_fix_types)
                )
            response = client.post("/api/remediation-runs", json=payload)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    return response, mock_sqs


def _added_run(session: MagicMock) -> MagicMock:
    return session.add.call_args.args[0]


def _queued_payload(mock_sqs: MagicMock) -> dict[str, object]:
    body = mock_sqs.send_message.call_args.kwargs["MessageBody"]
    return json.loads(body)


def test_pr_only_create_defaults_profile_id_to_strategy_id_and_persists_resolution(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_block_public_access")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_migrate_cloudfront_oac_private",
            "pr_bundle_variant": "cloudfront_oac_private_s3",
        },
        runtime_signals={
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": True,
            "evidence": {"existing_bucket_policy_statement_count": 0},
        },
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_migrate_cloudfront_oac_private"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["decision_version"] == RESOLVER_DECISION_VERSION_V1
    assert run.artifacts["selected_strategy"] == "s3_migrate_cloudfront_oac_private"
    assert run.artifacts["strategy_inputs"] == {
        "existing_bucket_policy_statement_count": 0,
    }
    assert run.artifacts["pr_bundle_variant"] == "cloudfront_oac_private_s3"
    payload = _queued_payload(mock_sqs)
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["resolution"] == resolution
    assert "profile_id" not in payload


def test_s3_2_create_downgrades_standard_strategy_to_manual_preservation_profile(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_block_public_access")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_bucket_block_public_access_standard",
        },
        runtime_signals={
            "s3_bucket_policy_public": True,
            "s3_bucket_website_configured": True,
            "access_path_evidence_available": True,
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "s3_website_enabled",
                    "status": "fail",
                    "message": "Bucket is currently serving traffic from S3 website hosting.",
                }
            ],
            "recommendation": "manual_review",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_bucket_block_public_access_manual_preservation"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["blocked_reasons"] == [
        "Bucket website hosting is enabled; use the manual preservation path before enforcing Block Public Access.",
        "Bucket policy is currently public; direct public-access preservation must be reviewed manually.",
    ]
    assert resolution["preservation_summary"]["manual_preservation_required"] is True
    assert _queued_payload(mock_sqs)["resolution"]["profile_id"] == resolution["profile_id"]


def test_s3_2_create_keeps_standard_strategy_executable_for_private_bucket_scope(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_block_public_access")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::safe-bucket|S3.2"
    action.resource_id = "arn:aws:s3:::safe-bucket"
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_bucket_block_public_access_standard",
        },
        runtime_signals={
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": True,
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "s3_public_access_dependency",
                    "status": "pass",
                    "message": "Runtime probes confirmed this bucket is private and not serving website traffic.",
                }
            ],
            "recommendation": "safe_to_proceed",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_bucket_block_public_access_standard"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_s3_5_create_requires_policy_preservation_evidence_before_executable_output(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_require_ssl")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enforce_ssl_strict_deny",
        },
        runtime_signals={
            "s3_policy_analysis_possible": True,
            "evidence": {"existing_bucket_policy_statement_count": 2},
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "existing_bucket_policy",
                    "status": "fail",
                    "message": "Bucket policy merge safety has not been proven.",
                }
            ],
            "recommendation": "manual_review",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enforce_ssl_strict_deny"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "Existing bucket policy statements were detected, but their JSON was not captured for safe merge.",
    ]
    assert resolution["preservation_summary"]["merge_safe_policy_available"] is False
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "review_required_bundle"


def test_s3_5_create_preserves_executable_support_tier_after_risk_acknowledgement(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_require_ssl")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::ssl-bucket|S3.5"
    action.resource_id = "arn:aws:s3:::ssl-bucket"
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enforce_ssl_strict_deny",
            "risk_acknowledged": True,
        },
        runtime_signals={
            "s3_policy_analysis_possible": True,
            "evidence": {
                "existing_bucket_policy_statement_count": 1,
                "existing_bucket_policy_json": json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "AllowTrustedRead",
                                "Effect": "Allow",
                                "Principal": {"AWS": "arn:aws:iam::123456789012:role/Reader"},
                                "Action": "s3:GetObject",
                                "Resource": "arn:aws:s3:::ssl-bucket/*",
                            }
                        ],
                    }
                ),
            },
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "s3_non_tls_client_breakage",
                    "status": "warn",
                    "message": "Non-TLS clients will fail after strict SSL enforcement.",
                },
                {
                    "code": "s3_policy_merge_risk",
                    "status": "warn",
                    "message": "Strict SSL enforcement can conflict with existing bucket policy statements.",
                },
            ],
            "recommendation": "review_and_acknowledge",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enforce_ssl_strict_deny"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_s3_11_create_requires_lifecycle_preservation_evidence_before_executable_output(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_lifecycle_configuration")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enable_abort_incomplete_uploads",
        },
        runtime_signals={
            "s3_lifecycle_analysis_possible": True,
            "evidence": {"existing_lifecycle_rule_count": 2},
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "existing_lifecycle_rules",
                    "status": "fail",
                    "message": "Lifecycle document must be reviewed before additive merge.",
                }
            ],
            "recommendation": "manual_review",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enable_abort_incomplete_uploads"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "Existing lifecycle rules were detected, but the lifecycle document was not captured for additive review.",
    ]
    assert resolution["preservation_summary"]["additive_merge_safe"] is False
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "review_required_bundle"


def test_s3_11_create_preserves_executable_support_tier_after_risk_acknowledgement(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_lifecycle_configuration")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::lifecycle-bucket|S3.11"
    action.resource_id = "arn:aws:s3:::lifecycle-bucket"
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enable_abort_incomplete_uploads",
            "risk_acknowledged": True,
        },
        runtime_signals={
            "s3_lifecycle_analysis_possible": True,
            "evidence": {"existing_lifecycle_rule_count": 0},
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "risk_evaluation_not_specialized",
                    "status": "unknown",
                    "message": "No specialized dependency checks are available for this strategy yet.",
                }
            ],
            "recommendation": "review_and_acknowledge",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enable_abort_incomplete_uploads"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_s3_9_create_stays_executable_only_when_destination_safety_is_proven(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_access_logging")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::source-bucket|S3.9"
    action.resource_id = "arn:aws:s3:::source-bucket"
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enable_access_logging_guided",
            "strategy_inputs": {"log_bucket_name": "dedicated-access-log-bucket"},
        },
        runtime_signals={
            "s3_access_logging_destination_safe": True,
            "s3_access_logging_destination_bucket_reachable": True,
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "s3_access_logging_bucket_scope_confirmed",
                    "status": "pass",
                    "message": "Bucket scope is confirmed.",
                },
                {
                    "code": "s3_access_logging_destination_safety_proven",
                    "status": "pass",
                    "message": "Destination safety is proven.",
                },
            ],
            "recommendation": "safe_to_proceed",
            "warnings": [],
            "evidence": {},
        },
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enable_access_logging_guided"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert resolution["preservation_summary"]["destination_safety_proven"] is True
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_s3_15_create_downgrades_customer_managed_branch_when_dependency_proof_is_missing(
    client: TestClient,
) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_encryption_kms")
    action.target_id = "123456789012|us-east-1|arn:aws:s3:::kms-bucket|S3.15"
    action.resource_id = "arn:aws:s3:::kms-bucket"
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_enable_sse_kms_guided",
            "strategy_inputs": {
                "kms_key_mode": "custom",
                "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
            },
        },
        runtime_signals={
            "s3_customer_kms_key_valid": True,
            "s3_customer_kms_dependency_proven": False,
            "s3_customer_kms_dependency_error": "Customer-managed KMS key policy/grant evidence is under-specified.",
            "evidence": {"customer_kms_grant_count": 0},
        },
        risk_snapshot={
            "checks": [
                {
                    "code": "s3_customer_kms_dependency_unproven",
                    "status": "fail",
                    "message": "Customer-managed KMS key policy/grant evidence is under-specified.",
                }
            ],
            "recommendation": "blocked",
            "warnings": [],
            "evidence": {},
        },
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_enable_sse_kms_customer_managed"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "Customer-managed KMS key policy/grant evidence is under-specified."
    ]
    assert run.artifacts["strategy_inputs"] == {
        "kms_key_mode": "custom",
        "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/custom-key-id",
    }
    assert _queued_payload(mock_sqs)["resolution"]["profile_id"] == "s3_enable_sse_kms_customer_managed"


def test_pr_only_create_preserves_profile_and_strategy_inputs_with_review_required_tier(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="aws_config_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "config_enable_centralized_delivery",
            "profile_id": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "risk_acknowledged": True,
        },
        runtime_signals={},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "config_enable_centralized_delivery"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["resolved_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "delivery_bucket": "central-config-bucket",
        "encrypt_with_kms": False,
    }
    assert resolution["blocked_reasons"] == [
        "AWS Config delivery bucket dependencies have not been proven from this account context."
    ]
    assert run.artifacts["selected_strategy"] == "config_enable_centralized_delivery"
    assert run.artifacts["strategy_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "delivery_bucket": "central-config-bucket",
        "encrypt_with_kms": False,
    }
    payload = _queued_payload(mock_sqs)
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["resolution"] == resolution
    assert "profile_id" not in payload


def test_cloudtrail_create_uses_tenant_bucket_default_when_runtime_proves_bucket(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant({"cloudtrail": {"default_bucket_name": "tenant-cloudtrail-logs"}})
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="cloudtrail_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "cloudtrail_enable_guided",
            "risk_acknowledged": True,
        },
        runtime_signals={"cloudtrail_log_bucket_reachable": True},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "cloudtrail_enable_guided"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["resolved_inputs"] == {
        "trail_name": "security-autopilot-trail",
        "trail_bucket_name": "tenant-cloudtrail-logs",
        "create_bucket_policy": True,
        "multi_region": True,
    }
    assert run.artifacts["strategy_inputs"] == {
        "trail_name": "security-autopilot-trail",
        "trail_bucket_name": "tenant-cloudtrail-logs",
        "create_bucket_policy": True,
        "multi_region": True,
    }
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_config_local_create_uses_tenant_defaults_and_stays_executable(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant(
        {
            "config": {
                "delivery_mode": "account_local_delivery",
                "default_bucket_name": "tenant-config-bucket",
            }
        }
    )
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="aws_config_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "config_enable_account_local_delivery",
            "risk_acknowledged": True,
        },
        runtime_signals={},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "config_enable_account_local_delivery"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["resolved_inputs"] == {
        "delivery_bucket": "tenant-config-bucket",
        "delivery_bucket_mode": "create_new",
    }
    assert run.artifacts["strategy_inputs"] == {
        "delivery_bucket": "tenant-config-bucket",
        "delivery_bucket_mode": "create_new",
    }
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_config_centralized_create_uses_tenant_defaults_when_runtime_proves_dependencies(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant(
        {
            "config": {
                "delivery_mode": "centralized_delivery",
                "default_bucket_name": "org-config-bucket",
                "default_kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/config",
            }
        }
    )
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="aws_config_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "config_enable_centralized_delivery",
            "risk_acknowledged": True,
        },
        runtime_signals={
            "config_delivery_bucket_reachable": True,
            "config_central_bucket_policy_valid": True,
            "config_kms_policy_valid": True,
        },
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "config_enable_centralized_delivery"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["resolved_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "existing_bucket_name": "org-config-bucket",
        "delivery_bucket": "org-config-bucket",
        "encrypt_with_kms": True,
        "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/config",
    }
    assert run.artifacts["strategy_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "existing_bucket_name": "org-config-bucket",
        "delivery_bucket": "org-config-bucket",
        "encrypt_with_kms": True,
        "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/config",
    }
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_pr_only_create_rejects_invalid_ec2_53_profile_id(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="sg_restrict_public_ports")
    session = _mock_async_session(tenant, action, None)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "sg_restrict_public_ports_guided",
            "profile_id": "not-a-real-profile",
        },
        runtime_signals={},
    )

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "Invalid profile_id"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_sqs.send_message.call_count == 0


def test_strategy_only_pr_only_client_still_succeeds_with_defaulted_inputs(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="cloudtrail_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, _ = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "cloudtrail_enable_guided",
            "risk_acknowledged": True,
        },
        runtime_signals={},
    )

    resolution = _added_run(session).artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "cloudtrail_enable_guided"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["resolved_inputs"] == {
        "trail_name": "security-autopilot-trail",
        "create_bucket_policy": True,
        "multi_region": True,
    }
    assert resolution["missing_defaults"] == ["cloudtrail.default_bucket_name"]
    assert resolution["blocked_reasons"] == [
        "CloudTrail log bucket name is unresolved. Configure cloudtrail.default_bucket_name or provide strategy_inputs.trail_bucket_name."
    ]


def test_cloudtrail_create_downgrades_under_proven_multi_region_override(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant({"cloudtrail": {"default_bucket_name": "tenant-cloudtrail-logs"}})
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="cloudtrail_enabled")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "cloudtrail_enable_guided",
            "strategy_inputs": {
                "multi_region": False,
            },
            "risk_acknowledged": True,
        },
        runtime_signals={"cloudtrail_log_bucket_reachable": True},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "cloudtrail_enable_guided"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["blocked_reasons"] == [
        "CloudTrail.1 multi-region coverage is under-proven when multi_region=false."
    ]
    assert run.artifacts["strategy_inputs"] == {
        "trail_name": "security-autopilot-trail",
        "trail_bucket_name": "tenant-cloudtrail-logs",
        "create_bucket_policy": True,
        "multi_region": False,
    }
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "review_required_bundle"


def test_ec2_53_strategy_only_create_persists_safe_resolved_profile(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="sg_restrict_public_ports")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "sg_restrict_public_ports_guided",
            "risk_acknowledged": True,
        },
        runtime_signals={
            "evidence": {
                "security_group_id": "sg-0123456789abcdef0",
                "public_admin_ipv4_ports": [22],
                "public_admin_ipv6_ports": [],
            }
        },
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "close_public"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert run.artifacts["strategy_inputs"] == {"access_mode": "close_public"}
    payload = _queued_payload(mock_sqs)
    assert payload["resolution"]["profile_id"] == "close_public"
    assert payload["resolution"]["support_tier"] == "deterministic_bundle"


def test_ec2_53_create_uses_tenant_cidr_preference_when_safe(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant(
        {
            "sg_access_path_preference": "restrict_to_approved_admin_cidr",
            "approved_admin_cidrs": ["203.0.113.10/32"],
        }
    )
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="sg_restrict_public_ports")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "sg_restrict_public_ports_guided",
            "risk_acknowledged": True,
        },
        runtime_signals={},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "restrict_to_cidr"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["resolved_inputs"]["allowed_cidr"] == "203.0.113.10/32"
    assert run.artifacts["strategy_inputs"] == {
        "access_mode": "restrict_to_cidr",
        "allowed_cidr": "203.0.113.10/32",
    }
    assert _queued_payload(mock_sqs)["resolution"]["profile_id"] == "restrict_to_cidr"
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "deterministic_bundle"


def test_ec2_53_create_downgrades_unsupported_profiles_explicitly(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="sg_restrict_public_ports")
    session = _mock_async_session(tenant, action, None, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "sg_restrict_public_ports_guided",
            "profile_id": "ssm_only",
            "risk_acknowledged": True,
        },
        runtime_signals={},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "ssm_only"
    assert resolution["support_tier"] == "manual_guidance_only"
    assert resolution["blocked_reasons"] == [
        "Wave 6 downgrades 'ssm_only' because SSM-only execution is not implemented."
    ]
    assert run.artifacts["strategy_inputs"] == {}
    assert _queued_payload(mock_sqs)["resolution"]["support_tier"] == "manual_guidance_only"


def test_direct_fix_create_is_rejected_as_out_of_scope(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = _mock_tenant()
    tenant.id = tenant_id
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_block_public_access")
    account = _mock_account("arn:aws:iam::123456789012:role/WriteRole")
    session = _mock_async_session(tenant, action, account, None)
    _install_refresh(session)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "direct_fix",
            "strategy_id": "s3_account_block_public_access_direct_fix",
            "risk_acknowledged": True,
        },
        probe_result=(True, None),
        direct_fix_types={"s3_block_public_access"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "Direct-fix out of scope"
    assert session.add.call_count == 0
    assert mock_sqs.send_message.call_count == 0
