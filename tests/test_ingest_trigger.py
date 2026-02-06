"""
Unit tests for POST /api/aws/accounts/{account_id}/ingest (Step 2.6).

Mock auth (tenant), DB (account lookup), and SQS per implementation plan.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.main import app
from backend.models.enums import AwsAccountStatus


def _mock_session(account: object | None) -> MagicMock:
    """Build mock AsyncSession where execute().scalar_one_or_none() returns `account`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = account
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result)
    return session


async def _mock_get_db_with_account(
    *,
    status: AwsAccountStatus = AwsAccountStatus.validated,
    regions: list[str] | None = None,
) -> AsyncGenerator[MagicMock, None]:
    acc = MagicMock()
    acc.status = status
    acc.regions = regions if regions is not None else ["us-east-1", "us-west-2"]
    yield _mock_session(acc)


def _ingest_url(account_id: str = "123456789012") -> str:
    return f"/api/aws/accounts/{account_id}/ingest"


def _ingest_params(tenant_id: str = "123e4567-e89b-12d3-a456-426614174000") -> dict:
    return {"tenant_id": tenant_id}


# ---------------------------------------------------------------------------
# 503 — Queue not configured
# ---------------------------------------------------------------------------


def test_ingest_503_queue_not_configured(client: TestClient) -> None:
    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = False
        r = client.post(_ingest_url(), params=_ingest_params())
    assert r.status_code == 503
    body = r.json()
    assert body["detail"]["error"] == "Ingestion service unavailable"
    assert "SQS_INGEST_QUEUE_URL" in body["detail"]["detail"] or "queue" in body["detail"]["detail"].lower()


# ---------------------------------------------------------------------------
# 400 — Invalid tenant_id
# ---------------------------------------------------------------------------


def test_ingest_400_invalid_tenant_id(client: TestClient) -> None:
    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        r = client.post(_ingest_url(), params={"tenant_id": "not-a-uuid"})
    assert r.status_code == 400
    detail = r.json().get("detail")
    # API may return detail as string or as dict
    if isinstance(detail, str):
        assert "tenant_id" in detail.lower() or "uuid" in detail.lower()
    else:
        assert detail.get("error") == "Bad request" or "tenant_id" in str(detail.get("detail", "")).lower()


# ---------------------------------------------------------------------------
# 404 — Tenant not found
# ---------------------------------------------------------------------------


def test_ingest_404_tenant_not_found(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_session(None)

    async def _get_tenant_404(_tid: uuid.UUID, _db: object) -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="x")

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock, side_effect=_get_tenant_404):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(_ingest_url(), params=_ingest_params())
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "Tenant not found"


# ---------------------------------------------------------------------------
# 404 — Account not found
# ---------------------------------------------------------------------------


def test_ingest_404_account_not_found(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield _mock_session(None)

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock) as gt:
            gt.return_value = None  # pass through, no raise
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(_ingest_url(), params=_ingest_params())
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "Account not found"


# ---------------------------------------------------------------------------
# 409 — Account not validated
# ---------------------------------------------------------------------------


def test_ingest_409_account_not_validated(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(status=AwsAccountStatus.error):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(_ingest_url(), params=_ingest_params())
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "Account not validated"


# ---------------------------------------------------------------------------
# 400 — No regions configured
# ---------------------------------------------------------------------------


def test_ingest_400_no_regions_configured(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=[]):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(_ingest_url(), params=_ingest_params())
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "Bad request"
    assert "region" in r.json()["detail"]["detail"].lower()


# ---------------------------------------------------------------------------
# 400 — Regions override empty
# ---------------------------------------------------------------------------


def test_ingest_400_regions_override_empty(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=["us-east-1"]):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(
                    _ingest_url(),
                    params=_ingest_params(),
                    json={"regions": []},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 400
    assert "regions" in r.json()["detail"]["detail"].lower() or "empty" in r.json()["detail"]["detail"].lower()


# ---------------------------------------------------------------------------
# 400 — Regions override not a subset
# ---------------------------------------------------------------------------


def test_ingest_400_regions_override_not_subset(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=["eu-west-1"]):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            app.dependency_overrides[get_db] = mock_get_db
            try:
                r = client.post(
                    _ingest_url(),
                    params=_ingest_params(),
                    json={"regions": ["us-east-1"]},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 400
    assert "subset" in r.json()["detail"]["detail"].lower() or "region" in r.json()["detail"]["detail"].lower()


# ---------------------------------------------------------------------------
# 202 — Success (no body, use account regions)
# ---------------------------------------------------------------------------


def test_ingest_202_success_no_body(client: TestClient) -> None:
    """Multi-region: account with 2 regions enqueues 2 jobs (Step 2.7)."""
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=["us-east-1", "us-west-2"]):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            with patch("backend.routers.aws_accounts._enqueue_ingest_jobs") as enq:
                enq.return_value = ["msg-1", "msg-2"]
                app.dependency_overrides[get_db] = mock_get_db
                try:
                    r = client.post(_ingest_url(), params=_ingest_params())
                finally:
                    app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 202
    data = r.json()
    assert data["account_id"] == "123456789012"
    assert data["jobs_queued"] == 2
    assert data["regions"] == ["us-east-1", "us-west-2"]
    assert data["message_ids"] == ["msg-1", "msg-2"]
    assert "queued" in data["message"].lower()
    # Step 2.7: _enqueue_ingest_jobs called with tenant_id, account_id, and exact regions list
    enq.assert_called_once()
    call_args = enq.call_args[0]
    assert call_args[2] == ["us-east-1", "us-west-2"]


# ---------------------------------------------------------------------------
# 202 — Success with regions override
# ---------------------------------------------------------------------------


def test_ingest_202_success_with_regions_override(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=["us-east-1", "us-west-2", "eu-west-1"]):
            yield s

    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            with patch("backend.routers.aws_accounts._enqueue_ingest_jobs") as enq:
                enq.return_value = ["msg-1"]
                app.dependency_overrides[get_db] = mock_get_db
                try:
                    r = client.post(
                        _ingest_url(),
                        params=_ingest_params(),
                        json={"regions": ["us-east-1"]},
                    )
                finally:
                    app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 202
    data = r.json()
    assert data["jobs_queued"] == 1
    assert data["regions"] == ["us-east-1"]
    assert data["message_ids"] == ["msg-1"]
    enq.assert_called_once()
    call_kw = enq.call_args
    assert call_kw[0][2] == ["us-east-1"]  # regions arg


# ---------------------------------------------------------------------------
# Step 2.7 — Multi-region: N regions → N SQS messages
# ---------------------------------------------------------------------------


def test_enqueue_ingest_jobs_sends_one_message_per_region() -> None:
    """Step 2.7: _enqueue_ingest_jobs sends exactly one SQS message per region."""
    import json
    from unittest.mock import MagicMock

    from backend.routers.aws_accounts import _enqueue_ingest_jobs

    tenant_id = uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
    account_id = "123456789012"
    regions = ["us-east-1", "us-west-2", "eu-west-1"]

    sqs = MagicMock()
    sqs.send_message.side_effect = [
        {"MessageId": "id-1"},
        {"MessageId": "id-2"},
        {"MessageId": "id-3"},
    ]

    with patch("backend.routers.aws_accounts.settings") as m:
        m.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/queue"
        m.AWS_REGION = "us-east-1"
        with patch("backend.routers.aws_accounts.boto3.client", return_value=sqs):
            ids = _enqueue_ingest_jobs(tenant_id, account_id, regions)

    assert ids == ["id-1", "id-2", "id-3"]
    assert sqs.send_message.call_count == 3
    for i, region in enumerate(regions):
        call = sqs.send_message.call_args_list[i]
        body = json.loads(call.kwargs["MessageBody"])
        assert body["region"] == region
        assert body["account_id"] == account_id
        assert body["tenant_id"] == str(tenant_id)
        assert body["job_type"] == "ingest_findings"


# ---------------------------------------------------------------------------
# 503 — SQS send failure
# ---------------------------------------------------------------------------


def test_ingest_503_sqs_failure(client: TestClient) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        async for s in _mock_get_db_with_account(regions=["us-east-1"]):
            yield s

    err = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "SendMessage")
    with patch("backend.routers.aws_accounts.settings") as m:
        m.has_ingest_queue = True
        with patch("backend.routers.aws_accounts.get_tenant", new_callable=AsyncMock):
            with patch("backend.routers.aws_accounts._enqueue_ingest_jobs", side_effect=err):
                app.dependency_overrides[get_db] = mock_get_db
                try:
                    r = client.post(_ingest_url(), params=_ingest_params())
                finally:
                    app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "Ingestion service unavailable"
