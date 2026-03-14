"""Phase 3 P1.2 graph-backed action detail context tests."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.services.action_graph_context import (
    GRAPH_CONTEXT_MAX_INVENTORY_ASSETS,
    GRAPH_CONTEXT_MAX_RELATED_ACTIONS,
    GRAPH_CONTEXT_MAX_RELATED_FINDINGS,
    build_action_graph_context,
)
from backend.services.canonicalization import build_resource_key
from backend.services.finding_relationship_context import build_finding_relationship_context


def _graph_raw_json(
    *,
    account_id: str,
    region: str | None,
    resource_id: str,
    resource_type: str,
) -> dict:
    return {
        "relationship_context": build_finding_relationship_context(
            account_id=account_id,
            region=region,
            resource_id=resource_id,
            resource_type=resource_type,
        ),
        "principal": {"AWS": ["arn:aws:iam::123456789012:role/AppRole"]},
        "Resources": [
            {"Id": "arn:aws:iam::123456789012:role/AppRole", "Type": "AwsIamRole"},
            {"Id": resource_id, "Type": resource_type},
        ],
    }


def _finding(
    *,
    control_id: str,
    resource_id: str,
    resource_type: str,
    raw_json: dict,
    account_id: str = "123456789012",
    region: str = "us-east-1",
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 11, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_id=f"finding-{control_id}",
        control_id=control_id,
        severity_label="HIGH",
        severity_normalized=75,
        title=f"{control_id} finding",
        description=f"{control_id} needs remediation.",
        resource_id=resource_id,
        resource_type=resource_type,
        resource_key=build_resource_key(
            account_id=account_id,
            region=region,
            resource_id=resource_id,
            resource_type=resource_type,
        ),
        account_id=account_id,
        region=region,
        raw_json=raw_json,
        updated_at=observed_at,
        created_at=observed_at,
    )


def _action(
    finding: SimpleNamespace,
    *,
    action_type: str,
    account_id: str = "123456789012",
    region: str | None = "us-east-1",
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 11, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type=action_type,
        target_id=f"{account_id}|{region or 'global'}|{finding.resource_id}|{finding.control_id}",
        account_id=account_id,
        region=region,
        score=88,
        score_components={"score": 88},
        priority=88,
        status="open",
        title=f"Remediate {action_type}",
        description=f"{action_type} needs remediation.",
        control_id=finding.control_id,
        resource_id=finding.resource_id,
        resource_type=finding.resource_type,
        created_at=observed_at,
        updated_at=observed_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _inventory_asset(
    *,
    resource_id: str,
    resource_type: str,
    service: str,
    account_id: str = "123456789012",
    region: str = "us-east-1",
) -> SimpleNamespace:
    observed_at = datetime(2026, 3, 12, 11, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        tenant_id=uuid.uuid4(),
        account_id=account_id,
        region=region,
        service=service,
        resource_id=resource_id,
        resource_type=resource_type,
        last_seen_at=observed_at,
    )


def _rows_result(rows: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_build_action_graph_context_returns_graph_sections_for_graph_enabled_action() -> None:
    anchor_finding = _finding(
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        raw_json=_graph_raw_json(
            account_id="123456789012",
            region="us-east-1",
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        ),
    )
    anchor_action = _action(anchor_finding, action_type="s3_bucket_block_public_access")
    account_finding = _finding(
        control_id="IAM.4",
        resource_id="123456789012",
        resource_type="AwsAccount",
        raw_json={
            "relationship_context": build_finding_relationship_context(
                account_id="123456789012",
                region=None,
                resource_id="123456789012",
                resource_type="AwsAccount",
            )
        },
    )
    related_action = _action(account_finding, action_type="iam_root_access_key_absent", region=None)
    bucket_inventory = _inventory_asset(
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        service="s3",
    )
    account_inventory = _inventory_asset(
        resource_id="123456789012",
        resource_type="AwsAccount",
        service="iam",
    )

    db_session = MagicMock()
    db_session.execute = AsyncMock(
        side_effect=[
            _rows_result([anchor_finding, account_finding]),
            _rows_result([anchor_action, related_action]),
            _rows_result([bucket_inventory, account_inventory]),
        ]
    )

    payload = asyncio.run(
        build_action_graph_context(db_session, tenant_id=anchor_action.tenant_id, action=anchor_action)
    )

    assert payload["status"] == "available"
    assert payload["availability_reason"] is None
    assert payload["connected_assets"]
    assert any(item["relationship"] == "anchor" for item in payload["connected_assets"])
    assert payload["identity_path"]
    assert payload["identity_path"][0]["node_type"] == "principal"
    assert payload["blast_radius_neighborhood"]
    assert any(item["scope"] == "anchor" for item in payload["blast_radius_neighborhood"])


def test_build_action_graph_context_returns_explicit_fallback_when_graph_is_unavailable() -> None:
    anchor_finding = _finding(
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        raw_json={},
    )
    anchor_action = _action(anchor_finding, action_type="s3_bucket_block_public_access")

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=[_rows_result([]), _rows_result([]), _rows_result([])])

    payload = asyncio.run(
        build_action_graph_context(db_session, tenant_id=anchor_action.tenant_id, action=anchor_action)
    )

    assert payload["status"] == "available"
    assert payload["availability_reason"] is None
    assert payload["self_resolved"] is True
    assert any(item["relationship"] == "anchor" for item in payload["connected_assets"])


def test_build_action_graph_context_returns_explicit_fallback_when_action_cannot_self_resolve() -> None:
    anchor_finding = _finding(
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        raw_json={},
    )
    anchor_action = _action(anchor_finding, action_type="s3_bucket_block_public_access")
    anchor_action.account_id = None

    db_session = MagicMock()
    db_session.execute = AsyncMock()

    payload = asyncio.run(
        build_action_graph_context(db_session, tenant_id=anchor_action.tenant_id, action=anchor_action)
    )

    assert payload["status"] == "unavailable"
    assert payload["availability_reason"] == "relationship_context_unavailable"
    assert payload["connected_assets"] == []
    assert payload["identity_path"] == []
    assert payload["blast_radius_neighborhood"] == []
    db_session.execute.assert_not_called()


def test_graph_traversal_queries_use_conservative_limits() -> None:
    anchor_finding = _finding(
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        raw_json=_graph_raw_json(
            account_id="123456789012",
            region="us-east-1",
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        ),
    )
    anchor_action = _action(anchor_finding, action_type="s3_bucket_block_public_access")
    captured_statements: list[object] = []

    async def _execute(statement, *args, **kwargs):  # noqa: ANN001
        captured_statements.append(statement)
        return _rows_result([])

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=_execute)

    payload = asyncio.run(
        build_action_graph_context(db_session, tenant_id=anchor_action.tenant_id, action=anchor_action)
    )

    assert payload["status"] == "available"
    assert len(captured_statements) == 3
    assert int(captured_statements[0]._limit_clause.value) == GRAPH_CONTEXT_MAX_RELATED_FINDINGS + 1
    assert int(captured_statements[1]._limit_clause.value) == GRAPH_CONTEXT_MAX_RELATED_ACTIONS + 1
    assert int(captured_statements[2]._limit_clause.value) == GRAPH_CONTEXT_MAX_INVENTORY_ASSETS + 1


def test_get_action_contract_includes_graph_context_payload_shape(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    anchor_finding = _finding(
        control_id="S3.2",
        resource_id="arn:aws:s3:::prod-sensitive-bucket",
        resource_type="AwsS3Bucket",
        raw_json=_graph_raw_json(
            account_id="123456789012",
            region="us-east-1",
            resource_id="arn:aws:s3:::prod-sensitive-bucket",
            resource_type="AwsS3Bucket",
        ),
    )
    action = _action(anchor_finding, action_type="s3_bucket_block_public_access")
    action.tenant_id = tenant_id
    account = SimpleNamespace(
        tenant_id=tenant_id,
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        role_write_arn="arn:aws:iam::123456789012:role/WriteRole",
        external_id="tenant-external-id",
    )

    tenant_row = _scalar_result(MagicMock())
    action_row = _scalar_result(action)
    exception_row = MagicMock()
    exception_row.scalars.return_value.all.return_value = []
    runs_row = _rows_result([])
    graph_findings_row = _rows_result([anchor_finding])
    graph_actions_row = _rows_result([action])
    graph_inventory_row = _rows_result(
        [
            _inventory_asset(
                resource_id="arn:aws:s3:::prod-sensitive-bucket",
                resource_type="AwsS3Bucket",
                service="s3",
            )
        ]
    )
    account_row = _scalar_result(account)

    db_session = MagicMock()
    db_session.execute = AsyncMock(
        side_effect=[
            tenant_row,
            action_row,
            exception_row,
            runs_row,
            graph_findings_row,
            graph_actions_row,
            graph_inventory_row,
            account_row,
        ]
    )

    user = MagicMock()
    user.tenant_id = tenant_id

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield db_session

    async def mock_get_optional_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_optional_user] = mock_get_optional_user
    try:
        response = client.get(f"/api/actions/{action.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)

    assert response.status_code == 200
    body = response.json()
    graph = body["graph_context"]
    assert graph["status"] == "available"
    assert graph["availability_reason"] is None
    assert graph["self_resolved"] is False
    assert graph["limits"]["max_connected_assets"] == 6
    assert isinstance(graph["connected_assets"], list)
    assert isinstance(graph["identity_path"], list)
    assert isinstance(graph["blast_radius_neighborhood"], list)
    assert graph["connected_assets"][0]["relationship"] == "anchor"
    assert graph["identity_path"][0]["node_type"] == "principal"
    assert graph["blast_radius_neighborhood"][0]["scope"] == "anchor"
