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
from backend.services.bundle_reporting_tokens import BundleReportingTokenSecretNotConfiguredError
from backend.services.grouped_bundle_conflicts import GroupedBundleRunRecord
from backend.services.remediation_risk import evaluate_strategy_impact as real_evaluate_strategy_impact
from backend.services.root_key_resolution_adapter import ROOT_KEY_EXECUTION_AUTHORITY_PATH
from backend.utils.sqs import REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2


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
def stub_action_group_tenant_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _stub_get_tenant(tenant_id: uuid.UUID, db) -> MagicMock:
        tenant = MagicMock()
        tenant.id = tenant_id
        tenant.remediation_settings = {}
        return tenant

    monkeypatch.setattr("backend.routers.action_groups.get_tenant", _stub_get_tenant)


@pytest.fixture(autouse=True)
def stub_reporting_token_issue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.routers.action_groups.issue_group_run_reporting_token",
        lambda **_: ("signed-token", "token-jti", datetime.now(timezone.utc) + timedelta(minutes=5)),
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
    existing_runs: list[GroupedBundleRunRecord] | None = None,
) -> tuple[MagicMock, list[object]]:
    added: list[object] = []
    session = MagicMock()
    grouped_run_rows = []
    for record in existing_runs or []:
        remediation_run = SimpleNamespace(
            id=uuid.UUID(record.run_id),
            action_id=uuid.UUID(record.action_id),
            mode=record.mode,
            status=record.status,
            created_at=record.created_at,
            artifacts=record.artifacts,
        )
        group_run = SimpleNamespace(id=uuid.UUID(record.group_run_id or str(uuid.uuid4())))
        grouped_run_rows.append((group_run, remediation_run))
    grouped_run_result = MagicMock()
    grouped_run_result.all.return_value = grouped_run_rows
    session.execute = AsyncMock(
        side_effect=[
            _mock_scalar_result(group),
            _mock_scalars_result(actions),
            _mock_scalar_result(account),
            grouped_run_result,
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
    assert group_bundle["reporting"]["token"] == payload["reporting_token"]
    assert group_bundle["reporting"]["callback_url"] == payload["reporting_callback_url"]
    assert group_bundle["action_ids"] == [str(action1.id), str(action2.id)]

    resolutions = group_bundle["action_resolutions"]
    assert [entry["action_id"] for entry in resolutions] == [str(action1.id), str(action2.id)]
    assert {entry["strategy_id"] for entry in resolutions} == {"s3_migrate_cloudfront_oac_private"}
    assert {entry["profile_id"] for entry in resolutions} == {
        "s3_migrate_cloudfront_oac_private_manual_preservation"
    }

    queue_payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    assert queue_payload["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert queue_payload["run_id"] == str(remediation_run.id)
    assert queue_payload["action_id"] == str(action1.id)
    assert queue_payload["strategy_id"] == "s3_migrate_cloudfront_oac_private"
    assert queue_payload["group_action_ids"] == [str(action1.id), str(action2.id)]
    assert queue_payload["repo_target"] == artifacts["repo_target"]
    assert "action_overrides" not in queue_payload
    assert queue_payload["action_resolutions"] == resolutions


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


def test_create_action_group_bundle_run_requires_dedicated_reporting_secret(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="aws_config_enabled")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    session, _ = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch(
            "backend.routers.action_groups.issue_group_run_reporting_token",
            side_effect=BundleReportingTokenSecretNotConfiguredError(
                "BUNDLE_REPORTING_TOKEN_SECRET is not configured. Bundle reporting tokens require a dedicated signing secret."
            ),
        ):
            try:
                response = client.post(
                    f"/api/action-groups/{group.id}/bundle-run",
                    json={"strategy_id": "config_enable_account_local_delivery"},
                )
            finally:
                _clear_action_group_dependencies()

    assert response.status_code == 503
    assert "BUNDLE_REPORTING_TOKEN_SECRET" in response.json()["detail"]
    assert session.commit.await_count == 0


def test_create_action_group_bundle_run_preserves_ec2_53_executable_family_tier(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="sg_restrict_public_ports")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action1.target_id = "123456789012|eu-north-1|sg-0123456789abcdef0|EC2.53"
    action1.resource_id = "sg-0123456789abcdef0"
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    action2.target_id = "123456789012|eu-north-1|sg-0fedcba9876543210|EC2.53"
    action2.resource_id = "sg-0fedcba9876543210"
    session, added = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-ec2-53"}
    token_expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
        real_evaluate_strategy_impact,
    )

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
                            "strategy_id": "sg_restrict_public_ports_guided",
                            "risk_acknowledged": True,
                            "action_overrides": [
                                {
                                    "action_id": str(action1.id),
                                    "profile_id": "close_and_revoke",
                                },
                                {
                                    "action_id": str(action2.id),
                                    "profile_id": "ssm_only",
                                },
                            ],
                        },
                    )
                finally:
                    _clear_action_group_dependencies()

    assert response.status_code == 201
    remediation_run = added[1]
    resolutions = {
        entry["action_id"]: entry["resolution"]
        for entry in remediation_run.artifacts["group_bundle"]["action_resolutions"]
    }
    assert resolutions[str(action1.id)]["profile_id"] == "close_and_revoke"
    assert resolutions[str(action1.id)]["support_tier"] == "deterministic_bundle"
    assert resolutions[str(action2.id)]["profile_id"] == "ssm_only"
    assert resolutions[str(action2.id)]["support_tier"] == "manual_guidance_only"

    queue_payload = json.loads(mock_sqs.send_message.call_args.kwargs["MessageBody"])
    queue_resolutions = {
        entry["action_id"]: entry["resolution"]
        for entry in queue_payload["action_resolutions"]
    }
    assert queue_resolutions[str(action1.id)]["support_tier"] == "deterministic_bundle"
    assert queue_resolutions[str(action2.id)]["support_tier"] == "manual_guidance_only"


def test_create_action_group_bundle_run_inherits_top_level_inputs_into_same_strategy_profile_overrides(
    client: TestClient,
) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="s3_bucket_access_logging")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    session, added = _mock_group_session(group=group, actions=[action1, action2])
    _install_action_group_dependencies(session, user)

    mock_sqs = MagicMock()
    mock_sqs.send_message.return_value = {"MessageId": "msg-s3-9-override"}
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
                    _clear_action_group_dependencies()

    assert response.status_code == 201
    remediation_run = added[1]
    resolutions = remediation_run.artifacts["group_bundle"]["action_resolutions"]
    for entry in resolutions:
        assert entry["strategy_id"] == "s3_enable_access_logging_guided"
        assert entry["profile_id"] == "s3_enable_access_logging_review_destination_safety"
        assert entry["strategy_inputs"] == {"log_bucket_name": "dedicated-access-log-bucket"}


def test_create_action_group_bundle_run_missing_required_inherited_inputs_returns_400(
    client: TestClient,
) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="s3_bucket_access_logging")
    action = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    session, _ = _mock_group_session(group=group, actions=[action])
    _install_action_group_dependencies(session, user)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client") as mock_boto_client:
            try:
                response = client.post(
                    f"/api/action-groups/{group.id}/bundle-run",
                    json={
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
                _clear_action_group_dependencies()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "Invalid grouped remediation request"
    assert detail["reason"] == "invalid_strategy_inputs"
    assert "strategy_inputs.log_bucket_name is required" in detail["detail"]
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


def test_create_action_group_bundle_run_cloudtrail_unresolved_bucket_returns_400(
    client: TestClient,
) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="cloudtrail_enabled")
    action = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    session, _ = _mock_group_session(group=group, actions=[action])
    _install_action_group_dependencies(session, user)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client") as mock_boto_client:
            try:
                response = client.post(
                    f"/api/action-groups/{group.id}/bundle-run",
                    json={
                        "strategy_id": "cloudtrail_enable_guided",
                        "risk_acknowledged": True,
                    },
                )
            finally:
                _clear_action_group_dependencies()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "Invalid grouped remediation request"
    assert detail["reason"] == "invalid_strategy_inputs"
    assert "CloudTrail log bucket name is unresolved" in detail["detail"]
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0


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


def test_create_action_group_bundle_run_root_key_requires_dedicated_route(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="iam_root_access_key_absent")
    action = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    session, added = _mock_group_session(group=group, actions=[action])
    _install_action_group_dependencies(session, user)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client") as mock_boto_client:
            try:
                response = client.post(
                    f"/api/action-groups/{group.id}/bundle-run",
                    json={"strategy_id": "iam_root_key_disable"},
                )
            finally:
                _clear_action_group_dependencies()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["reason"] == "root_key_execution_authority"
    assert detail["execution_authority"] == ROOT_KEY_EXECUTION_AUTHORITY_PATH
    assert added == []
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


def test_create_action_group_bundle_run_rejects_identical_successful_bundle(client: TestClient) -> None:
    tenant_id = uuid.uuid4()
    user = _mock_user(tenant_id)
    group = _make_group(tenant_id, action_type="s3_bucket_block_public_access")
    action1 = _make_action(action_type=group.action_type, priority=100, minutes_ago=1)
    action2 = _make_action(action_type=group.action_type, priority=90, minutes_ago=2)
    successful_run = GroupedBundleRunRecord(
        run_id=str(uuid.uuid4()),
        action_id=str(action1.id),
        mode="pr_only",
        status="success",
        created_at=datetime.now(timezone.utc),
        artifacts={
            "selected_strategy": "s3_migrate_cloudfront_oac_private",
            "group_bundle": {
                "group_key": group.group_key,
                "action_ids": [str(action1.id), str(action2.id)],
                "action_resolutions": [
                    {
                        "action_id": str(action1.id),
                        "strategy_id": "s3_migrate_cloudfront_oac_private",
                        "profile_id": "s3_migrate_cloudfront_oac_private_manual_preservation",
                        "strategy_inputs": {},
                    },
                    {
                        "action_id": str(action2.id),
                        "strategy_id": "s3_migrate_cloudfront_oac_private",
                        "profile_id": "s3_migrate_cloudfront_oac_private_manual_preservation",
                        "strategy_inputs": {},
                    },
                ],
            },
        },
        group_run_id=str(uuid.uuid4()),
    )
    session, _ = _mock_group_session(group=group, actions=[action1, action2], existing_runs=[successful_run])
    _install_action_group_dependencies(session, user)

    with patch("backend.routers.action_groups.settings") as mock_settings:
        mock_settings.has_ingest_queue = True
        mock_settings.SQS_INGEST_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123/test"
        mock_settings.API_PUBLIC_URL = "https://api.example.com"
        with patch("backend.routers.action_groups.boto3.client") as mock_boto_client:
            with patch(
                "backend.routers.action_groups.issue_group_run_reporting_token",
                return_value=("signed-token", "token-jti", datetime.now(timezone.utc) + timedelta(minutes=5)),
            ):
                try:
                    response = client.post(
                        f"/api/action-groups/{group.id}/bundle-run",
                        json={"strategy_id": "s3_migrate_cloudfront_oac_private"},
                    )
                finally:
                    _clear_action_group_dependencies()

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "grouped_bundle_already_created_no_changes"
    assert detail["existing_run_id"] == successful_run.run_id
    assert session.add.call_count == 0
    assert session.commit.await_count == 0
    assert mock_boto_client.call_count == 0
