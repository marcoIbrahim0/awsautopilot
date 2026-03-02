from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch

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


def test_control_plane_reconcile_recently_touched_enqueues_and_logs(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    session = MagicMock()
    session.execute = AsyncMock(return_value=_result(scalar_one_or_none=SimpleNamespace(id=tenant_id)))
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    admin_user = SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    async def mock_require_saas_admin():
        return admin_user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    with patch("backend.routers.saas_admin.settings") as mock_settings:
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/inventory"
        mock_settings.CONTROL_PLANE_RECENT_TOUCH_LOOKBACK_MINUTES = 60
        mock_settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD = 500
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]
        with patch("backend.routers.saas_admin.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
            mock_boto3.client.return_value = mock_sqs
            try:
                response = client.post(
                    "/api/saas/control-plane/reconcile/recently-touched",
                    json={
                        "tenant_id": str(tenant_id),
                        "lookback_minutes": 30,
                        "services": ["ec2"],
                        "max_resources": 200,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["enqueued"] == 1
    assert body["status"] == "ok"
    assert len(body["job_ids"]) == 1


def test_control_plane_reconcile_jobs_lists_recent_entries(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        job_type="reconcile_inventory_global",
        status="enqueued",
        payload_summary={"enqueued": 4},
        submitted_at=datetime.now(timezone.utc),
        submitted_by_email="admin@example.com",
        error_message=None,
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=SimpleNamespace(id=tenant_id)),
            _result(scalar=1),
            _result(scalars_all=[row]),
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    try:
        response = client.get(f"/api/saas/control-plane/reconcile-jobs?tenant_id={tenant_id}&limit=10")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["job_type"] == "reconcile_inventory_global"
    assert body["items"][0]["status"] == "enqueued"


def test_control_plane_reconcile_global_enqueues_shards(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id="123456789012",
        regions=["eu-north-1", "us-east-1"],
        status="validated",
    )
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=SimpleNamespace(id=tenant_id)),
            _result(scalars_all=[account]),
        ]
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    with patch("backend.routers.saas_admin.settings") as mock_settings:
        mock_settings.SQS_INVENTORY_RECONCILE_QUEUE_URL = "https://sqs.eu-north-1.amazonaws.com/123/inventory"
        mock_settings.AWS_REGION = "eu-north-1"
        mock_settings.CONTROL_PLANE_INVENTORY_MAX_RESOURCES_PER_SHARD = 500
        mock_settings.control_plane_inventory_services_list = ["ec2", "s3"]
        with patch("backend.routers.saas_admin.boto3") as mock_boto3:
            mock_sqs = MagicMock()
            mock_boto3.client.return_value = mock_sqs
            try:
                response = client.post(
                    "/api/saas/control-plane/reconcile/global",
                    json={"tenant_id": str(tenant_id), "services": ["ec2", "s3"]},
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["enqueued"] == 4
    assert mock_sqs.send_message.call_count == 4


def test_control_plane_promotion_guardrail_health_requires_auth_401(client: TestClient) -> None:
    response = client.get("/api/saas/control-plane/promotion-guardrail-health")
    assert response.status_code == 401


def test_control_plane_promotion_guardrail_health_returns_shape_and_metrics(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    candidate_rows = [
        (tenant_id, "EC2.53", "RESOLVED", 99, now, "RESOLVED"),      # success
        (tenant_id, "EC2.53", "OPEN", 99, now, "RESOLVED"),          # mismatch
        (tenant_id, "EC2.53", "SOFT_RESOLVED", 99, now, "RESOLVED"), # blocked: soft-resolved
        (tenant_id, "S3.1", "OPEN", 99, now, "OPEN"),                # blocked: not high-confidence
        (tenant_id, "EC2.53", "OPEN", 80, now, "OPEN"),              # blocked: low confidence
    ]

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(all_rows=candidate_rows),
            _result(scalar=10),  # total shadow rows
            _result(scalar=2),   # stale shadow rows
            _result(scalar=now),  # latest evaluated
            _result(scalar=now),  # oldest evaluated
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    with patch("backend.routers.saas_admin.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_SOURCE = "event_monitor_shadow"
        mock_settings.CONTROL_PLANE_SHADOW_MODE = False
        mock_settings.CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED = True
        mock_settings.control_plane_high_confidence_controls_set = {"EC2.53"}
        mock_settings.control_plane_promotion_min_confidence = 95
        mock_settings.CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED = False
        mock_settings.control_plane_promotion_pilot_tenants_set = set()
        mock_settings.CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES = 30
        try:
            response = client.get("/api/saas/control-plane/promotion-guardrail-health?hours=24")
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "generated_at",
        "scope",
        "tenant_id",
        "window_hours",
        "guardrails",
        "promotion",
        "mismatch",
        "soft_resolved",
        "shadow_freshness",
    }
    assert body["scope"] == "global"
    assert body["tenant_id"] is None
    assert body["window_hours"] == 24
    assert body["guardrails"]["high_confidence_controls_count"] == 1

    assert body["promotion"]["attempts"] == 5
    assert body["promotion"]["successes"] == 1
    assert body["promotion"]["blocked"] == 3
    assert body["promotion"]["success_rate"] == 0.2
    assert body["promotion"]["blocked_rate"] == 0.6
    assert body["promotion"]["blocked_by_reason"]["soft_resolved_not_allowed"] == 1
    assert body["promotion"]["blocked_by_reason"]["control_not_high_confidence"] == 1
    assert body["promotion"]["blocked_by_reason"]["confidence_below_threshold"] == 1

    assert body["mismatch"]["comparable_rows"] == 4
    assert body["mismatch"]["mismatches"] == 1
    assert body["mismatch"]["mismatch_rate"] == 0.25

    assert body["soft_resolved"]["promoted_controls_rows"] == 4
    assert body["soft_resolved"]["soft_resolved_rows"] == 1
    assert body["soft_resolved"]["soft_resolved_rate"] == 0.25

    assert body["shadow_freshness"]["stale_threshold_minutes"] == 30
    assert body["shadow_freshness"]["total_rows"] == 10
    assert body["shadow_freshness"]["stale_rows"] == 2
    assert body["shadow_freshness"]["stale_rate"] == 0.2
    assert body["shadow_freshness"]["latest_evaluated_at"] is not None
    assert body["shadow_freshness"]["oldest_evaluated_at"] is not None


def test_control_plane_promotion_guardrail_health_supports_tenant_scope(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(scalar_one_or_none=SimpleNamespace(id=tenant_id)),  # tenant exists
            _result(all_rows=[]),  # candidate rows
            _result(scalar=0),  # total shadow rows
            _result(scalar=0),  # stale rows
            _result(scalar=now),  # latest evaluated
            _result(scalar=now),  # oldest evaluated
        ]
    )

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_require_saas_admin():
        return SimpleNamespace(id=uuid.uuid4(), email="admin@example.com")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[require_saas_admin] = mock_require_saas_admin
    with patch("backend.routers.saas_admin.settings") as mock_settings:
        mock_settings.CONTROL_PLANE_SOURCE = "event_monitor_shadow"
        mock_settings.CONTROL_PLANE_SHADOW_MODE = False
        mock_settings.CONTROL_PLANE_AUTHORITATIVE_PROMOTION_ENABLED = True
        mock_settings.control_plane_high_confidence_controls_set = {"EC2.53"}
        mock_settings.control_plane_promotion_min_confidence = 95
        mock_settings.CONTROL_PLANE_PROMOTION_ALLOW_SOFT_RESOLVED = False
        mock_settings.control_plane_promotion_pilot_tenants_set = set()
        mock_settings.CONTROL_PLANE_PREREQ_MAX_STALENESS_MINUTES = 30
        try:
            response = client.get(
                f"/api/saas/control-plane/promotion-guardrail-health?tenant_id={tenant_id}"
            )
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(require_saas_admin, None)

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "tenant"
    assert body["tenant_id"] == str(tenant_id)
