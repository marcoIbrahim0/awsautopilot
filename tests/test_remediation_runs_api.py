"""
Unit tests for remediation runs API (Step 7.2 + 8.4).

Covers: POST create run (approval, direct_fix validation), GET remediation-preview.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import (
    RemediationRunExecutionPhase,
    RemediationRunExecutionStatus,
    RemediationRunMode,
    RemediationRunStatus,
)


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    u = MagicMock()
    u.id = uuid.uuid4()
    u.tenant_id = tenant_id
    u.email = "user@example.com"
    return u


def _mock_action(action_type: str = "s3_block_public_access") -> MagicMock:
    a = MagicMock()
    a.id = uuid.uuid4()
    a.tenant_id = uuid.uuid4()
    a.action_type = action_type
    a.account_id = "123456789012"
    a.region = None if action_type == "s3_block_public_access" else "us-east-1"
    return a


def _mock_account(role_write_arn: str | None) -> MagicMock:
    acc = MagicMock()
    acc.role_write_arn = role_write_arn
    acc.external_id = "ext-123"
    return acc


def _mock_tenant() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    return t


def _mock_async_session(*scalar_results: object) -> MagicMock:
    """Mock AsyncSession with execute returning results in order."""
    result = MagicMock()
    result.scalar_one_or_none.side_effect = list(scalar_results)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# POST create_remediation_run - direct_fix validation (8.4)
# ---------------------------------------------------------------------------


def test_create_direct_fix_action_not_fixable_400(client: TestClient) -> None:
    """direct_fix with action_type=pr_only returns 400 Action not fixable."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="pr_only")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={"action_id": str(action.id), "mode": "direct_fix"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    data = r.json()
    err = data.get("detail", {})
    if isinstance(err, dict):
        err = err.get("error", "")
    assert "not fixable" in str(err).lower() or "fixable" in str(err).lower()


def test_create_direct_fix_no_write_role_400(client: TestClient) -> None:
    """direct_fix with account lacking WriteRole returns 400."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_block_public_access")
    account = _mock_account(role_write_arn=None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, account, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={"action_id": str(action.id), "mode": "direct_fix"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    data = r.json()
    err = data.get("detail", {})
    if isinstance(err, dict):
        err = err.get("error", "")
    assert "writerole" in str(err).lower()


def test_create_direct_fix_with_pr_bundle_variant_400(client: TestClient) -> None:
    """direct_fix request cannot include pr_bundle_variant."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_block_public_access")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        # action lookup only; validation should fail before account lookup
        yield _mock_async_session(action)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={
                "action_id": str(action.id),
                "mode": "direct_fix",
                "pr_bundle_variant": "cloudfront_oac_private_s3",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    data = r.json()
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid pr_bundle_variant"


def test_create_direct_fix_permission_probe_failed_400(client: TestClient) -> None:
    """direct_fix should fail fast when WriteRole probe indicates denied API permissions."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_block_public_access")
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account.account_id = "123456789012"

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        # action lookup, account lookup
        yield _mock_async_session(action, account)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch(
            "backend.routers.remediation_runs.probe_direct_fix_permissions",
            return_value=(False, "WriteRole probe denied by AWS API (AccessDenied)."),
        ):
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={"action_id": str(action.id), "mode": "direct_fix"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Direct-fix permission probe failed"
        assert detail.get("check_id") == "direct_fix_permission_probe_failed"


def test_create_pr_only_variant_not_applicable_400(client: TestClient) -> None:
    """cloudfront_oac_private_s3 variant is only valid for s3_bucket_block_public_access actions."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={
                "action_id": str(action.id),
                "mode": "pr_only",
                "pr_bundle_variant": "cloudfront_oac_private_s3",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    data = r.json()
    detail = data.get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid pr_bundle_variant"


def test_create_pr_only_run_for_pr_only_action_rejected_400(client: TestClient) -> None:
    """PR bundle generation is disabled for pr_only action types."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="pr_only")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        try:
            r = client.post(
                "/api/remediation-runs",
                json={"action_id": str(action.id), "mode": "pr_only"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "PR bundle unsupported"


def test_create_group_pr_bundle_run_pr_only_rejected_400(client: TestClient) -> None:
    """Group PR bundle generation is disabled for pr_only action type."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        try:
            r = client.post(
                "/api/remediation-runs/group-pr-bundle",
                json={
                    "action_type": "pr_only",
                    "account_id": "123456789012",
                    "region": "eu-north-1",
                    "status": "open",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "PR bundle unsupported"


def test_create_group_pr_bundle_run_success(client: TestClient) -> None:
    """group-pr-bundle endpoint should queue one run with group_action_ids in payload."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    action1 = _mock_action(action_type="s3_bucket_block_public_access")
    action1.id = uuid.uuid4()
    action1.account_id = "123456789012"
    action1.region = "eu-north-1"
    action1.status = "open"
    action1.priority = 100

    action2 = _mock_action(action_type="s3_bucket_block_public_access")
    action2.id = uuid.uuid4()
    action2.account_id = "123456789012"
    action2.region = "eu-north-1"
    action2.status = "open"
    action2.priority = 90

    actions_result = MagicMock()
    actions_result.scalars.return_value.unique.return_value.all.return_value = [action1, action2]

    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = None

    pending_result = MagicMock()
    pending_result.scalars.return_value.unique.return_value.all.return_value = []

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[actions_result, account_result, pending_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(run_obj: MagicMock) -> None:
        from datetime import datetime, timezone
        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-1"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch("backend.routers.remediation_runs.emit_strategy_metric") as mock_metric:
                try:
                    r = client.post(
                        "/api/remediation-runs/group-pr-bundle",
                        json={
                            "action_type": "s3_bucket_block_public_access",
                            "account_id": "123456789012",
                            "region": "eu-north-1",
                            "status": "open",
                            "strategy_id": "s3_migrate_cloudfront_oac_private",
                            "risk_acknowledged": True,
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert mock_sqs.send_message.call_count == 1
    metric_names = [call.args[1] for call in mock_metric.call_args_list if len(call.args) >= 2]
    assert "strategy_selected_count" in metric_names
    kwargs = mock_sqs.send_message.call_args.kwargs
    body = kwargs.get("MessageBody", "")
    assert str(action1.id) in body
    assert str(action2.id) in body


def test_create_group_pr_bundle_requires_region_filter(client: TestClient) -> None:
    """group-pr-bundle requires exact region or region_is_null=true."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield MagicMock()

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        try:
            r = client.post(
                "/api/remediation-runs/group-pr-bundle",
                json={
                    "action_type": "s3_bucket_block_public_access",
                    "account_id": "123456789012",
                    "status": "open",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid region filter"


# ---------------------------------------------------------------------------
# Strategy safety validations (Phase 1)
# ---------------------------------------------------------------------------


def test_create_run_missing_strategy_id_for_strategy_action_400(client: TestClient) -> None:
    """Mapped strategy actions must provide strategy_id."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={"action_id": str(action.id), "mode": "pr_only"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Missing strategy_id"


def test_create_run_strategy_mode_mismatch_400(client: TestClient) -> None:
    """Selected strategy mode must match request mode."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={
                "action_id": str(action.id),
                "mode": "direct_fix",
                "strategy_id": "s3_migrate_cloudfront_oac_private",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid strategy selection"
        assert "requires mode" in str(detail.get("detail", "")).lower()


def test_create_run_strategy_input_validation_400(client: TestClient) -> None:
    """Required strategy inputs are validated server-side."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
    try:
        r = client.post(
            "/api/remediation-runs",
            json={
                "action_id": str(action.id),
                "mode": "pr_only",
                "strategy_id": "config_enable_centralized_delivery",
                "strategy_inputs": {},
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid strategy selection"
        assert "strategy_inputs.delivery_bucket is required" in str(detail.get("detail", ""))


def test_create_run_warn_requires_risk_ack_400(client: TestClient) -> None:
    """Warn/unknown dependency checks require explicit risk acknowledgment."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, None)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.emit_strategy_metric") as mock_metric:
            with patch("backend.routers.remediation_runs.emit_validation_failure") as mock_failure:
                try:
                    r = client.post(
                        "/api/remediation-runs",
                        json={
                            "action_id": str(action.id),
                            "mode": "pr_only",
                            "strategy_id": "s3_migrate_cloudfront_oac_private",
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Risk acknowledgement required"
    metric_names = [call.args[1] for call in mock_metric.call_args_list if len(call.args) >= 2]
    assert "risk_ack_required_count" in metric_names
    assert "risk_ack_missing_rejection_count" in metric_names
    assert mock_failure.call_count >= 1
    reasons = [call.kwargs.get("reason") for call in mock_failure.call_args_list]
    assert "risk_ack_missing" in reasons


def test_create_run_legacy_variant_maps_to_strategy_success(client: TestClient) -> None:
    """Legacy pr_bundle_variant is accepted and mapped to strategy_id in queued payload."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")

    action_result = MagicMock()
    action_result.scalar_one_or_none.return_value = action
    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = None
    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[action_result, account_result, existing_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(run_obj: MagicMock) -> None:
        from datetime import datetime, timezone

        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-legacy"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch("backend.routers.remediation_runs.emit_strategy_metric") as mock_metric:
                try:
                    r = client.post(
                        "/api/remediation-runs",
                        json={
                            "action_id": str(action.id),
                            "mode": "pr_only",
                            "pr_bundle_variant": "cloudfront_oac_private_s3",
                            "risk_acknowledged": True,
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    metric_names = [call.args[1] for call in mock_metric.call_args_list if len(call.args) >= 2]
    assert "strategy_selected_count" in metric_names
    body = mock_sqs.send_message.call_args.kwargs.get("MessageBody", "")
    assert '"pr_bundle_variant": "cloudfront_oac_private_s3"' in body
    assert '"strategy_id": "s3_migrate_cloudfront_oac_private"' in body


# ---------------------------------------------------------------------------
# GET remediation-preview (8.4)
# ---------------------------------------------------------------------------


def test_remediation_preview_action_not_fixable(client: TestClient) -> None:
    """Preview for pr_only action returns compliant=False, will_apply=False."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="pr_only")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(
            f"/api/actions/{action.id}/remediation-preview?mode=direct_fix",
            params={"tenant_id": str(tenant.id)},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is False
    assert "does not support direct fix" in data["message"]


def test_remediation_preview_no_write_role(client: TestClient) -> None:
    """Preview with no WriteRole returns compliant=False without assuming."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_block_public_access")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn=None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.actions.assume_role") as mock_assume:
        try:
            r = client.get(
                f"/api/actions/{action.id}/remediation-preview?mode=direct_fix",
                params={"tenant_id": str(tenant.id)},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    assert mock_assume.call_count == 0
    data = r.json()
    assert data["compliant"] is False
    assert "WriteRole" in data["message"]


def test_remediation_preview_success(client: TestClient) -> None:
    """Preview with WriteRole assumes and returns preview result."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_block_public_access")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user
    from worker.services.direct_fix import RemediationPreviewResult

    preview_result = RemediationPreviewResult(
        compliant=False,
        message="S3 Block Public Access not configured; will enable.",
        will_apply=True,
    )

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.actions.assume_role", return_value=MagicMock()):
        with patch(
            "worker.services.direct_fix.run_remediation_preview",
            return_value=preview_result,
        ):
            try:
                r = client.get(
                    f"/api/actions/{action.id}/remediation-preview?mode=direct_fix",
                    params={"tenant_id": str(tenant.id)},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is True
    assert "S3 Block Public Access" in data["message"]


# ---------------------------------------------------------------------------
# PATCH cancel remediation run
# ---------------------------------------------------------------------------


def test_patch_cancel_pending_run_200(client: TestClient) -> None:
    """PATCH with status=cancelled on pending run returns 200 and cancels."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action()
    run_id = uuid.uuid4()

    action.id = uuid.uuid4()
    action.title = "Test action"
    action.account_id = "123456789012"
    action.region = "us-east-1"

    run = MagicMock()
    run.id = run_id
    run.tenant_id = tenant.id
    run.action_id = action.id
    run.status = RemediationRunStatus.pending
    run.outcome = None
    run.logs = "Run started."
    run.started_at = None
    run.completed_at = None
    run.action = action
    run.mode = RemediationRunMode.pr_only
    run.approved_by_user_id = user.id
    run.artifacts = None
    run.created_at = MagicMock()
    run.created_at.isoformat = lambda: "2026-02-02T12:00:00Z"
    run.updated_at = MagicMock()
    run.updated_at.isoformat = lambda: "2026-02-02T12:00:00Z"

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        # get_tenant needs tenant; patch_remediation_run select needs run
        session = _mock_async_session(tenant, run)
        session.flush = MagicMock()
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        r = client.patch(
            f"/api/remediation-runs/{run_id}",
            json={"status": "cancelled"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "cancelled"
    assert data["outcome"] == "Cancelled by user"


# ---------------------------------------------------------------------------
# GET pr-bundle.zip (Step 9.6)
# ---------------------------------------------------------------------------


def test_get_pr_bundle_zip_200(client: TestClient) -> None:
    """GET /remediation-runs/{id}/pr-bundle.zip returns zip when run has pr_bundle.files."""
    import zipfile
    import io

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run_id = str(uuid.uuid4())
    run = MagicMock()
    run.id = uuid.UUID(run_id)
    run.tenant_id = tenant.id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.success
    run.artifacts = {
        "pr_bundle": {
            "files": [
                {"path": "providers.tf", "content": "# terraform\n"},
                {"path": "s3_block_public_access.tf", "content": 'resource "aws_s3_account_public_access_block" "x" {}'},
            ],
        },
    }

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        # get_tenant query, then get run query (no selectinload for pr-bundle.zip)
        session = _mock_async_session(tenant, run)
        yield session

    from backend.auth import get_optional_user

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/remediation-runs/{run_id}/pr-bundle.zip")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    assert "application/zip" in r.headers.get("content-type", "")
    assert f"pr-bundle-{run_id}.zip" in r.headers.get("content-disposition", "")
    # Verify zip content
    zf = zipfile.ZipFile(io.BytesIO(r.content), "r")
    names = zf.namelist()
    zf.close()
    assert "providers.tf" in names
    assert "s3_block_public_access.tf" in names


def test_get_pr_bundle_zip_404_no_artifacts(client: TestClient) -> None:
    """GET /remediation-runs/{id}/pr-bundle.zip returns 404 when run has no pr_bundle."""
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run_id = str(uuid.uuid4())
    run = MagicMock()
    run.id = uuid.UUID(run_id)
    run.tenant_id = tenant.id
    run.artifacts = None

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = _mock_async_session(tenant, run)
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/remediation-runs/{run_id}/pr-bundle.zip")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 404


def test_execute_pr_bundle_plan_queues_execution(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.success
    run.outcome = "PR bundle generated"
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": "x"}]}}
    run.action = action

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    active_result = MagicMock()
    active_result.scalars.return_value.first.return_value = None
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[run_result, active_result, count_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def _refresh(exec_obj: MagicMock) -> None:
        from datetime import datetime, timezone
        exec_obj.created_at = datetime.now(timezone.utc)
        exec_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-exec"}
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT = 2
        mock_settings.SAAS_BUNDLE_EXECUTOR_FAIL_FAST = True
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(f"/api/remediation-runs/{run.id}/execute-pr-bundle")
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    data = r.json()
    assert "execution_id" in data
    assert data["status"] == "queued"
    assert mock_sqs.send_message.call_count == 1


def test_execute_pr_bundle_plan_throttled_429(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.success
    run.outcome = "PR bundle generated"
    run.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": "x"}]}}
    run.action = action

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    active_result = MagicMock()
    active_result.scalars.return_value.first.return_value = None
    count_result = MagicMock()
    count_result.scalar.return_value = 2

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[run_result, active_result, count_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT = 2
        try:
            r = client.post(f"/api/remediation-runs/{run.id}/execute-pr-bundle")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 429
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Execution capacity reached"


def test_approve_apply_requires_awaiting_approval(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.mode = RemediationRunMode.pr_only

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = run
    latest_exec = MagicMock()
    latest_exec.phase = RemediationRunExecutionPhase.plan
    latest_exec.status = RemediationRunExecutionStatus.running
    latest_result = MagicMock()
    latest_result.scalars.return_value.first.return_value = latest_exec

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[run_result, latest_result])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        try:
            r = client.post(f"/api/remediation-runs/{run.id}/approve-apply")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Run not awaiting approval"


def test_bulk_execute_pr_bundle_plan_queues_multiple(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run1 = MagicMock()
    run1.id = uuid.uuid4()
    run1.tenant_id = tenant.id
    run1.mode = RemediationRunMode.pr_only
    run1.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": "x"}]}}
    run1.status = RemediationRunStatus.success
    run1.outcome = "PR bundle generated"
    run1.action = _mock_action(action_type="s3_bucket_block_public_access")

    run2 = MagicMock()
    run2.id = uuid.uuid4()
    run2.tenant_id = tenant.id
    run2.mode = RemediationRunMode.pr_only
    run2.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": "x"}]}}
    run2.status = RemediationRunStatus.success
    run2.outcome = "PR bundle generated"
    run2.action = _mock_action(action_type="cloudtrail_enabled")

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [run1, run2]
    active_one = MagicMock()
    active_one.scalars.return_value.first.return_value = None
    active_two = MagicMock()
    active_two.scalars.return_value.first.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[count_result, runs_result, active_one, active_two])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-exec"}
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT = 6
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(
                    "/api/remediation-runs/bulk-execute-pr-bundle",
                    json={
                        "run_ids": [str(run1.id), str(run2.id)],
                        "max_parallel": 3,
                        "fail_fast": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    body = r.json()
    assert len(body.get("accepted", [])) == 2
    assert len(body.get("rejected", [])) == 0
    assert mock_sqs.send_message.call_count == 2


def test_bulk_execute_pr_bundle_plan_rejects_capacity(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run1 = MagicMock()
    run1.id = uuid.uuid4()
    run1.tenant_id = tenant.id
    run1.mode = RemediationRunMode.pr_only
    run1.artifacts = {"pr_bundle": {"files": [{"path": "main.tf", "content": "x"}]}}
    run1.status = RemediationRunStatus.success
    run1.outcome = "PR bundle generated"
    run1.action = _mock_action(action_type="s3_bucket_block_public_access")

    count_result = MagicMock()
    count_result.scalar.return_value = 6
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [run1]
    active_one = MagicMock()
    active_one.scalars.return_value.first.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[count_result, runs_result, active_one])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT = 6
        with patch("backend.routers.remediation_runs.boto3.client", return_value=MagicMock()):
            try:
                r = client.post(
                    "/api/remediation-runs/bulk-execute-pr-bundle",
                    json={
                        "run_ids": [str(run1.id)],
                        "max_parallel": 3,
                        "fail_fast": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    body = r.json()
    assert len(body.get("accepted", [])) == 0
    assert len(body.get("rejected", [])) == 1
    assert body["rejected"][0]["reason"] == "capacity_exceeded"


def test_bulk_approve_apply_queues_multiple(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run1 = MagicMock()
    run1.id = uuid.uuid4()
    run1.tenant_id = tenant.id
    run1.mode = RemediationRunMode.pr_only
    run1.status = RemediationRunStatus.awaiting_approval
    run1.outcome = "Plan complete. Awaiting approval for apply."

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [run1]
    latest_plan = MagicMock()
    latest_plan.phase = RemediationRunExecutionPhase.plan
    latest_plan.status = RemediationRunExecutionStatus.awaiting_approval
    latest_plan.workspace_manifest = {"bundle_hash": "abc"}
    latest_result = MagicMock()
    latest_result.scalars.return_value.first.return_value = latest_plan
    active_apply_result = MagicMock()
    active_apply_result.scalars.return_value.first.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[count_result, runs_result, latest_result, active_apply_result])
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-apply"}
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SAAS_BUNDLE_EXECUTOR_ENABLED = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.SAAS_BUNDLE_EXECUTOR_MAX_CONCURRENT_PER_TENANT = 6
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(
                    "/api/remediation-runs/bulk-approve-apply",
                    json={"run_ids": [str(run1.id)], "max_parallel": 3},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 200
    body = r.json()
    assert len(body.get("accepted", [])) == 1
    assert len(body.get("rejected", [])) == 0
    assert mock_sqs.send_message.call_count == 1
