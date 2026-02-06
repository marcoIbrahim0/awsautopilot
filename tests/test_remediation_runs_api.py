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
from backend.models.enums import RemediationRunMode, RemediationRunStatus


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
