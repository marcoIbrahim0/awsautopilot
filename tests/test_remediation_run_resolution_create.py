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
from backend.services.direct_fix_approval import DIRECT_FIX_APPROVAL_ARTIFACT_KEY
from backend.services.remediation_profile_resolver import RESOLVER_DECISION_VERSION_V1


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "resolver@example.com"
    return user


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
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_block_public_access")
    session = _mock_async_session(action, None, None)
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
        runtime_signals={"s3_bucket_policy_public": False, "s3_bucket_website_configured": False},
    )

    run = _added_run(session)
    resolution = run.artifacts["resolution"]
    assert response.status_code == 201
    assert resolution["profile_id"] == "s3_migrate_cloudfront_oac_private"
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["decision_version"] == RESOLVER_DECISION_VERSION_V1
    assert run.artifacts["selected_strategy"] == "s3_migrate_cloudfront_oac_private"
    assert run.artifacts["strategy_inputs"] == {}
    assert run.artifacts["pr_bundle_variant"] == "cloudfront_oac_private_s3"
    assert _queued_payload(mock_sqs)["schema_version"] == 1
    assert "profile_id" not in _queued_payload(mock_sqs)


def test_pr_only_create_preserves_profile_and_strategy_inputs_with_review_required_tier(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="aws_config_enabled")
    session = _mock_async_session(action, None, None)
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
    assert run.artifacts["selected_strategy"] == "config_enable_centralized_delivery"
    assert run.artifacts["strategy_inputs"] == {"delivery_bucket": "central-config-bucket"}
    assert _queued_payload(mock_sqs)["schema_version"] == 1
    assert "profile_id" not in _queued_payload(mock_sqs)


def test_pr_only_create_invalid_profile_id_returns_400(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_bucket_block_public_access")
    session = _mock_async_session(action, None)

    response, mock_sqs = _post_create(
        client,
        session,
        user,
        {
            "action_id": str(action.id),
            "mode": "pr_only",
            "strategy_id": "s3_migrate_cloudfront_oac_private",
            "profile_id": "not-a-real-profile",
        },
    )

    detail = response.json()["detail"]
    assert response.status_code == 400
    assert detail["error"] == "Invalid profile_id"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_sqs.send_message.call_count == 0


def test_strategy_only_pr_only_client_still_succeeds_with_defaulted_inputs(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="cloudtrail_enabled")
    session = _mock_async_session(action, None, None)
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


def test_direct_fix_create_remains_without_resolution_artifact(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    action = _mock_action(tenant_id, action_type="s3_block_public_access")
    account = _mock_account("arn:aws:iam::123456789012:role/WriteRole")
    session = _mock_async_session(action, account, None)
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

    run = _added_run(session)
    assert response.status_code == 201
    assert "resolution" not in run.artifacts
    assert DIRECT_FIX_APPROVAL_ARTIFACT_KEY in run.artifacts
    assert _queued_payload(mock_sqs)["schema_version"] == 1
    assert "profile_id" not in _queued_payload(mock_sqs)
