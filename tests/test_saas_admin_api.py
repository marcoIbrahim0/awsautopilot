from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.auth import get_current_user, require_saas_admin
from backend.database import get_db
from backend.main import app


def _result(
    *,
    scalar: object | None = None,
    scalar_one_or_none: object | None = None,
    scalars_all: list | None = None,
    all_rows: list | None = None,
) -> MagicMock:
    res = MagicMock()
    res.scalar.return_value = scalar
    res.scalar_one_or_none.return_value = scalar_one_or_none
    if scalars_all is not None:
        res.scalars.return_value.all.return_value = scalars_all
    if all_rows is not None:
        res.all.return_value = all_rows
    return res


def test_saas_tenants_requires_auth_401(client: TestClient) -> None:
    response = client.get("/api/saas/tenants")
    assert response.status_code == 401


def test_saas_tenants_forbidden_for_non_admin_403(client: TestClient) -> None:
    async def mock_require_saas_admin():
        raise HTTPException(status_code=403, detail="SaaS admin access required")

    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    try:
        response = client.get("/api/saas/tenants")
    finally:
        app.dependency_overrides.pop(require_saas_admin, None)
    assert response.status_code == 403


def test_saas_tenants_returns_200_for_admin(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = SimpleNamespace(
        id=tenant_id,
        name="Acme",
        created_at=datetime.now(timezone.utc),
        digest_enabled=True,
        slack_webhook_url="https://hooks.slack.com/redacted",
    )

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar=1),
            _result(scalars_all=[tenant]),
            _result(scalar=2),   # users_count
            _result(scalar=1),   # aws_accounts_count
            _result(scalar=3),   # open_findings_count
            _result(scalar=1),   # open_actions_count
            _result(scalar=datetime.now(timezone.utc)),  # latest_finding
            _result(scalar=None),  # latest_remediation
            _result(scalar=None),  # latest_export
            _result(scalar=None),  # latest_baseline
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    try:
        response = client.get("/api/saas/tenants")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert "slack_webhook_url" not in str(payload)
    assert payload["items"][0]["tenant_name"] == "Acme"


def test_saas_accounts_redacts_arns_and_external_id(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(
        id=uuid.uuid4(),
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        role_write_arn="arn:aws:iam::123456789012:role/WriteRole",
        external_id="secret-ext-id",
        regions=["us-east-1"],
        status="validated",
        last_validated_at=None,
        created_at=datetime.now(timezone.utc),
    )
    tenant = SimpleNamespace(id=tenant_id)

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=tenant),
            _result(scalars_all=[account]),
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    try:
        response = client.get(f"/api/saas/tenants/{tenant_id}/aws-accounts")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "role_read_arn" not in body[0]
    assert "role_write_arn" not in body[0]
    assert "external_id" not in body[0]


def test_saas_findings_redacts_raw_json(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    tenant = SimpleNamespace(id=tenant_id)
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-1",
        account_id="123456789012",
        region="us-east-1",
        source="security_hub",
        severity_label="HIGH",
        status="NEW",
        title="Issue",
        description="desc",
        resource_id="res",
        resource_type="AWS::S3::Bucket",
        control_id="S3.1",
        standard_name="CIS",
        first_observed_at=None,
        last_observed_at=None,
        sh_updated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        raw_json={"secret": True},
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=tenant),
            _result(scalar=1),
            _result(scalars_all=[finding]),
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    try:
        response = client.get(f"/api/saas/tenants/{tenant_id}/findings")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert "raw_json" not in body["items"][0]


def test_support_file_download_is_tenant_scoped(client: TestClient) -> None:
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(scalar_one_or_none=None))

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user():
        return SimpleNamespace(id=uuid.uuid4(), tenant_id=uuid.uuid4(), email="tenant@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        response = client.get(f"/api/support-files/{uuid.uuid4()}/download")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 404
