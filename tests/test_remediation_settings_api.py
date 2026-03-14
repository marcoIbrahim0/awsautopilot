from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.enums import UserRole


def _mock_user(tenant_id: str, role: str = "member") -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = uuid.UUID(tenant_id)
    user.email = "user@example.com"
    user.name = "Test User"
    user.role = UserRole.admin if role == "admin" else UserRole.member
    return user


def _mock_tenant(tenant_id: str, remediation_settings: dict | None = None) -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.UUID(tenant_id)
    tenant.name = "Test Tenant"
    tenant.remediation_settings = remediation_settings
    tenant.slack_webhook_url = "https://hooks.slack.com/services/tenant-secret"
    tenant.governance_webhook_url = "https://notify.example.com/tenant-secret"
    return tenant


def _override_dependencies(user: MagicMock, session: MagicMock) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_get_remediation_settings_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/users/me/remediation-settings")
    assert response.status_code == 401


def test_get_remediation_settings_returns_normalized_defaults() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(tenant_id, remediation_settings=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.get("/api/users/me/remediation-settings")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "sg_access_path_preference": None,
        "approved_admin_cidrs": [],
        "approved_bastion_security_group_ids": [],
        "cloudtrail": {"default_bucket_name": None, "default_kms_key_arn": None},
        "config": {
            "delivery_mode": None,
            "default_bucket_name": None,
            "default_kms_key_arn": None,
        },
        "s3_access_logs": {"default_target_bucket_name": None},
        "s3_encryption": {"mode": None, "kms_key_arn": None},
    }


def test_patch_remediation_settings_requires_admin() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="member")

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user
    try:
        client = TestClient(app)
        response = client.patch("/api/users/me/remediation-settings", json={"sg_access_path_preference": "ssm_only"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403
    assert "admin" in (response.json().get("detail") or "").lower()


def test_patch_remediation_settings_writes_and_get_returns_values() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, remediation_settings=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        payload = {
            "sg_access_path_preference": " restrict_to_approved_admin_cidr ",
            "approved_admin_cidrs": ["10.0.0.9/24", "192.168.1.10/32"],
            "approved_bastion_security_group_ids": [" sg-123 ", "bastion-group"],
            "cloudtrail": {
                "default_bucket_name": " trail-logs ",
                "default_kms_key_arn": " arn:aws:kms:us-east-1:123:key/abc ",
            },
            "config": {
                "delivery_mode": " account_local_delivery ",
                "default_bucket_name": " config-bucket ",
                "default_kms_key_arn": " arn:aws:kms:us-east-1:123:key/config ",
            },
            "s3_access_logs": {"default_target_bucket_name": " access-logs "},
            "s3_encryption": {
                "mode": " customer_managed ",
                "kms_key_arn": " arn:aws:kms:us-east-1:123:key/s3 ",
            },
        }
        patch_response = client.patch("/api/users/me/remediation-settings", json=payload)
        get_response = client.get("/api/users/me/remediation-settings")
    finally:
        _clear_overrides()

    expected = {
        "sg_access_path_preference": "restrict_to_approved_admin_cidr",
        "approved_admin_cidrs": ["10.0.0.0/24", "192.168.1.10/32"],
        "approved_bastion_security_group_ids": ["sg-123", "bastion-group"],
        "cloudtrail": {
            "default_bucket_name": "trail-logs",
            "default_kms_key_arn": "arn:aws:kms:us-east-1:123:key/abc",
        },
        "config": {
            "delivery_mode": "account_local_delivery",
            "default_bucket_name": "config-bucket",
            "default_kms_key_arn": "arn:aws:kms:us-east-1:123:key/config",
        },
        "s3_access_logs": {"default_target_bucket_name": "access-logs"},
        "s3_encryption": {
            "mode": "customer_managed",
            "kms_key_arn": "arn:aws:kms:us-east-1:123:key/s3",
        },
    }

    assert patch_response.status_code == 200
    assert tenant.remediation_settings == expected
    assert patch_response.json() == expected
    assert get_response.status_code == 200
    assert get_response.json() == expected


def test_patch_remediation_settings_omitted_fields_remain_unchanged() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(
        tenant_id,
        remediation_settings={
            "sg_access_path_preference": "close_public",
            "approved_admin_cidrs": ["10.0.0.0/24"],
            "approved_bastion_security_group_ids": ["sg-keep"],
            "cloudtrail": {
                "default_bucket_name": "trail-bucket",
                "default_kms_key_arn": "arn:aws:kms:trail",
            },
            "config": {
                "delivery_mode": "account_local_delivery",
                "default_bucket_name": "config-bucket",
                "default_kms_key_arn": "arn:aws:kms:config",
            },
            "s3_access_logs": {"default_target_bucket_name": "logs-bucket"},
            "s3_encryption": {
                "mode": "customer_managed",
                "kms_key_arn": "arn:aws:kms:s3",
            },
        },
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/users/me/remediation-settings",
            json={"config": {"delivery_mode": "centralized_delivery"}},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["delivery_mode"] == "centralized_delivery"
    assert data["config"]["default_bucket_name"] == "config-bucket"
    assert data["sg_access_path_preference"] == "close_public"
    assert data["approved_admin_cidrs"] == ["10.0.0.0/24"]
    assert data["cloudtrail"]["default_bucket_name"] == "trail-bucket"


def test_patch_remediation_settings_explicit_null_clears_scalar_and_object_branch() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(
        tenant_id,
        remediation_settings={
            "sg_access_path_preference": "bastion_sg_reference",
            "cloudtrail": {
                "default_bucket_name": "trail-bucket",
                "default_kms_key_arn": "arn:aws:kms:trail",
            },
        },
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/users/me/remediation-settings",
            json={"sg_access_path_preference": None, "cloudtrail": None},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["sg_access_path_preference"] is None
    assert response.json()["cloudtrail"] == {
        "default_bucket_name": None,
        "default_kms_key_arn": None,
    }


def test_patch_remediation_settings_rejects_unknown_keys() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, remediation_settings=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/users/me/remediation-settings",
            json={"cloudtrail": {"unknown_field": "value"}},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 400
    assert "unknown remediation settings key" in (response.json().get("detail") or "").lower()
    assert session.commit.await_count == 0


def test_patch_remediation_settings_rejects_invalid_cidr() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id, role="admin")
    tenant = _mock_tenant(tenant_id, remediation_settings=None)

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.patch(
            "/api/users/me/remediation-settings",
            json={"approved_admin_cidrs": ["not-a-cidr"]},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 400
    assert "cidr" in (response.json().get("detail") or "").lower()
    assert session.commit.await_count == 0


def test_get_remediation_settings_does_not_expose_secret_fields() -> None:
    tenant_id = "123e4567-e89b-12d3-a456-426614174000"
    user = _mock_user(tenant_id)
    tenant = _mock_tenant(
        tenant_id,
        remediation_settings={
            "approved_admin_cidrs": ["10.0.0.0/24"],
            "cloudtrail": {
                "default_bucket_name": "trail-bucket",
                "default_kms_key_arn": "arn:aws:kms:trail",
                "webhook_url": "secret",
            },
            "slack_webhook_url": "https://hooks.slack.com/services/embedded-secret",
            "governance_webhook_url": "https://notify.example.com/embedded-secret",
            "tenant_secret": "super-secret",
        },
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = tenant
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    _override_dependencies(user, session)
    try:
        client = TestClient(app)
        response = client.get("/api/users/me/remediation-settings")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    data = response.json()
    assert data["approved_admin_cidrs"] == ["10.0.0.0/24"]
    assert data["cloudtrail"] == {
        "default_bucket_name": "trail-bucket",
        "default_kms_key_arn": "arn:aws:kms:trail",
    }
    assert "slack_webhook_url" not in data
    assert "governance_webhook_url" not in data
    assert "tenant_secret" not in data
    assert "secret" not in json.dumps(data)
