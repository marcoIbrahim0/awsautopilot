from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.action_group_run import ActionGroupRun
from backend.models.enums import ActionGroupRunStatus, RemediationRunStatus
from backend.models.remediation_run import RemediationRun


@pytest.fixture(autouse=True)
def stub_grouped_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
        lambda *_, **__: {"checks": [], "warnings": [], "recommendation": "ok"},
    )


def _mock_scalar_result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars_result(values: list[object]) -> MagicMock:
    scalars = MagicMock()
    scalars.all.return_value = values
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "user@example.com"
    return user


def _make_group(tenant_id: uuid.UUID, *, action_type: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        group_key=f"{tenant_id}|{action_type}|123456789012|eu-north-1",
        action_type=action_type,
        account_id="123456789012",
        region="eu-north-1",
    )


def _make_action(
    *,
    action_type: str,
    priority: int,
    minutes_ago: int,
) -> SimpleNamespace:
    action_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    bucket_name = f"bucket-{str(action_id)[:8]}"
    return SimpleNamespace(
        id=action_id,
        action_type=action_type,
        account_id="123456789012",
        region="eu-north-1",
        status="open",
        priority=priority,
        updated_at=now - timedelta(minutes=minutes_ago),
        created_at=now - timedelta(minutes=minutes_ago + 1),
        target_id=f"arn:aws:s3:::{bucket_name}",
        resource_id=f"arn:aws:s3:::{bucket_name}",
    )


def _mock_group_session(
    *,
    group: SimpleNamespace,
    actions: list[SimpleNamespace],
    account: object | None = None,
) -> tuple[MagicMock, list[object]]:
    added: list[object] = []
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(group),
            _mock_scalars_result(actions),
            _mock_scalar_result(account),
        ]
    )
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    async def flush_side_effect() -> None:
        for obj in added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=flush_side_effect)
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    return session, added


def _install_action_group_dependencies(session: MagicMock, user: MagicMock) -> None:
    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user


def _clear_action_group_dependencies() -> None:
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_create_action_group_bundle_run_preserves_reporting_and_repo_target(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="s3_bucket_block_public_access")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    session, added = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-1"}
    callback_url = "https://api.example.com/api/internal/group-runs/report"
    token_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.routers.action_groups.issue_group_run_reporting_token",
                return_value=("signed-token", "token-jti", token_expiry),
            ):
                try:
                    response = client.post(
                        f"/api/action-groups/{group.id}/bundle-run",
                        json={
                            "strategy_id": "s3_migrate_cloudfront_oac_private",
                            "repo_target": {
                                "provider": "gitlab",
                                "repository": "org/repo",
                                "base_branch": "main",
                                "head_branch": "codex/w3",
                            },
                        },
                    )
                finally:
                    _clear_action_group_dependencies()

    assert response.status_code == 201
    payload = response.json()
    assert len(added) == 2

    group_run = added[0]
    remediation_run = added[1]
    assert isinstance(group_run, ActionGroupRun)
    assert isinstance(remediation_run, RemediationRun)

    assert payload["group_run_id"] == str(group_run.id)
    assert payload["remediation_run_id"] == str(remediation_run.id)
    assert payload["reporting_token"] == "signed-token"
    assert payload["reporting_callback_url"] == callback_url
    assert payload["status"] == ActionGroupRunStatus.queued.value

    assert group_run.mode == "download_bundle"
    assert group_run.status == ActionGroupRunStatus.queued
    assert group_run.reporting_source == "system"
    assert group_run.report_token_jti == "token-jti"
    assert group_run.remediation_run_id == remediation_run.id

    assert remediation_run.status == RemediationRunStatus.pending
    assert remediation_run.action_id == action1.id
    assert remediation_run.approved_by_user_id == user.id

    artifacts = remediation_run.artifacts
    assert artifacts["selected_strategy"] == "s3_migrate_cloudfront_oac_private"
    assert artifacts["repo_target"] == {
        "provider": "gitlab",
        "repository": "org/repo",
        "base_branch": "main",
        "head_branch": "codex/w3",
    }

    group_bundle = artifacts["group_bundle"]
    assert group_bundle["group_id"] == str(group.id)
    assert group_bundle["group_key"] == group.group_key
    assert group_bundle["group_run_id"] == str(group_run.id)
    assert group_bundle["reporting"] == {
        "callback_url": callback_url,
        "token": "signed-token",
        "reporting_source": "bundle_callback",
    }
    assert group_bundle["action_ids"] == [str(action1.id), str(action2.id)]

    resolutions = group_bundle["action_resolutions"]
    assert [entry["action_id"] for entry in resolutions] == [str(action1.id), str(action2.id)]
    assert {entry["strategy_id"] for entry in resolutions} == {"s3_migrate_cloudfront_oac_private"}
    assert {entry["profile_id"] for entry in resolutions} == {"s3_migrate_cloudfront_oac_private"}

    queue_payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert queue_payload["schema_version"] == 1
    assert queue_payload["run_id"] == str(remediation_run.id)
    assert queue_payload["action_id"] == str(action1.id)
    assert queue_payload["strategy_id"] == "s3_migrate_cloudfront_oac_private"
    assert queue_payload["group_action_ids"] == [str(action1.id), str(action2.id)]
    assert queue_payload["repo_target"] == artifacts["repo_target"]
    assert "action_overrides" not in queue_payload
    assert "action_resolutions" not in queue_payload


def test_create_action_group_bundle_run_accepts_action_overrides(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="aws_config_enabled")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    session, added = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-override"}
    token_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.routers.action_groups.issue_group_run_reporting_token",
                return_value=("signed-token", "token-jti", token_expiry),
            ):
                try:
                    response = client.post(
                        f"/api/action-groups/{group.id}/bundle-run",
                        json={
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
                    _clear_action_group_dependencies()

    assert response.status_code == 201
    remediation_run = added[1]
    resolutions = {
        entry["action_id"]: entry
        for entry in remediation_run.artifacts["group_bundle"]["action_resolutions"]
    }
    assert resolutions[str(action1.id)]["strategy_id"] == "config_enable_account_local_delivery"
    assert resolutions[str(action1.id)]["profile_id"] == "config_enable_account_local_delivery"
    assert resolutions[str(action1.id)]["strategy_inputs"] == {}
    assert resolutions[str(action2.id)]["strategy_id"] == "config_enable_centralized_delivery"
    assert resolutions[str(action2.id)]["profile_id"] == "config_enable_centralized_delivery"
    assert resolutions[str(action2.id)]["strategy_inputs"] == {
        "delivery_bucket": "central-config-bucket"
    }


@pytest.mark.parametrize(
    ("action_overrides", "expected_error"),
    [
        (
            [
                {"action_id": "same-action", "strategy_id": "config_enable_account_local_delivery"},
                {"action_id": "same-action", "strategy_id": "config_enable_account_local_delivery"},
            ],
            "Duplicate action_overrides entry",
        ),
        (
            [{"action_id": "outside-group", "strategy_id": "config_enable_account_local_delivery"}],
            "Invalid action_overrides[].action_id",
        ),
        (
            [{"action_id": "same-action", "strategy_id": "s3_migrate_cloudfront_oac_private"}],
            "Invalid strategy selection",
        ),
        (
            [
                {
                    "action_id": "same-action",
                    "strategy_id": "config_enable_account_local_delivery",
                    "profile_id": "not-a-profile",
                }
            ],
            "Invalid profile_id",
        ),
    ],
)
def test_create_action_group_bundle_run_invalid_overrides_rejected(
    client: TestClient,
    action_overrides: list[dict[str, str]],
    expected_error: str,
) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="aws_config_enabled")
    action = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    session, _ = _mock_group_session(group=group, actions=[action])
    _install_action_group_dependencies(session, user)

    normalized_overrides = []
    for item in action_overrides:
        normalized = dict(item)
        if normalized["action_id"] == "same-action":
            normalized["action_id"] = str(action.id)
        if normalized["action_id"] == "outside-group":
            normalized["action_id"] = str(uuid.uuid4())
        normalized_overrides.append(normalized)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client") as mock_boto_client:
            try:
                response = client.post(
                    f"/api/action-groups/{group.id}/bundle-run",
                    json={
                        "strategy_id": "config_enable_account_local_delivery",
                        "action_overrides": normalized_overrides,
                    },
                )
            finally:
                _clear_action_group_dependencies()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == expected_error
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_action_group_bundle_run_enqueue_failure_marks_rows_failed(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="s3_bucket_block_public_access")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    session, added = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    mock_sqs = MagicMock()
    mock_sqs.send_message.side_effect = RuntimeError("queue down")
    token_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client", return_value=mock_sqs):
            with patch(
                "backend.routers.action_groups.issue_group_run_reporting_token",
                return_value=("signed-token", "token-jti", token_expiry),
            ):
                try:
                    response = client.post(
                        f"/api/action-groups/{group.id}/bundle-run",
                        json={"strategy_id": "s3_migrate_cloudfront_oac_private"},
                    )
                finally:
                    _clear_action_group_dependencies()

    assert response.status_code == 503
    assert response.json()["detail"] == "Could not enqueue group bundle run job."
    assert len(added) == 2

    group_run = added[0]
    remediation_run = added[1]
    assert group_run.status == ActionGroupRunStatus.failed
    assert group_run.finished_at is not None
    assert remediation_run.status == RemediationRunStatus.failed
    assert remediation_run.outcome == "Queue enqueue failed for bundle generation."
    assert group_run.remediation_run_id == remediation_run.id
    assert session.commit.await_count == 2
