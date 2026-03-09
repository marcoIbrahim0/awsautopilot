"""Phase 3 P0.7 execution-guidance contract tests."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_optional_user
from backend.database import get_db
from backend.main import app
from backend.services.action_execution_guidance import build_action_execution_guidance
from backend.services.remediation_strategy import STRATEGY_REGISTRY


def _target_id_for_action_type(action_type: str) -> tuple[str, str | None, str | None]:
    if action_type == "sg_restrict_public_ports":
        return "123456789012|us-east-1|sg-0123456789abcdef0|EC2.53", "sg-0123456789abcdef0", "AwsEc2SecurityGroup"
    if action_type == "iam_root_access_key_absent":
        return "123456789012", "123456789012", "AwsAccount"
    if action_type.startswith("s3_") or action_type in {"cloudtrail_enabled"}:
        return "arn:aws:s3:::prod-app-bucket", "arn:aws:s3:::prod-app-bucket", "AwsS3Bucket"
    return "123456789012|us-east-1|account-scope", None, "AwsAccount"


def _make_action(action_type: str) -> SimpleNamespace:
    target_id, resource_id, resource_type = _target_id_for_action_type(action_type)
    observed_at = datetime(2026, 3, 9, 12, 0, tzinfo=timezone.utc)
    finding = SimpleNamespace(
        id=uuid.uuid4(),
        finding_id=f"{action_type}-finding",
        severity_label="HIGH",
        title=f"{action_type} finding",
        resource_id=resource_id,
        account_id="123456789012",
        region="us-east-1",
        updated_at=observed_at,
    )
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        action_type=action_type,
        target_id=target_id,
        account_id="123456789012",
        region=None if action_type == "iam_root_access_key_absent" else "us-east-1",
        score=88,
        score_components={"score": 88},
        priority=88,
        status="open",
        title=f"Remediate {action_type}",
        description=f"{action_type} needs remediation.",
        control_id="TEST.1",
        resource_id=resource_id,
        resource_type=resource_type,
        created_at=observed_at,
        updated_at=observed_at,
        action_finding_links=[SimpleNamespace(finding=finding)],
    )


def _make_account() -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id=uuid.uuid4(),
        account_id="123456789012",
        role_read_arn="arn:aws:iam::123456789012:role/ReadRole",
        role_write_arn="arn:aws:iam::123456789012:role/WriteRole",
        external_id="tenant-external-id",
    )


def _assert_guidance_complete(guidance: dict) -> None:
    assert guidance["blast_radius"]
    assert guidance["blast_radius_summary"]
    assert guidance["expected_outcome"]
    assert guidance["pre_checks"]
    assert guidance["post_checks"]
    assert guidance["rollback"]["summary"]
    assert guidance["rollback"]["command"]


@pytest.mark.parametrize("action_type", sorted(STRATEGY_REGISTRY))
def test_supported_action_types_return_complete_execution_guidance(action_type: str) -> None:
    action = _make_action(action_type)

    guidance = build_action_execution_guidance(action)

    assert guidance
    for item in guidance:
        _assert_guidance_complete(item)


def test_execution_guidance_differs_between_direct_fix_and_pr_modes() -> None:
    action = _make_action("s3_block_public_access")

    guidance = build_action_execution_guidance(action, account=_make_account())
    by_mode = {item["mode"]: item for item in guidance}

    assert set(by_mode) == {"direct_fix", "pr_only"}
    assert by_mode["direct_fix"]["expected_outcome"] != by_mode["pr_only"]["expected_outcome"]
    assert by_mode["direct_fix"]["rollback"]["summary"] != by_mode["pr_only"]["rollback"]["summary"]
    assert by_mode["direct_fix"]["pre_checks"][1]["code"] == "direct_fix_change_window"
    assert by_mode["pr_only"]["pre_checks"][1]["code"] == "pr_bundle_owner_confirmed"
    assert by_mode["direct_fix"]["post_checks"][0]["code"] == "direct_fix_run_success"
    assert by_mode["pr_only"]["post_checks"][0]["code"] == "pr_bundle_review_and_apply"


def test_get_action_contract_includes_execution_guidance(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    action = _make_action("s3_block_public_access")
    account = _make_account()
    account.tenant_id = tenant_id

    tenant_row = MagicMock()
    tenant_row.scalar_one_or_none.return_value = MagicMock()
    action_row = MagicMock()
    action_row.scalar_one_or_none.return_value = action
    exception_row = MagicMock()
    exception_row.scalars.return_value.all.return_value = []
    runs_row = MagicMock()
    runs_row.scalars.return_value.all.return_value = []
    account_row = MagicMock()
    account_row.scalar_one_or_none.return_value = account

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tenant_row
        if call_count == 2:
            return action_row
        if call_count == 3:
            return exception_row
        if call_count == 4:
            return runs_row
        return account_row

    db_session = MagicMock()
    db_session.execute = AsyncMock(side_effect=execute_side_effect)

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
    assert body["execution_guidance"]
    assert body["implementation_artifacts"] == []
    for item in body["execution_guidance"]:
        _assert_guidance_complete(item)
        assert item["mode"] in {"direct_fix", "pr_only"}
