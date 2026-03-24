"""
Unit tests for remediation runs API (Step 7.2 + 8.4).

Covers: POST create run (approval, direct_fix validation), GET remediation-preview.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.exc import IntegrityError

from backend.auth import get_current_user, get_optional_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import (
    RemediationRunMode,
    RemediationRunStatus,
)
from backend.services.root_key_resolution_adapter import ROOT_KEY_EXECUTION_AUTHORITY_PATH
from backend.services.remediation_strategy import (
    list_strategies_for_action_type,
    validate_strategy_inputs,
)
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
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
    acc.account_id = "123456789012"
    acc.role_read_arn = "arn:aws:iam::123456789012:role/ReadRole"
    acc.role_write_arn = role_write_arn
    acc.external_id = "ext-123"
    return acc


def _mock_tenant() -> MagicMock:
    t = MagicMock()
    t.id = uuid.uuid4()
    return t


def _mock_strategy_with_fields(fields: list[dict[str, object]]) -> dict[str, object]:
    return {
        "strategy_id": "test_strategy",
        "action_type": "test_action_type",
        "label": "Test strategy",
        "mode": "pr_only",
        "risk_level": "low",
        "recommended": False,
        "requires_inputs": bool(fields),
        "input_schema": {"fields": fields},
        "supports_exception_flow": False,
        "exception_only": False,
        "warnings": [],
        "legacy_pr_bundle_variant": None,
    }


def _mock_existing_run(
    action: MagicMock,
    *,
    status: RemediationRunStatus,
    mode: RemediationRunMode = RemediationRunMode.pr_only,
    artifacts: dict | None = None,
) -> MagicMock:
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = action.tenant_id
    run.action_id = action.id
    run.status = status
    run.mode = mode
    run.artifacts = artifacts
    run.created_at = datetime.now(timezone.utc)
    run.updated_at = run.created_at
    run.started_at = None
    run.completed_at = None
    run.outcome = None
    return run


def _mock_async_session(*scalar_results: object) -> MagicMock:
    """Mock AsyncSession with execute returning one mocked result per call."""
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

    async def _refresh(obj: MagicMock) -> None:
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        obj.updated_at = now

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


def _mock_group_action(
    *,
    action_type: str = "s3_bucket_block_public_access",
    account_id: str = "123456789012",
    region: str | None = "eu-north-1",
    status: str = "open",
    priority: int = 100,
) -> MagicMock:
    action = _mock_action(action_type=action_type)
    action.id = uuid.uuid4()
    action.account_id = account_id
    action.region = region
    action.status = status
    action.priority = priority
    return action


def _mock_group_query_result(items: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    scalars.unique.return_value.all.return_value = items
    result.scalars.return_value = scalars
    return result


def _mock_group_account_result(account: MagicMock | None) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    return result


def _mock_group_session(
    actions: list[MagicMock],
    *,
    account: MagicMock | None = None,
    pending_runs: list[MagicMock] | None = None,
    active_runs: list[MagicMock] | None = None,
    refetched_active_runs: list[MagicMock] | None = None,
) -> MagicMock:
    initial_active_runs = active_runs if active_runs is not None else (pending_runs or [])
    refreshed_active_runs = refetched_active_runs if refetched_active_runs is not None else initial_active_runs
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_group_query_result(actions),
            _mock_group_account_result(account),
            _mock_group_query_result(initial_active_runs),
            _mock_group_query_result(refreshed_active_runs),
        ]
    )
    added: list[MagicMock] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()
    session._added = added

    async def _refresh(run_obj: MagicMock) -> None:
        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)
    return session


@pytest.fixture(autouse=True)
def stub_remediation_run_tenant_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_get_tenant(tenant_id: uuid.UUID, db) -> MagicMock:
        tenant = MagicMock()
        tenant.id = tenant_id
        tenant.remediation_settings = {}
        return tenant

    monkeypatch.setattr("backend.routers.remediation_runs.get_tenant", _stub_get_tenant)


# ---------------------------------------------------------------------------
# POST create_remediation_run - direct_fix validation (8.4)
# ---------------------------------------------------------------------------


def test_create_direct_fix_action_not_fixable_400(client: TestClient) -> None:
    """direct_fix is rejected as out of scope before action-type-specific validation."""
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
    detail = r.json()["detail"]
    assert detail["error"] == "Direct-fix out of scope"
    assert "out of scope" in detail["detail"].lower()


def test_create_direct_fix_no_write_role_400(client: TestClient) -> None:
    """direct_fix is rejected before WriteRole-specific validation."""
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
                        json={
                            "action_id": str(action.id),
                            "mode": "direct_fix",
                            "strategy_id": "s3_account_block_public_access_direct_fix",
                        },
                    )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "Direct-fix out of scope"
    assert "out of scope" in detail["detail"].lower()


def test_create_direct_fix_with_pr_bundle_variant_400(client: TestClient) -> None:
    """direct_fix is rejected before legacy variant validation."""
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
    detail = r.json()["detail"]
    assert detail["error"] == "Direct-fix out of scope"
    assert "out of scope" in detail["detail"].lower()


def test_create_direct_fix_permission_probe_failed_400(client: TestClient) -> None:
    """direct_fix is rejected before permission probing runs."""
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
        ) as mock_probe:
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={
                        "action_id": str(action.id),
                        "mode": "direct_fix",
                        "strategy_id": "s3_account_block_public_access_direct_fix",
                        "risk_acknowledged": True,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "Direct-fix out of scope"
    assert "out of scope" in detail["detail"].lower()
    assert mock_probe.call_count == 0


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


def test_create_run_duplicate_active_status_returns_409_with_existing_run_id(client: TestClient) -> None:
    """Active runs (pending/running/awaiting_approval) must block duplicate create requests."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing = _mock_existing_run(action, status=RemediationRunStatus.running)

    session = _mock_async_session(action, None, existing)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

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

    assert r.status_code == 409
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Duplicate pending run"
        assert detail.get("reason") == "duplicate_active_run"
        assert detail.get("existing_run_id") == str(existing.id)
        assert detail.get("existing_run_status") == "running"
    assert session.commit.await_count == 0


def test_create_run_auto_retires_stale_pending_duplicate(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing = _mock_existing_run(action, status=RemediationRunStatus.pending)
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    existing.created_at = stale_time
    existing.updated_at = stale_time
    session = _mock_async_session(action, None, [existing], [existing])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-retired-stale-pending"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={"action_id": str(action.id), "mode": "pr_only"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert existing.status == RemediationRunStatus.failed
    assert existing.outcome == "stale_active_run_retired"
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1


def test_create_run_auto_retires_stale_running_duplicate(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing = _mock_existing_run(action, status=RemediationRunStatus.running)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=4)
    existing.created_at = stale_time
    existing.updated_at = stale_time
    existing.started_at = stale_time
    session = _mock_async_session(action, None, [existing], [existing])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-retired-stale-running"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={"action_id": str(action.id), "mode": "pr_only"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert existing.status == RemediationRunStatus.failed
    assert existing.outcome == "stale_active_run_retired"
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1


def test_create_run_identical_pr_bundle_rate_limit_returns_429(client: TestClient) -> None:
    """Same PR bundle config is capped at 3 queue submissions per 20-minute window."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing_runs = [
        _mock_existing_run(action, status=RemediationRunStatus.success),
        _mock_existing_run(action, status=RemediationRunStatus.success),
        _mock_existing_run(action, status=RemediationRunStatus.success),
    ]

    session = _mock_async_session(action, None, existing_runs)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

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

    assert r.status_code == 429
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "PR bundle queue rate limit exceeded"
        assert detail.get("reason") == "pr_bundle_rate_limit_identical"
        assert detail.get("limit") == 3
        assert detail.get("observed") == 3
    assert session.commit.await_count == 0


def test_create_run_different_profile_id_not_treated_as_identical_duplicate(client: TestClient) -> None:
    """Profile-aware duplicate signatures should not collapse different canonical profiles."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="cloudtrail_enabled")
    action.tenant_id = tenant.id
    existing_runs = [
        _mock_existing_run(
            action,
            status=RemediationRunStatus.success,
            artifacts={
                "selected_strategy": "cloudtrail_enable_guided",
                "resolution": {
                    "strategy_id": "cloudtrail_enable_guided",
                    "profile_id": f"legacy-profile-{idx}",
                },
            },
        )
        for idx in range(3)
    ]
    session = _mock_async_session(action, None, existing_runs)

    async def _refresh(run_obj: MagicMock) -> None:
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
    mock_sqs.send_message.return_value = {"MessageId": "msg-profile-aware"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch("backend.routers.remediation_runs.collect_runtime_risk_signals", return_value={}):
                try:
                    r = client.post(
                        "/api/remediation-runs",
                        json={
                            "action_id": str(action.id),
                            "mode": "pr_only",
                            "strategy_id": "cloudtrail_enable_guided",
                            "profile_id": "cloudtrail_enable_guided",
                            "risk_acknowledged": True,
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert stale_pending_run.status == RemediationRunStatus.failed
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1


def test_create_run_total_pr_bundle_rate_limit_returns_429(client: TestClient) -> None:
    """Total PR bundle submissions for an action are capped at 6 per 20-minute window."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing_runs = [
        _mock_existing_run(
            action,
            status=RemediationRunStatus.success,
            artifacts={"selected_strategy": f"strategy-{idx}"},
        )
        for idx in range(6)
    ]

    session = _mock_async_session(action, None, existing_runs)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

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

    assert r.status_code == 429
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "PR bundle queue rate limit exceeded"
        assert detail.get("reason") == "pr_bundle_rate_limit_total"
        assert detail.get("limit") == 6
        assert detail.get("observed") == 6
    assert session.commit.await_count == 0


def test_create_run_recent_different_signature_allows_new_run(client: TestClient) -> None:
    """Recent run with different request signature should not block a new run."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id
    existing = _mock_existing_run(
        action,
        status=RemediationRunStatus.success,
        mode=RemediationRunMode.direct_fix,
    )

    session = _mock_async_session(action, None, existing)

    async def _refresh(run_obj: MagicMock) -> None:
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
    mock_sqs.send_message.return_value = {"MessageId": "msg-non-duplicate"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={"action_id": str(action.id), "mode": "pr_only"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert stale_pending_run.status == RemediationRunStatus.failed
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1


def test_resend_run_rate_limited_after_three_attempts_in_window(client: TestClient) -> None:
    """Resend endpoint blocks the 4th resend attempt within 20 minutes for the same run."""
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.pending
    now = datetime.now(timezone.utc)
    run.artifacts = {
        "queue_resend_attempts": [
            (now - timedelta(minutes=1)).isoformat(),
            (now - timedelta(minutes=2)).isoformat(),
            (now - timedelta(minutes=3)).isoformat(),
        ]
    }

    session = _mock_async_session(tenant, run)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.is_local = True
        try:
            r = client.post(f"/api/remediation-runs/{run.id}/resend")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 429
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Resend rate limit exceeded"
        assert detail.get("limit") == 3
        assert detail.get("window_minutes") == 20
    assert session.commit.await_count == 0


def test_create_group_pr_bundle_run_success(client: TestClient) -> None:
    """Legacy top-level grouped requests still succeed and persist Wave 3 action resolutions."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    action1 = _mock_group_action(priority=100)
    action2 = _mock_group_action(priority=90)
    session = _mock_group_session([action1, action2])

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
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
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
    run = session.add.call_args.args[0]
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["action_id"] == str(action1.id)
    assert payload["strategy_id"] == "s3_migrate_cloudfront_oac_private"
    assert payload["group_action_ids"] == [str(action1.id), str(action2.id)]
    assert payload["risk_acknowledged"] is True
    assert "action_overrides" not in payload
    assert payload["action_resolutions"] == run.artifacts["group_bundle"]["action_resolutions"]

    assert run.action_id == action1.id
    assert run.artifacts["selected_strategy"] == "s3_migrate_cloudfront_oac_private"
    resolutions = run.artifacts["group_bundle"]["action_resolutions"]
    assert [entry["action_id"] for entry in resolutions] == [str(action1.id), str(action2.id)]
    assert {entry["strategy_id"] for entry in resolutions} == {"s3_migrate_cloudfront_oac_private"}
    assert {entry["profile_id"] for entry in resolutions} == {
        "s3_migrate_cloudfront_oac_private_manual_preservation"
    }


def test_create_group_pr_bundle_accepts_action_overrides(client: TestClient) -> None:
    """Grouped runs accept additive action_overrides[] and persist per-action resolutions."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    session = _mock_group_session([action1, action2])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-override"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                                "action_overrides": [
                                    {
                                        "action_id": str(action1.id),
                                        "strategy_id": "config_enable_account_local_delivery",
                                    }
                                ],
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    run = session.add.call_args.args[0]
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["strategy_id"] == "config_enable_centralized_delivery"
    assert payload["strategy_inputs"] == {"delivery_bucket": "central-config-bucket"}
    assert payload["group_action_ids"] == [str(action1.id), str(action2.id)]
    assert payload["action_resolutions"] == run.artifacts["group_bundle"]["action_resolutions"]
    assert "action_overrides" not in payload

    assert run.artifacts["selected_strategy"] == "config_enable_centralized_delivery"
    resolutions = {
        entry["action_id"]: entry
        for entry in run.artifacts["group_bundle"]["action_resolutions"]
    }
    assert resolutions[str(action1.id)]["strategy_id"] == "config_enable_account_local_delivery"
    assert resolutions[str(action1.id)]["profile_id"] == "config_enable_account_local_delivery"
    assert resolutions[str(action1.id)]["strategy_inputs"] == {
        "delivery_bucket_mode": "create_new"
    }
    assert resolutions[str(action2.id)]["strategy_id"] == "config_enable_centralized_delivery"
    assert resolutions[str(action2.id)]["profile_id"] == "config_enable_centralized_delivery"
    assert resolutions[str(action2.id)]["strategy_inputs"] == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "delivery_bucket": "central-config-bucket",
        "encrypt_with_kms": False,
    }


def test_create_group_pr_bundle_duplicate_action_overrides_rejected_400(client: TestClient) -> None:
    """Duplicate grouped override entries are rejected before any run is created."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_group_action(action_type="aws_config_enabled")
    session = _mock_group_session([action])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            try:
                r = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "aws_config_enabled",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "config_enable_account_local_delivery",
                        "action_overrides": [
                            {
                                "action_id": str(action.id),
                                "strategy_id": "config_enable_account_local_delivery",
                            },
                            {
                                "action_id": str(action.id),
                                "strategy_id": "config_enable_account_local_delivery",
                            },
                        ],
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Duplicate action_overrides entry"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_group_pr_bundle_override_action_outside_group_rejected_400(client: TestClient) -> None:
    """Overrides must target actions inside the grouped action set."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_group_action(action_type="aws_config_enabled")
    session = _mock_group_session([action])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            try:
                r = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "aws_config_enabled",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "config_enable_account_local_delivery",
                        "action_overrides": [
                            {
                                "action_id": str(uuid.uuid4()),
                                "strategy_id": "config_enable_account_local_delivery",
                            }
                        ],
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid action_overrides[].action_id"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


@pytest.mark.parametrize(
    ("override", "expected_error"),
    [
        (
            {"strategy_id": "s3_migrate_cloudfront_oac_private"},
            "Invalid strategy selection",
        ),
        (
            {
                "strategy_id": "config_enable_account_local_delivery",
                "profile_id": "not-a-profile",
            },
            "Invalid profile_id",
        ),
    ],
)
def test_create_group_pr_bundle_invalid_action_override_rejected_400(
    client: TestClient,
    override: dict[str, str],
    expected_error: str,
) -> None:
    """Invalid override strategy/profile selections are rejected."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_group_action(action_type="aws_config_enabled")
    session = _mock_group_session([action])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            try:
                r = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "aws_config_enabled",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "config_enable_account_local_delivery",
                        "action_overrides": [
                            {
                                "action_id": str(action.id),
                                **override,
                            }
                        ],
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == expected_error
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_group_pr_bundle_duplicate_pending_guard_still_works(client: TestClient) -> None:
    """The grouped duplicate-pending guard remains unchanged for the legacy queue contract."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(priority=100)
    action2 = _mock_group_action(priority=90)
    pending_run = MagicMock()
    pending_run.id = uuid.uuid4()
    pending_run.action_id = action1.id
    pending_run.mode = RemediationRunMode.pr_only
    pending_run.status = RemediationRunStatus.pending
    pending_run.created_at = datetime.now(timezone.utc)
    pending_run.artifacts = {
        "group_bundle": {
            "group_key": "s3_bucket_block_public_access|123456789012|eu-north-1|open"
        }
    }
    session = _mock_group_session([action1, action2], pending_runs=[pending_run])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "s3_bucket_block_public_access",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "s3_migrate_cloudfront_oac_private",
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 409
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Duplicate pending run"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_group_pr_bundle_different_override_map_not_duplicate(client: TestClient) -> None:
    """Grouped duplicate checks should use effective per-action decisions, not only group_key."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    pending_run = MagicMock()
    pending_run.id = uuid.uuid4()
    pending_run.action_id = action1.id
    pending_run.mode = RemediationRunMode.pr_only
    pending_run.status = RemediationRunStatus.pending
    pending_run.created_at = datetime.now(timezone.utc)
    pending_run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(action1.id), str(action2.id)],
            "action_resolutions": [
                {
                    "action_id": str(action1.id),
                    "strategy_id": "config_enable_account_local_delivery",
                    "profile_id": "config_enable_account_local_delivery",
                    "strategy_inputs": {},
                },
                {
                    "action_id": str(action2.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                },
            ],
        },
    }
    session = _mock_group_session([action1, action2], pending_runs=[pending_run], active_runs=[pending_run])

    async def _commit_side_effect() -> None:
        run = session._added[-1]
        if run.action_id == action1.id:
            raise IntegrityError(
                "insert into remediation_runs ...",
                {},
                Exception('duplicate key value violates unique constraint "uq_remediation_runs_action_active"'),
            )

    session.commit = AsyncMock(side_effect=_commit_side_effect)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-group-different-overrides"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                                "action_overrides": [
                                    {
                                        "action_id": str(action2.id),
                                        "strategy_id": "config_enable_account_local_delivery",
                                    }
                                ],
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert stale_pending_run.status == RemediationRunStatus.failed
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1
    assert r.json()["action_id"] == str(action2.id)
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["action_id"] == str(action2.id)


def test_create_group_pr_bundle_different_repo_target_not_duplicate(client: TestClient) -> None:
    """A different repo_target should avoid the occupied representative action instead of 500ing."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    pending_run = MagicMock()
    pending_run.id = uuid.uuid4()
    pending_run.action_id = action1.id
    pending_run.mode = RemediationRunMode.pr_only
    pending_run.status = RemediationRunStatus.pending
    pending_run.created_at = datetime.now(timezone.utc)
    pending_run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "repo_target": {"repository": "acme/live", "base_branch": "main"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(action1.id), str(action2.id)],
            "action_resolutions": [
                {
                    "action_id": str(action1.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                },
                {
                    "action_id": str(action2.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                },
            ],
        },
    }
    session = _mock_group_session([action1, action2], pending_runs=[pending_run], active_runs=[pending_run])

    async def _commit_side_effect() -> None:
        run = session._added[-1]
        if run.action_id == action1.id:
            raise IntegrityError(
                "insert into remediation_runs ...",
                {},
                Exception('duplicate key value violates unique constraint "uq_remediation_runs_action_active"'),
            )

    session.commit = AsyncMock(side_effect=_commit_side_effect)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-group-different-repo-target"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                                "repo_target": {
                                    "provider": "generic_git",
                                    "repository": "acme/live",
                                    "base_branch": "main",
                                    "head_branch": "wave-4-rerun",
                                },
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert stale_pending_run.status == RemediationRunStatus.failed
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1
    assert r.json()["action_id"] == str(action2.id)
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["action_id"] == str(action2.id)


def test_create_group_pr_bundle_ignores_stale_pending_pr_only_run(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    stale_pending_run = MagicMock()
    stale_pending_run.id = uuid.uuid4()
    stale_pending_run.action_id = action1.id
    stale_pending_run.mode = RemediationRunMode.pr_only
    stale_pending_run.status = RemediationRunStatus.pending
    stale_pending_run.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    stale_pending_run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(action1.id), str(action2.id)],
            "action_resolutions": [
                {
                    "action_id": str(action1.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                },
                {
                    "action_id": str(action2.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                },
            ],
        },
    }
    session = _mock_group_session(
        [action1, action2],
        pending_runs=[stale_pending_run],
        active_runs=[stale_pending_run],
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-stale-pending-group"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 201
    assert stale_pending_run.status == RemediationRunStatus.failed
    assert session.commit.await_count == 2
    assert mock_sqs.send_message.call_count == 1


def test_create_group_pr_bundle_identical_override_map_still_duplicate(client: TestClient) -> None:
    """Identical grouped effective decisions should still hit the pending duplicate guard."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    canonical_resolutions = [
        {
            "action_id": str(action1.id),
            "strategy_id": "config_enable_account_local_delivery",
            "profile_id": "config_enable_account_local_delivery",
            "strategy_inputs": {"delivery_bucket_mode": "create_new"},
        },
        {
            "action_id": str(action2.id),
            "strategy_id": "config_enable_centralized_delivery",
            "profile_id": "config_enable_centralized_delivery",
            "strategy_inputs": {
                "recording_scope": "keep_existing",
                "delivery_bucket_mode": "use_existing",
                "delivery_bucket": "central-config-bucket",
                "encrypt_with_kms": False,
            },
        },
    ]
    pending_run = MagicMock()
    pending_run.id = uuid.uuid4()
    pending_run.action_id = action1.id
    pending_run.mode = RemediationRunMode.pr_only
    pending_run.status = RemediationRunStatus.pending
    pending_run.created_at = datetime.now(timezone.utc)
    pending_run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(action1.id), str(action2.id)],
            "action_resolutions": canonical_resolutions,
        },
    }
    session = _mock_group_session([action1, action2], pending_runs=[pending_run])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                                "action_overrides": [
                                    {
                                        "action_id": str(action1.id),
                                        "strategy_id": "config_enable_account_local_delivery",
                                    }
                                ],
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 409
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Duplicate pending run"
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_group_pr_bundle_rejects_identical_successful_run(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(action_type="aws_config_enabled", priority=100)
    action2 = _mock_group_action(action_type="aws_config_enabled", priority=90)
    successful_run = MagicMock()
    successful_run.id = uuid.uuid4()
    successful_run.action_id = action1.id
    successful_run.mode = RemediationRunMode.pr_only
    successful_run.status = RemediationRunStatus.success
    successful_run.created_at = datetime.now(timezone.utc)
    successful_run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(action1.id), str(action2.id)],
            "action_resolutions": [
                {
                    "action_id": str(action1.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {
                        "recording_scope": "keep_existing",
                        "delivery_bucket_mode": "use_existing",
                        "delivery_bucket": "central-config-bucket",
                        "encrypt_with_kms": False,
                    },
                },
                {
                    "action_id": str(action2.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "profile_id": "config_enable_centralized_delivery",
                    "strategy_inputs": {
                        "recording_scope": "keep_existing",
                        "delivery_bucket_mode": "use_existing",
                        "delivery_bucket": "central-config-bucket",
                        "encrypt_with_kms": False,
                    },
                },
            ],
        },
    }
    session = _mock_group_session([action1, action2], active_runs=[successful_run])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            with patch(
                "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
                return_value={},
            ):
                with patch(
                    "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
                    return_value={"checks": [], "warnings": [], "recommendation": "ok"},
                ):
                    try:
                        r = client.post(
                            "/api/remediation-runs/group-pr-bundle",
                            json={
                                "action_type": "aws_config_enabled",
                                "account_id": "123456789012",
                                "region": "eu-north-1",
                                "status": "open",
                                "strategy_id": "config_enable_centralized_delivery",
                                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
                            },
                        )
                    finally:
                        app.dependency_overrides.pop(get_db, None)
                        app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "PR bundle already created"
    assert detail["reason"] == "grouped_bundle_already_created_no_changes"
    assert detail["existing_run_id"] == str(successful_run.id)
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_resend_run_legacy_grouped_artifacts_requeue_schema_v1(client: TestClient) -> None:
    """Legacy grouped runs should still reconstruct resend payloads without schema-v2 emission."""
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.pending
    run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "pr_bundle_variant": "terraform",
        "risk_acknowledged": True,
        "repo_target": {"repository": "acme/live", "base_branch": "main"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        },
    }

    session = _mock_async_session(tenant, run)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-resend-legacy-group"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.is_local = True
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(f"/api/remediation-runs/{run.id}/resend")
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
    assert payload["strategy_id"] == "config_enable_centralized_delivery"
    assert payload["strategy_inputs"] == {"delivery_bucket": "central-config-bucket"}
    assert payload["group_action_ids"] == run.artifacts["group_bundle"]["action_ids"]
    assert payload["repo_target"] == {"repository": "acme/live", "base_branch": "main"}
    assert "resolution" not in payload
    assert "action_resolutions" not in payload


def test_resend_run_canonical_single_resolution_requeues_schema_v2(client: TestClient) -> None:
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    resolution = {
        "strategy_id": "cloudtrail_enable_guided",
        "profile_id": "cloudtrail_enable_guided",
        "support_tier": "review_required_bundle",
        "resolved_inputs": {"trail_name": "security-trail"},
        "missing_inputs": [],
        "missing_defaults": [],
        "blocked_reasons": [],
        "rejected_profiles": [],
        "finding_coverage": {},
        "preservation_summary": {},
        "decision_rationale": "",
        "decision_version": "resolver/v1",
    }
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.pending
    run.artifacts = {
        "selected_strategy": "cloudtrail_enable_guided",
        "strategy_inputs": {"trail_name": "legacy-trail"},
        "pr_bundle_variant": "terraform",
        "resolution": resolution,
    }

    session = _mock_async_session(tenant, run)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-resend-canonical-single"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.is_local = True
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(f"/api/remediation-runs/{run.id}/resend")
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["strategy_id"] == "cloudtrail_enable_guided"
    assert payload["strategy_inputs"] == {"trail_name": "legacy-trail"}
    assert payload["resolution"] == resolution
    assert "action_resolutions" not in payload


def test_resend_run_canonical_grouped_resolutions_requeue_schema_v2(client: TestClient) -> None:
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action_one = str(uuid.uuid4())
    action_two = str(uuid.uuid4())
    action_resolutions = [
        {
            "action_id": action_one,
            "strategy_id": "config_enable_account_local_delivery",
            "profile_id": "config_enable_account_local_delivery",
            "strategy_inputs": {},
            "resolution": {
                "strategy_id": "config_enable_account_local_delivery",
                "profile_id": "config_enable_account_local_delivery",
                "support_tier": "deterministic_bundle",
                "resolved_inputs": {},
                "missing_inputs": [],
                "missing_defaults": [],
                "blocked_reasons": [],
                "rejected_profiles": [],
                "finding_coverage": {},
                "preservation_summary": {},
                "decision_rationale": "",
                "decision_version": "resolver/v1",
            },
        },
        {
            "action_id": action_two,
            "strategy_id": "config_enable_centralized_delivery",
            "profile_id": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "resolution": {
                "strategy_id": "config_enable_centralized_delivery",
                "profile_id": "config_enable_centralized_delivery",
                "support_tier": "review_required_bundle",
                "resolved_inputs": {"delivery_bucket": "central-config-bucket"},
                "missing_inputs": [],
                "missing_defaults": [],
                "blocked_reasons": [],
                "rejected_profiles": [],
                "finding_coverage": {},
                "preservation_summary": {},
                "decision_rationale": "",
                "decision_version": "resolver/v1",
            },
        },
    ]
    run = MagicMock()
    run.id = uuid.uuid4()
    run.tenant_id = tenant.id
    run.action_id = uuid.uuid4()
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.pending
    run.artifacts = {
        "selected_strategy": "config_enable_centralized_delivery",
        "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
        "repo_target": {"repository": "acme/live", "base_branch": "main"},
        "group_bundle": {
            "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
            "action_ids": [action_one, action_two],
            "action_resolutions": action_resolutions,
        },
    }

    session = _mock_async_session(tenant, run)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-resend-canonical-group"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.is_local = True
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                r = client.post(f"/api/remediation-runs/{run.id}/resend")
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["group_action_ids"] == [action_one, action_two]
    assert payload["repo_target"] == {"repository": "acme/live", "base_branch": "main"}
    assert payload["action_resolutions"] == action_resolutions
    assert "resolution" not in payload


def test_create_group_pr_bundle_exception_only_strategy_rejected_400(client: TestClient) -> None:
    """Group PR creation rejects exception-only strategies before creating a run."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")
    action.account_id = "123456789012"
    action.region = "eu-north-1"
    action.status = "open"
    action.priority = 100

    actions_result = MagicMock()
    actions_result.scalars.return_value.unique.return_value.all.return_value = [action]
    account_result = MagicMock()
    account_result.scalar_one_or_none.return_value = None

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[actions_result, account_result])
    session.add = MagicMock()
    session.commit = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            try:
                r = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "aws_config_enabled",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "config_keep_exception",
                        "strategy_inputs": {
                            "exception_duration_days": "90",
                            "exception_reason": "Approved temporary exception during migration freeze.",
                        },
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Exception-only strategy"
        assert "Use Exception workflow instead of PR bundle." in str(detail.get("detail", ""))
        assert detail.get("exception_flow") == {
            "duration_days": 90,
            "reason": "Approved temporary exception during migration freeze.",
        }
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


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


def test_create_run_exception_only_strategy_rejected_400_no_run_created(client: TestClient) -> None:
    """Exception-only strategy selections must be routed to exception workflow, not PR runs."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")
    session = _mock_async_session(action, None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
            try:
                r = client.post(
                    "/api/remediation-runs",
                    json={
                        "action_id": str(action.id),
                        "mode": "pr_only",
                        "strategy_id": "config_keep_exception",
                        "strategy_inputs": {
                            "exception_duration_days": "14",
                            "exception_reason": "Short-term approved exception pending next change window.",
                        },
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Exception-only strategy"
        assert "Use Exception workflow instead of PR bundle." in str(detail.get("detail", ""))
        assert detail.get("exception_flow") == {
            "duration_days": 14,
            "reason": "Short-term approved exception pending next change window.",
        }
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_run_strategy_mode_mismatch_400(client: TestClient) -> None:
    """Deprecated direct_fix requests are rejected before strategy-mode mismatch handling."""
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
        assert detail.get("error") == "Direct-fix out of scope"
        assert "out of scope" in str(detail.get("detail", "")).lower()


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


def test_config_account_local_resolution_prefers_create_new_over_unproven_existing_bucket() -> None:
    from backend.services.remediation_run_resolution import resolve_create_profile_selection

    action = _mock_action("aws_config_enabled")
    strategy = next(
        item
        for item in list_strategies_for_action_type("aws_config_enabled")
        if item["strategy_id"] == "config_enable_account_local_delivery"
    )

    resolution = resolve_create_profile_selection(
        action_type="aws_config_enabled",
        strategy=strategy,
        requested_profile_id=None,
        explicit_inputs={},
        tenant_settings=None,
        runtime_signals={
            "context": {
                "default_inputs": {
                    "recording_scope": "keep_existing",
                    "delivery_bucket_mode": "use_existing",
                    "delivery_bucket": "config-bucket-123456789012",
                    "existing_bucket_name": "config-bucket-123456789012",
                }
            },
            "evidence": {"config_delivery_bucket_name": "config-bucket-123456789012"},
        },
        action=action,
    )

    assert resolution.support_tier == "deterministic_bundle"
    assert resolution.resolved_inputs["delivery_bucket_mode"] == "create_new"
    assert "existing_bucket_name" not in resolution.resolved_inputs
    assert resolution.persisted_strategy_inputs == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "create_new",
        "delivery_bucket": "config-bucket-123456789012",
    }


def test_validate_strategy_input_new_types_accept_valid_values() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "access_mode",
                "type": "select",
                "required": True,
                "description": "Access mode",
                "options": [
                    {"value": "close_public", "label": "Close public"},
                    {"value": "restrict_to_cidr", "label": "Restrict to CIDR"},
                ],
            },
            {
                "key": "dry_run",
                "type": "boolean",
                "required": True,
                "description": "Dry run",
            },
            {
                "key": "allowed_cidr",
                "type": "cidr",
                "required": True,
                "description": "Allowed CIDR",
            },
            {
                "key": "abort_days",
                "type": "number",
                "required": True,
                "description": "Abort days",
                "min": 1,
                "max": 365,
            },
        ]
    )

    normalized = validate_strategy_inputs(
        strategy,
        {
            "access_mode": "restrict_to_cidr",
            "dry_run": False,
            "allowed_cidr": "10.0.0.1/24",
            "abort_days": 7,
        },
    )

    assert normalized == {
        "access_mode": "restrict_to_cidr",
        "dry_run": False,
        "allowed_cidr": "10.0.0.0/24",
        "abort_days": 7,
    }


def test_validate_strategy_input_select_rejects_value_outside_options() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "access_mode",
                "type": "select",
                "required": True,
                "description": "Access mode",
                "options": [
                    {"value": "close_public", "label": "Close public"},
                    {"value": "restrict_to_cidr", "label": "Restrict to CIDR"},
                ],
            }
        ]
    )

    with pytest.raises(ValueError, match="strategy_inputs.access_mode must be one of"):
        validate_strategy_inputs(strategy, {"access_mode": "delete_everything"})


def test_validate_strategy_input_boolean_rejects_non_boolean() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "create_bucket_policy",
                "type": "boolean",
                "required": True,
                "description": "Create bucket policy",
            }
        ]
    )

    with pytest.raises(ValueError, match="strategy_inputs.create_bucket_policy must be a boolean"):
        validate_strategy_inputs(strategy, {"create_bucket_policy": "true"})


def test_validate_strategy_input_cidr_rejects_invalid_value() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "allowed_cidr",
                "type": "cidr",
                "required": True,
                "description": "Allowed CIDR",
            }
        ]
    )

    with pytest.raises(ValueError, match="strategy_inputs.allowed_cidr must be a valid CIDR"):
        validate_strategy_inputs(strategy, {"allowed_cidr": "not-a-cidr"})


def test_validate_strategy_input_number_enforces_type_and_bounds() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "abort_days",
                "type": "number",
                "required": True,
                "description": "Abort days",
                "min": 1,
                "max": 365,
            }
        ]
    )

    with pytest.raises(ValueError, match="strategy_inputs.abort_days must be a number"):
        validate_strategy_inputs(strategy, {"abort_days": "7"})

    with pytest.raises(ValueError, match="strategy_inputs.abort_days must be >= 1"):
        validate_strategy_inputs(strategy, {"abort_days": 0})

    with pytest.raises(ValueError, match="strategy_inputs.abort_days must be <= 365"):
        validate_strategy_inputs(strategy, {"abort_days": 400})


def test_validate_strategy_input_string_and_array_behavior_unchanged() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "delivery_bucket",
                "type": "string",
                "required": True,
                "description": "Delivery bucket",
            },
            {
                "key": "kms_key_arn",
                "type": "string",
                "required": False,
                "description": "KMS key ARN",
            },
            {
                "key": "exempt_principals",
                "type": "string_array",
                "required": True,
                "description": "Principal exemptions",
            },
        ]
    )

    normalized = validate_strategy_inputs(
        strategy,
        {
            "delivery_bucket": "  central-bucket  ",
            "kms_key_arn": "   ",
            "exempt_principals": [" arn:aws:iam::111111111111:role/a ", "", "arn:aws:iam::111111111111:role/a"],
        },
    )

    assert normalized == {
        "delivery_bucket": "central-bucket",
        "exempt_principals": ["arn:aws:iam::111111111111:role/a"],
    }


def test_validate_strategy_input_unknown_field_rejected() -> None:
    strategy = _mock_strategy_with_fields(
        [
            {
                "key": "delivery_bucket",
                "type": "string",
                "required": True,
                "description": "Delivery bucket",
            }
        ]
    )

    with pytest.raises(ValueError, match="strategy_inputs contains unknown field"):
        validate_strategy_inputs(strategy, {"delivery_bucket": "central", "extra": "value"})


def test_validate_strategy_input_iam_root_action_mode_accepts_matching_strategy() -> None:
    """IAM root action_mode is optional but accepted when it matches selected strategy."""
    strategies = {
        strategy["strategy_id"]: strategy
        for strategy in list_strategies_for_action_type("iam_root_access_key_absent")
    }
    disable_strategy = strategies["iam_root_key_disable"]
    delete_strategy = strategies["iam_root_key_delete"]

    assert validate_strategy_inputs(disable_strategy, {}) == {}
    assert validate_strategy_inputs(disable_strategy, {"action_mode": "disable_key"}) == {
        "action_mode": "disable_key"
    }
    assert validate_strategy_inputs(delete_strategy, {"action_mode": "delete_key"}) == {
        "action_mode": "delete_key"
    }


def test_validate_strategy_input_iam_root_action_mode_mismatch_rejected() -> None:
    """IAM root action_mode must map to the selected existing strategy ID."""
    strategies = {
        strategy["strategy_id"]: strategy
        for strategy in list_strategies_for_action_type("iam_root_access_key_absent")
    }

    with pytest.raises(ValueError, match="requires strategy_id 'iam_root_key_delete'"):
        validate_strategy_inputs(strategies["iam_root_key_disable"], {"action_mode": "delete_key"})

    with pytest.raises(ValueError, match="requires strategy_id 'iam_root_key_disable'"):
        validate_strategy_inputs(strategies["iam_root_key_delete"], {"action_mode": "disable_key"})


def test_create_run_root_key_strategy_requires_dedicated_route(client: TestClient) -> None:
    """IAM.4 generic single-run creation must defer to the dedicated root-key API."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="iam_root_access_key_absent")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn=None)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(action, account)

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
                    "strategy_id": "iam_root_key_delete",
                    "risk_acknowledged": True,
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert isinstance(detail, dict)
    assert detail.get("reason") == "root_key_execution_authority"
    assert detail.get("execution_authority") == ROOT_KEY_EXECUTION_AUTHORITY_PATH


def test_group_pr_bundle_root_key_strategy_requires_dedicated_route(client: TestClient) -> None:
    """IAM.4 generic grouped creation must not produce a usable alternate path."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    session = _mock_async_session(tenant)

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

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
                    "action_type": "iam_root_access_key_absent",
                    "account_id": "123456789012",
                    "status": "open",
                    "region": "us-east-1",
                    "strategy_id": "iam_root_key_disable",
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("reason") == "root_key_execution_authority"
    assert detail.get("execution_authority") == ROOT_KEY_EXECUTION_AUTHORITY_PATH


def test_resend_root_key_run_requires_dedicated_route(client: TestClient) -> None:
    """Pending legacy IAM.4 generic runs cannot be re-enqueued through the generic resend route."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="iam_root_access_key_absent")
    action.tenant_id = tenant.id
    run = _mock_existing_run(
        action,
        status=RemediationRunStatus.pending,
        artifacts={
            "manual_high_risk": {
                "requires_root_credentials": True,
                "action_type": "iam_root_access_key_absent",
            }
        },
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(run)

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        try:
            r = client.post(f"/api/remediation-runs/{run.id}/resend")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("reason") == "root_key_execution_authority"
    assert detail.get("execution_authority") == ROOT_KEY_EXECUTION_AUTHORITY_PATH


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


def test_create_run_cloudtrail_warn_requires_risk_ack_400(client: TestClient) -> None:
    """CloudTrail guided PR-bundle creation requires risk acknowledgment instead of fail-closed blocking."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="cloudtrail_enabled")

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
                            "strategy_id": "cloudtrail_enable_guided",
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
                    app.dependency_overrides.pop(get_current_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert isinstance(detail, dict)
    assert detail.get("error") == "Risk acknowledgement required"
    checks = detail.get("risk_snapshot", {}).get("checks", [])
    codes = {check.get("code") for check in checks if isinstance(check, dict)}
    assert "cloudtrail_cost_impact" in codes
    assert "cloudtrail_log_bucket_prereq" in codes
    assert "risk_evaluation_not_specialized" not in codes
    metric_names = [call.args[1] for call in mock_metric.call_args_list if len(call.args) >= 2]
    assert "risk_ack_required_count" in metric_names
    assert "risk_ack_missing_rejection_count" in metric_names
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


def test_remediation_options_marks_exception_only_strategies(client: TestClient) -> None:
    """Remediation options payload includes machine-readable exception_only flags."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = {item["strategy_id"]: item for item in r.json().get("strategies", [])}
    assert strategies["config_keep_exception"]["exception_only"] is True
    assert strategies["config_keep_exception"]["supports_exception_flow"] is True
    assert strategies["config_enable_account_local_delivery"]["exception_only"] is False
    exception_fields = strategies["config_keep_exception"]["input_schema"]["fields"]
    assert [field["key"] for field in exception_fields] == ["exception_duration_days", "exception_reason"]


def test_remediation_options_root_action_exposes_runbook_notice(client: TestClient) -> None:
    """Root-key remediation options include root-credentials notice and runbook link."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="iam_root_access_key_absent")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    body = r.json()
    assert body.get("manual_high_risk") is True
    assert "Root credentials required" in str(body.get("pre_execution_notice", ""))
    assert body.get("runbook_url") == "docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md"
    strategies = {item["strategy_id"]: item for item in body.get("strategies", [])}
    disable_field = strategies["iam_root_key_disable"]["input_schema"]["fields"][0]
    delete_field = strategies["iam_root_key_delete"]["input_schema"]["fields"][0]
    for field in (disable_field, delete_field):
        assert field["key"] == "action_mode"
        assert field["type"] == "select"
        option_values = [option["value"] for option in field.get("options", [])]
        assert option_values == ["disable_key", "delete_key"]
        for option in field.get("options", []):
            assert option.get("impact_text")


@pytest.mark.parametrize(
    ("action_type", "expected_impact_fragment", "expected_estimate", "expected_supports_reeval"),
    [
        (
            "enable_security_hub",
            "AWS Security Hub will be enabled in this region.",
            "~1 hour",
            False,
        ),
        (
            "enable_guardduty",
            "Amazon GuardDuty will be enabled in this region.",
            "~1 hour",
            False,
        ),
        ("ssm_block_public_sharing", "Public sharing of SSM documents", "12-24 hours", True),
        ("ebs_snapshot_block_public_access", "Public access to EBS snapshots", "12-24 hours", True),
        (
            "ebs_default_encryption",
            "All new EBS volumes in this region will be encrypted by default.",
            "12-24 hours",
            True,
        ),
    ],
)
def test_remediation_options_simple_controls_expose_non_empty_impact_text(
    client: TestClient,
    action_type: str,
    expected_impact_fragment: str,
    expected_estimate: str,
    expected_supports_reeval: bool,
) -> None:
    """Task 7: simple-control remediation options include non-empty strategy impact_text metadata."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type=action_type)
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    body = r.json()
    strategies = body.get("strategies", [])
    assert strategies

    for strategy in strategies:
        assert "impact_text" in strategy
        assert str(strategy.get("impact_text") or "").strip()
        assert str(strategy.get("estimated_resolution_time") or "").strip()
        assert isinstance(strategy.get("supports_immediate_reeval"), bool)

    assert any(
        expected_impact_fragment in str(strategy.get("impact_text") or "")
        for strategy in strategies
    )
    assert all(
        str(strategy.get("estimated_resolution_time") or "") == expected_estimate
        for strategy in strategies
    )
    non_exception_strategies = [strategy for strategy in strategies if not bool(strategy.get("exception_only"))]
    assert non_exception_strategies
    assert all(
        bool(strategy.get("supports_immediate_reeval")) is expected_supports_reeval
        for strategy in non_exception_strategies
    )
    exception_strategies = [strategy for strategy in strategies if bool(strategy.get("exception_only"))]
    assert all(
        bool(strategy.get("supports_immediate_reeval")) is False
        for strategy in exception_strategies
    )

    if action_type in {"enable_security_hub", "enable_guardduty"}:
        assert set(body.get("mode_options", [])) == {"pr_only"}


@pytest.mark.parametrize(
    ("action_type", "expected_estimate", "expected_non_exception_supports_reeval"),
    [
        ("aws_config_enabled", "1-6 hours", True),
        ("cloudtrail_enabled", "1-6 hours", True),
        ("sg_restrict_public_ports", "12-24 hours", True),
    ],
)
def test_remediation_options_include_estimate_and_reeval_metadata(
    client: TestClient,
    action_type: str,
    expected_estimate: str,
    expected_non_exception_supports_reeval: bool,
) -> None:
    """Task 14: strategy metadata includes estimated resolution and re-eval support flags."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type=action_type)
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = r.json().get("strategies", [])
    assert strategies
    non_exception_strategies = [strategy for strategy in strategies if not bool(strategy.get("exception_only"))]
    assert non_exception_strategies
    for strategy in strategies:
        assert strategy.get("estimated_resolution_time") == expected_estimate
    for strategy in non_exception_strategies:
        assert strategy.get("supports_immediate_reeval") is expected_non_exception_supports_reeval
    for strategy in strategies:
        if bool(strategy.get("exception_only")):
            assert strategy.get("supports_immediate_reeval") is False


@pytest.mark.parametrize(
    ("action_type", "expected_blast_radius"),
    [
        ("s3_block_public_access", "account"),
        ("s3_bucket_block_public_access", "resource"),
        ("s3_bucket_encryption", "resource"),
        ("aws_config_enabled", "account"),
        ("cloudtrail_enabled", "resource"),
        ("enable_security_hub", "account"),
        ("enable_guardduty", "account"),
        ("ssm_block_public_sharing", "account"),
        ("ebs_snapshot_block_public_access", "account"),
        ("ebs_default_encryption", "account"),
        ("s3_bucket_access_logging", "resource"),
        ("s3_bucket_lifecycle_configuration", "resource"),
        ("s3_bucket_encryption_kms", "resource"),
        ("s3_bucket_require_ssl", "resource"),
        ("sg_restrict_public_ports", "access_changing"),
        ("iam_root_access_key_absent", "access_changing"),
    ],
)
def test_remediation_options_include_blast_radius_metadata_for_all_controls(
    client: TestClient,
    action_type: str,
    expected_blast_radius: str,
) -> None:
    """Task 15: remediation options expose blast-radius metadata for all 16 in-scope controls."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type=action_type)
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = r.json().get("strategies", [])
    assert strategies
    for strategy in strategies:
        assert strategy.get("blast_radius") in {"account", "resource", "access_changing"}
        assert strategy.get("blast_radius") == expected_blast_radius


@pytest.mark.parametrize(
    ("action_type", "expected_rollback_fragment"),
    [
        ("s3_block_public_access", "delete-public-access-block --account-id <ACCOUNT_ID>"),
        ("s3_bucket_block_public_access", "delete-public-access-block --bucket <BUCKET_NAME>"),
        ("s3_bucket_encryption", "delete-bucket-encryption --bucket <BUCKET_NAME>"),
        (
            "aws_config_enabled",
            "stop-configuration-recorder --configuration-recorder-name <RECORDER_NAME>",
        ),
        ("cloudtrail_enabled", "cloudtrail stop-logging --name <TRAIL_NAME>"),
        ("enable_security_hub", "securityhub disable-security-hub"),
        ("enable_guardduty", "guardduty delete-detector --detector-id <DETECTOR_ID>"),
        (
            "ssm_block_public_sharing",
            "/ssm/documents/console/public-sharing-permission --setting-value Enable",
        ),
        ("ebs_snapshot_block_public_access", "disable-snapshot-block-public-access"),
        ("ebs_default_encryption", "disable-ebs-encryption-by-default"),
        ("s3_bucket_access_logging", "put-bucket-logging --bucket <SOURCE_BUCKET>"),
        ("s3_bucket_lifecycle_configuration", "delete-bucket-lifecycle --bucket <BUCKET_NAME>"),
        ("s3_bucket_encryption_kms", "file://pre-remediation-encryption.json"),
        ("s3_bucket_require_ssl", "put-bucket-policy --bucket <BUCKET_NAME>"),
        (
            "sg_restrict_public_ports",
            "authorize-security-group-ingress --group-id <SECURITY_GROUP_ID>",
        ),
        ("iam_root_access_key_absent", "update-access-key --access-key-id <ROOT_ACCESS_KEY_ID>"),
    ],
)
def test_remediation_options_include_rollback_command_for_all_controls(
    client: TestClient,
    action_type: str,
    expected_rollback_fragment: str,
) -> None:
    """Task 13: remediation options expose rollback commands for all 16 in-scope controls."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type=action_type)
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = r.json().get("strategies", [])
    assert strategies

    for strategy in strategies:
        rollback_command = str(strategy.get("rollback_command") or "").strip()
        assert rollback_command

    assert any(
        expected_rollback_fragment in str(strategy.get("rollback_command") or "")
        for strategy in strategies
    )


def test_remediation_options_s3_ssl_warns_to_capture_existing_policy_before_apply(client: TestClient) -> None:
    """S3.5 options should warn operators to capture the current bucket policy before apply."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_require_ssl")
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
    strategies = response.json().get("strategies", [])
    assert any(
        any("get-bucket-policy --bucket <BUCKET_NAME>" in str(warning) for warning in strategy.get("warnings") or [])
        for strategy in strategies
        if strategy.get("strategy_id") == "s3_enforce_ssl_strict_deny"
    )


def test_remediation_options_s3_kms_warns_to_capture_existing_encryption_before_apply(
    client: TestClient,
) -> None:
    """S3.15 options should warn operators to capture the current bucket encryption before apply."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_encryption_kms")
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
    strategies = response.json().get("strategies", [])
    assert any(
        any("Capture the current bucket encryption configuration before apply" in str(warning) for warning in strategy.get("warnings") or [])
        for strategy in strategies
        if strategy.get("strategy_id") == "s3_enable_sse_kms_guided"
    )


def test_remediation_options_root_delete_strategy_exposes_delete_specific_rollback(client: TestClient) -> None:
    """Root-key delete strategy should expose a create-access-key rollback recipe."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="iam_root_access_key_absent")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, None)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/actions/{action.id}/remediation-options")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = {item["strategy_id"]: item for item in r.json().get("strategies", [])}
    assert strategies["iam_root_key_delete"]["rollback_command"] == "aws iam create-access-key"


def test_trigger_reeval_enqueues_reconcile_jobs(client: TestClient) -> None:
    """Task 14: POST trigger-reeval enqueues inventory shard jobs for the action scope."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="sg_restrict_public_ports")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account.regions = ["us-east-1"]

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action, account)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "reeval-msg-1"}
    with patch("backend.routers.actions.boto3.client", return_value=mock_sqs):
        with patch("backend.routers.actions.settings") as mock_settings:
            mock_settings.has_inventory_reconcile_queue = True
            mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/reconcile"
            mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]
            mock_settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD = 500
            mock_settings.AWS_REGION = "us-east-1"
            try:
                r = client.post(
                    f"/api/actions/{action.id}/trigger-reeval",
                    json={"strategy_id": "sg_restrict_public_ports_guided"},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 202
    body = r.json()
    assert body["action_id"] == str(action.id)
    assert body["strategy_id"] == "sg_restrict_public_ports_guided"
    assert body["estimated_resolution_time"] == "12-24 hours"
    assert body["supports_immediate_reeval"] is True
    assert body["enqueued_jobs"] == 2
    assert mock_sqs.send_message.call_count == 2
    first_payload = json.loads(mock_sqs.send_message.call_args_list[0].kwargs["MessageBody"])
    assert first_payload["job_type"] == "reconcile_inventory_shard"
    assert first_payload["account_id"] == action.account_id
    assert first_payload["region"] == action.region


def test_trigger_reeval_rejects_unsupported_strategy(client: TestClient) -> None:
    """Task 14: immediate re-evaluation rejects direct-fix strategy IDs that are no longer exposed."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="enable_security_hub")
    action.tenant_id = tenant.id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_async_session(tenant, action)

    async def mock_get_optional_user() -> MagicMock:
        return user

    from backend.auth import get_optional_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.post(
            f"/api/actions/{action.id}/trigger-reeval",
            json={"strategy_id": "security_hub_enable_direct_fix"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 400
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        assert detail.get("error") == "Invalid strategy_id"


def test_remediation_options_s3_dependency_pass_when_runtime_indicates_no_public_dependency(client: TestClient) -> None:
    """S3 remediation options should surface runtime-based pass when bucket is non-public and no website is configured."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_block_public_access")
    action.tenant_id = tenant.id
    action.target_id = "arn:aws:s3:::b1-private-bucket"
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")
    account.role_read_arn = "arn:aws:iam::123456789012:role/ReadRole"

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
        },
    ) as mock_collect:
        try:
            r = client.get(f"/api/actions/{action.id}/remediation-options")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    strategies = {item["strategy_id"]: item for item in r.json().get("strategies", [])}
    standard = strategies["s3_bucket_block_public_access_standard"]
    checks = {item["code"]: item for item in standard["dependency_checks"]}
    assert checks["s3_public_access_dependency"]["status"] == "pass"
    assert mock_collect.call_count >= 1


# ---------------------------------------------------------------------------
# GET remediation-preview (8.4)
# ---------------------------------------------------------------------------


def test_remediation_preview_action_not_fixable(client: TestClient) -> None:
    """Preview for direct_fix now returns the out-of-scope message."""
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
            f"/api/actions/{action.id}/remediation-preview",
            params={"mode": "direct_fix", "tenant_id": str(tenant.id)},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is False
    assert "out of scope" in data["message"].lower()
    assert data["before_state"] == {}
    assert data["after_state"] == {}
    assert data["diff_lines"] == []


def test_remediation_preview_no_write_role(client: TestClient) -> None:
    """Preview returns out-of-scope before any WriteRole handling."""
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
    try:
        r = client.get(
            f"/api/actions/{action.id}/remediation-preview",
            params={"mode": "direct_fix", "tenant_id": str(tenant.id)},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert "out of scope" in data["message"].lower()


def test_remediation_preview_pr_only_includes_choice_impact_summary(client: TestClient) -> None:
    """pr_only preview includes impact summary derived from selected strategy choices."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="sg_restrict_public_ports")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

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
                "public_admin_ipv4_ports": [22, 3389],
                "public_admin_ipv6_ports": [],
            }
        },
    ):
        try:
            r = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "tenant_id": str(tenant.id),
                    "strategy_id": "sg_restrict_public_ports_guided",
                    "strategy_inputs": json.dumps({"access_mode": "close_and_revoke"}),
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is False
    assert "informational only" in data["message"]
    assert isinstance(data.get("impact_summary"), str)
    assert "automatically removed" in data["impact_summary"]
    assert isinstance(data.get("before_state"), dict)
    assert isinstance(data.get("after_state"), dict)
    assert isinstance(data.get("diff_lines"), list)
    assert any(
        line.get("type") == "remove" and line.get("label") == "Public admin ingress (IPv4)"
        for line in data["diff_lines"]
    )
    assert any(
        line.get("type") == "add" and line.get("label") == "Restricted admin ingress (IPv4)"
        for line in data["diff_lines"]
    )


def test_remediation_preview_pr_only_s3_5_includes_before_after_simulation(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="s3_bucket_require_ssl")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

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
                "target_bucket": "example-bucket",
                "s3_ssl_deny_present": False,
                "existing_bucket_policy_statement_count": 2,
            }
        },
    ):
        try:
            r = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "tenant_id": str(tenant.id),
                    "strategy_id": "s3_enforce_ssl_strict_deny",
                    "strategy_inputs": json.dumps({"preserve_existing_policy": True}),
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["before_state"]["bucket"] == "example-bucket"
    assert data["before_state"]["ssl_enforced"] is False
    assert data["after_state"]["ssl_enforced"] is True
    assert any(
        line.get("type") == "add" and line.get("label") == "HTTPS-only access"
        for line in data["diff_lines"]
    )


def test_remediation_preview_pr_only_config_1_includes_before_after_simulation(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action(action_type="aws_config_enabled")
    action.tenant_id = tenant.id
    account = _mock_account(role_write_arn="arn:aws:iam::123456789012:role/WriteRole")

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
                "config_recorder_exists": False,
                "config_recording_scope": "not_configured",
                "config_delivery_bucket_name": None,
            }
        },
    ):
        try:
            r = client.get(
                f"/api/actions/{action.id}/remediation-preview",
                params={
                    "mode": "pr_only",
                    "tenant_id": str(tenant.id),
                    "strategy_id": "config_enable_centralized_delivery",
                    "strategy_inputs": json.dumps(
                        {
                            "recording_scope": "all_resources",
                            "delivery_bucket_mode": "use_existing",
                            "existing_bucket_name": "security-autopilot-config-123456789012-us-east-1",
                            "delivery_bucket": "security-autopilot-config-123456789012-us-east-1",
                        }
                    ),
                },
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["before_state"]["recorder_enabled"] is False
    assert data["after_state"]["recorder_enabled"] is True
    assert data["after_state"]["delivery_bucket"] == "security-autopilot-config-123456789012-us-east-1"
    assert any(
        line.get("type") == "add" and line.get("label") == "Configuration recorder"
        for line in data["diff_lines"]
    )


def test_remediation_preview_direct_fix_returns_out_of_scope_message(client: TestClient) -> None:
    """direct_fix preview returns the out-of-scope message instead of assuming WriteRole."""
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

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(
            f"/api/actions/{action.id}/remediation-preview",
            params={"mode": "direct_fix", "tenant_id": str(tenant.id)},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is False
    assert "out of scope" in data["message"].lower()


def test_remediation_preview_direct_fix_includes_strategy_impact_summary(client: TestClient) -> None:
    """direct_fix preview stays out of scope even when a direct-fix strategy_id is sent."""
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

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(
            f"/api/actions/{action.id}/remediation-preview",
            params={
                "mode": "direct_fix",
                "tenant_id": str(tenant.id),
                "strategy_id": "s3_account_block_public_access_direct_fix",
            },
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["compliant"] is False
    assert data["will_apply"] is False
    assert "out of scope" in data["message"].lower()
    assert data.get("impact_summary") == "All four account-level public access block settings will be enabled."


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


def test_get_run_detail_includes_artifact_metadata_and_closure_links(client: TestClient) -> None:
    """GET /remediation-runs/{id} returns normalized artifact metadata for handoff-free closure."""
    from backend.auth import get_optional_user

    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_action("sg_restrict_public_ports")
    action.id = uuid.uuid4()
    action.title = "Restrict public admin ports"
    action.account_id = "123456789012"
    action.region = "us-east-1"
    action.status = "resolved"

    run_id = uuid.uuid4()
    run = MagicMock()
    run.id = run_id
    run.tenant_id = tenant.id
    run.action_id = action.id
    run.mode = RemediationRunMode.pr_only
    run.status = RemediationRunStatus.success
    run.outcome = "SaaS apply completed successfully."
    run.logs = "generated bundle\napplied change summary"
    run.started_at = datetime(2026, 3, 4, 10, 10, tzinfo=timezone.utc)
    run.completed_at = datetime(2026, 3, 4, 10, 12, tzinfo=timezone.utc)
    run.created_at = datetime(2026, 3, 4, 10, 9, tzinfo=timezone.utc)
    run.updated_at = datetime(2026, 3, 4, 10, 12, tzinfo=timezone.utc)
    run.approved_by_user_id = user.id
    run.action = action
    run.artifacts = {
        "pr_bundle": {
            "format": "terraform",
            "files": [
                {"path": "main.tf", "content": 'terraform {}'},
                {"path": "README.md", "content": "# Review and apply"},
            ],
            "steps": ["Review", "Apply"],
            "metadata": {
                "generated_action_count": 1,
                "skipped_action_count": 0,
            },
        },
        "change_summary": {
            "run_id": str(run_id),
            "applied_at": "2026-03-04T10:12:00+00:00",
            "applied_by": "ops@example.com",
            "changes": [
                {
                    "field": "allowed cidr",
                    "before": "0.0.0.0/0",
                    "after": "10.0.0.0/24",
                }
            ],
        },
        "risk_snapshot": {
            "checks": [{"code": "review_complete", "status": "pass"}],
            "recommendation": "apply",
        },
    }

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = _mock_async_session(tenant, run)
        yield session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        r = client.get(f"/api/remediation-runs/{run_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert r.status_code == 200
    data = r.json()
    assert data["action"]["status"] == "resolved"
    implementation_artifacts = data["artifact_metadata"]["implementation_artifacts"]
    assert [artifact["key"] for artifact in implementation_artifacts] == ["pr_bundle", "change_summary"]
    assert implementation_artifacts[0]["href"] == f"/remediation-runs/{run_id}#run-generated-files"
    assert implementation_artifacts[1]["href"] == f"/remediation-runs/{run_id}#run-activity"

    evidence_pointers = {pointer["key"]: pointer for pointer in data["artifact_metadata"]["evidence_pointers"]}
    assert "activity_log" in evidence_pointers
    assert "risk_snapshot" in evidence_pointers
    assert evidence_pointers["risk_snapshot"]["href"] == f"/remediation-runs/{run_id}#run-generated-files"

    checklist = {item["id"]: item for item in data["artifact_metadata"]["closure_checklist"]}
    assert checklist["artifact_recorded"]["status"] == "complete"
    assert checklist["evidence_attached"]["status"] == "complete"
    assert checklist["action_closure_verified"]["status"] == "complete"
    assert "pr_bundle" in checklist["artifact_recorded"]["evidence_keys"]


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


def test_get_pr_bundle_zip_is_deterministic_for_same_artifacts(client: TestClient) -> None:
    """Repeated downloads for unchanged artifacts should return byte-identical ZIP payloads."""
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    run_id = str(uuid.uuid4())
    run = MagicMock()
    run.id = uuid.UUID(run_id)
    run.tenant_id = tenant.id
    run.artifacts = {
        "pr_bundle": {
            "files": [
                {"path": "z.tf", "content": "z"},
                {"path": "a.tf", "content": "a"},
            ],
        },
    }

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        session = _mock_async_session(tenant, run)
        yield session

    from backend.auth import get_optional_user

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        first = client.get(f"/api/remediation-runs/{run_id}/pr-bundle.zip")
        second = client.get(f"/api/remediation-runs/{run_id}/pr-bundle.zip")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content


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


def _assert_archived_saas_bundle_execution_response(response) -> None:
    assert response.status_code == 410
    detail = response.json().get("detail", {})
    assert detail == {
        "error": "SaaS bundle execution archived",
        "reason": "saas_bundle_execution_archived",
        "detail": (
            "PR bundles remain supported. Download the bundle, review the generated artifacts, "
            "and run it with your own credentials or pipeline outside the SaaS. "
            "Optional grouped reporting callbacks remain supported for customer-run bundles."
        ),
    }


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/remediation-runs/run-archived/execute-pr-bundle", {}),
        ("/api/remediation-runs/run-archived/approve-apply", None),
        ("/api/remediation-runs/bulk-execute-pr-bundle", {"run_ids": ["run-1"]}),
        ("/api/remediation-runs/bulk-approve-apply", {"run_ids": ["run-1"]}),
    ],
)
def test_saas_bundle_execution_routes_return_archived_410_and_do_not_enqueue(
    client: TestClient,
    path: str,
    payload: dict[str, object] | None,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    with patch("backend.routers.remediation_runs.boto3.client") as mock_boto_client:
        with patch(
            "backend.routers.remediation_runs.build_pr_bundle_execution_job_payload"
        ) as mock_build_payload:
            with patch(
                "backend.routers.remediation_runs._tenant_active_execution_count",
                new_callable=AsyncMock,
                return_value=0,
            ) as mock_active_count:
                with patch(
                    "backend.routers.remediation_runs._assert_tenant_execution_capacity",
                    new_callable=AsyncMock,
                ) as mock_capacity_check:
                    try:
                        if payload is None:
                            response = client.post(path)
                        else:
                            response = client.post(path, json=payload)
                    finally:
                        app.dependency_overrides.pop(get_current_user, None)

    _assert_archived_saas_bundle_execution_response(response)
    assert mock_boto_client.call_count == 0
    assert mock_build_payload.call_count == 0
    assert mock_active_count.await_count == 0
    assert mock_capacity_check.await_count == 0
