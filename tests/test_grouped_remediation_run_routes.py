from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import get_current_user
from backend.database import get_db
from backend.main import app
from backend.models.action_group_run import ActionGroupRun
from backend.models.remediation_run import RemediationRun
from backend.utils.sqs import REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2


def _mock_user(tenant_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.tenant_id = tenant_id
    user.email = "user@example.com"
    return user


def _mock_tenant() -> MagicMock:
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    return tenant


def _mock_group_action(
    *,
    action_type: str,
    priority: int,
    bucket_name: str,
) -> MagicMock:
    action = MagicMock()
    action.id = uuid.uuid4()
    action.action_type = action_type
    action.account_id = "123456789012"
    action.region = "eu-north-1"
    action.status = "open"
    action.priority = priority
    action.created_at = datetime.now(timezone.utc)
    action.updated_at = datetime.now(timezone.utc)
    action.target_id = f"123456789012|eu-north-1|arn:aws:s3:::{bucket_name}|S3.9"
    action.resource_id = f"arn:aws:s3:::{bucket_name}"
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


def _mock_group_session(actions: list[MagicMock], *, account: MagicMock | None = None) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _mock_group_query_result(actions),
            _mock_group_account_result(account),
            _mock_group_query_result([]),
        ]
    )
    added: list[MagicMock] = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.commit = AsyncMock()
    session._added = added

    async def _flush() -> None:
        for obj in added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    session.flush = AsyncMock(side_effect=_flush)

    async def _refresh(run_obj: MagicMock) -> None:
        run_obj.created_at = datetime.now(timezone.utc)
        run_obj.updated_at = datetime.now(timezone.utc)

    session.refresh = AsyncMock(side_effect=_refresh)

    async def _run_sync(fn):
        group_id = uuid.uuid4()
        group_key = (
            f"{actions[0].action_type}|{actions[0].account_id}|"
            f"{actions[0].region or 'global'}|{actions[0].status}"
        )
        return group_id, group_key, [action.id for action in actions]

    session.run_sync = AsyncMock(side_effect=_run_sync)
    return session


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


@pytest.fixture(autouse=True)
def stub_remediation_run_tenant_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_get_tenant(tenant_id: uuid.UUID, db) -> MagicMock:
        tenant = MagicMock()
        tenant.id = tenant_id
        tenant.remediation_settings = {}
        return tenant

    monkeypatch.setattr("backend.routers.remediation_runs.get_tenant", _stub_get_tenant)


@pytest.fixture(autouse=True)
def stub_reporting_token_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.routers.remediation_runs.issue_group_run_reporting_token",
        lambda **_: ("signed-token", "token-jti", datetime.now(timezone.utc)),
    )


def test_group_pr_bundle_inherits_top_level_inputs_into_same_strategy_profile_overrides(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(
        action_type="s3_bucket_access_logging",
        priority=100,
        bucket_name="source-bucket-one",
    )
    action2 = _mock_group_action(
        action_type="s3_bucket_access_logging",
        priority=90,
        bucket_name="source-bucket-two",
    )
    session = _mock_group_session([action1, action2])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-s3-9-group"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                response = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "s3_bucket_access_logging",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "s3_enable_access_logging_guided",
                        "strategy_inputs": {"log_bucket_name": "dedicated-access-log-bucket"},
                        "action_overrides": [
                            {
                                "action_id": str(action1.id),
                                "profile_id": "s3_enable_access_logging_review_destination_safety",
                            },
                            {
                                "action_id": str(action2.id),
                                "profile_id": "s3_enable_access_logging_review_destination_safety",
                            },
                        ],
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201
    run = session._added[1]
    payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert payload["strategy_inputs"] == {"log_bucket_name": "dedicated-access-log-bucket"}
    for entry in run.artifacts["group_bundle"]["action_resolutions"]:
        assert entry["strategy_id"] == "s3_enable_access_logging_guided"
        assert entry["profile_id"] == "s3_enable_access_logging_review_destination_safety"
        assert entry["strategy_inputs"] == {"log_bucket_name": "dedicated-access-log-bucket"}


def test_group_pr_bundle_derives_s3_9_log_bucket_name_when_override_omits_inputs(client: TestClient) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action = _mock_group_action(
        action_type="s3_bucket_access_logging",
        priority=100,
        bucket_name="source-bucket-one",
    )
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
                response = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "s3_bucket_access_logging",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "s3_enable_access_logging_guided",
                        "action_overrides": [
                            {
                                "action_id": str(action.id),
                                "profile_id": "s3_enable_access_logging_review_destination_safety",
                            }
                        ],
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201
    run = session._added[1]
    resolution = run.artifacts["group_bundle"]["action_resolutions"][0]
    assert resolution["strategy_inputs"] == {"log_bucket_name": "source-bucket-one-access-logs"}
    assert resolution["resolution"]["support_tier"] == "review_required_bundle"


def test_group_pr_bundle_persists_group_run_and_reporting_metadata_immediately(
    client: TestClient,
) -> None:
    tenant = _mock_tenant()
    user = _mock_user(tenant.id)
    action1 = _mock_group_action(
        action_type="s3_bucket_access_logging",
        priority=100,
        bucket_name="source-bucket-one",
    )
    action2 = _mock_group_action(
        action_type="s3_bucket_access_logging",
        priority=90,
        bucket_name="source-bucket-two",
    )
    session = _mock_group_session([action1, action2])

    async def mock_get_db() -> AsyncGenerator[MagicMock, None]:
        yield session

    async def mock_get_current_user() -> MagicMock:
        return user

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-group-run"}

    with patch("backend.routers.remediation_runs.settings") as mock_settings:
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.remediation_runs.boto3.client", return_value=mock_sqs):
            try:
                response = client.post(
                    "/api/remediation-runs/group-pr-bundle",
                    json={
                        "action_type": "s3_bucket_access_logging",
                        "account_id": "123456789012",
                        "region": "eu-north-1",
                        "status": "open",
                        "strategy_id": "s3_enable_access_logging_guided",
                        "strategy_inputs": {"log_bucket_name": "dedicated-access-log-bucket"},
                    },
                )
            finally:
                app.dependency_overrides.pop(get_db, None)
                app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 201
    assert len(session._added) == 2
    group_run = session._added[0]
    remediation_run = session._added[1]
    assert isinstance(group_run, ActionGroupRun)
    assert isinstance(remediation_run, RemediationRun)
    assert group_run.remediation_run_id == remediation_run.id

    group_bundle = remediation_run.artifacts["group_bundle"]
    assert group_bundle["group_run_id"] == str(group_run.id)
    assert group_bundle["reporting"] == {
        "callback_url": "https://api.example.com/api/internal/group-runs/report",
        "token": "signed-token",
        "reporting_source": "bundle_callback",
    }
