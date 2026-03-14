from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest

from backend.services.grouped_remediation_runs import (
    GroupedActionOverride,
    GroupedActionScope,
    GroupedRemediationRunValidationError,
    NormalizedGroupedRunRequest,
    build_grouped_run_persistence_plan,
    normalize_grouped_request_from_action_group,
    normalize_grouped_request_from_remediation_runs,
)
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
)


@dataclass(slots=True)
class DummyAction:
    id: uuid.UUID
    action_type: str
    account_id: str
    region: str | None
    status: str
    priority: int
    updated_at: datetime
    created_at: datetime
    target_id: str
    resource_id: str


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


def test_normalize_grouped_request_across_both_route_styles() -> None:
    raw_request = {
        "strategy_id": "  s3_migrate_cloudfront_oac_private  ",
        "strategy_inputs": {"preserve_existing_policy": True},
        "risk_acknowledged": True,
        "pr_bundle_variant": "  cloudfront_oac_private_s3  ",
        "repo_target": {
            "provider": "  gitlab  ",
            "repository": "  org/repo  ",
            "base_branch": "  main  ",
            "head_branch": "  codex/w3  ",
            "root_path": "  infra/aws  ",
        },
        "action_overrides": [
            {
                "action_id": "  action-1  ",
                "strategy_id": "  s3_bucket_block_public_access_standard  ",
                "strategy_inputs": {"preserve_existing_policy": False},
            }
        ],
    }
    group_request = SimpleNamespace(**raw_request)

    normalized_runs = normalize_grouped_request_from_remediation_runs(raw_request)
    normalized_group = normalize_grouped_request_from_action_group(group_request)

    assert normalized_runs == normalized_group
    assert normalized_runs.strategy_id == "s3_migrate_cloudfront_oac_private"
    assert normalized_runs.pr_bundle_variant == "cloudfront_oac_private_s3"
    assert normalized_runs.risk_acknowledged is True
    assert normalized_runs.repo_target == {
        "provider": "gitlab",
        "repository": "org/repo",
        "base_branch": "main",
        "head_branch": "codex/w3",
        "root_path": "infra/aws",
    }
    assert normalized_runs.action_overrides == (
        GroupedActionOverride(
            action_id="action-1",
            strategy_id="s3_bucket_block_public_access_standard",
            profile_id=None,
            strategy_inputs={"preserve_existing_policy": False},
        ),
    )


def test_duplicate_action_overrides_are_rejected() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action_one.id),
                strategy_id="s3_bucket_block_public_access_standard",
            ),
            GroupedActionOverride(
                action_id=str(action_one.id),
                strategy_id="s3_migrate_cloudfront_oac_private",
            ),
        ),
    )

    with pytest.raises(GroupedRemediationRunValidationError) as exc:
        build_grouped_run_persistence_plan(
            request=request,
            scope=_scope(),
            actions=[action_one],
            group_bundle_seed={"group_key": "group-1"},
        )

    assert exc.value.code == "duplicate_action_override"


def test_override_action_not_in_group_is_rejected() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        action_overrides=(
            GroupedActionOverride(
                action_id=str(uuid.uuid4()),
                strategy_id="s3_bucket_block_public_access_standard",
            ),
        ),
    )

    with pytest.raises(GroupedRemediationRunValidationError) as exc:
        build_grouped_run_persistence_plan(
            request=request,
            scope=_scope(),
            actions=[action_one],
            group_bundle_seed={"group_key": "group-1"},
        )

    assert exc.value.code == "override_action_not_in_group"


def test_invalid_override_strategy_is_rejected() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action_one.id),
                strategy_id="config_enable_account_local_delivery",
            ),
        ),
    )

    with pytest.raises(GroupedRemediationRunValidationError) as exc:
        build_grouped_run_persistence_plan(
            request=request,
            scope=_scope(),
            actions=[action_one],
            group_bundle_seed={"group_key": "group-1"},
        )

    assert exc.value.code == "invalid_override_strategy"
    assert "Unknown strategy_id" in str(exc.value)


def test_invalid_override_profile_is_rejected() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action_one.id),
                strategy_id="s3_bucket_block_public_access_standard",
                profile_id="not-a-profile",
            ),
        ),
    )

    with pytest.raises(GroupedRemediationRunValidationError) as exc:
        build_grouped_run_persistence_plan(
            request=request,
            scope=_scope(),
            actions=[action_one],
            group_bundle_seed={"group_key": "group-1"},
        )

    assert exc.value.code == "invalid_override_profile"
    assert "not valid" in str(exc.value)


def test_actions_without_overrides_inherit_top_level_strategy_and_profile() -> None:
    action_one = _make_action(priority=100, minutes_ago=1, action_type="aws_config_enabled")
    action_two = _make_action(priority=90, minutes_ago=2, action_type="aws_config_enabled")
    request = NormalizedGroupedRunRequest(
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action_one.id),
                strategy_id="config_enable_account_local_delivery",
            ),
        ),
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="aws_config_enabled"),
        actions=[action_two, action_one],
        group_bundle_seed={"group_key": "group-1"},
    )

    entries = {entry.action_id: entry for entry in plan.action_resolutions}
    inherited = entries[str(action_two.id)]
    overridden = entries[str(action_one.id)]

    assert overridden.strategy_id == "config_enable_account_local_delivery"
    assert overridden.profile_id == "config_enable_account_local_delivery"
    assert inherited.strategy_id == "config_enable_centralized_delivery"
    assert inherited.profile_id == "config_enable_centralized_delivery"
    assert inherited.strategy_inputs == {"delivery_bucket": "central-config-bucket"}
    assert plan.request.strategy_id == "config_enable_centralized_delivery"
    assert plan.request.strategy_inputs == {"delivery_bucket": "central-config-bucket"}


def test_grouped_artifacts_include_per_action_resolutions() -> None:
    action_one = _make_action(priority=100, minutes_ago=1, action_type="aws_config_enabled")
    action_two = _make_action(priority=90, minutes_ago=2, action_type="aws_config_enabled")
    request = NormalizedGroupedRunRequest(
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        repo_target={
            "provider": "gitlab",
            "repository": "org/repo",
            "base_branch": "main",
        },
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="aws_config_enabled"),
        actions=[action_two, action_one],
        group_bundle_seed={"group_key": "group-1"},
    )

    artifacts = plan.artifacts
    assert artifacts["selected_strategy"] == "config_enable_centralized_delivery"
    assert artifacts["strategy_inputs"] == {"delivery_bucket": "central-config-bucket"}
    assert artifacts["repo_target"] == {
        "provider": "gitlab",
        "repository": "org/repo",
        "base_branch": "main",
    }
    resolutions = artifacts["group_bundle"]["action_resolutions"]
    assert isinstance(resolutions, list)
    assert [entry["action_id"] for entry in resolutions] == list(plan.action_ids)
    first_resolution = resolutions[0]
    assert set(first_resolution) == {
        "action_id",
        "strategy_id",
        "profile_id",
        "strategy_inputs",
        "resolution",
    }
    assert first_resolution["resolution"]["strategy_id"] == first_resolution["strategy_id"]
    assert first_resolution["resolution"]["profile_id"] == first_resolution["profile_id"]


def test_representative_action_selection_is_deterministic() -> None:
    slow = _make_action(priority=80, minutes_ago=5)
    winner = _make_action(priority=100, minutes_ago=1)
    tie_break = _make_action(priority=100, minutes_ago=3)
    request = NormalizedGroupedRunRequest(strategy_id="s3_migrate_cloudfront_oac_private")

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[slow, winner, tie_break],
        group_bundle_seed={"group_key": "group-1"},
    )

    assert plan.representative_action_id == str(winner.id)
    assert list(plan.action_ids) == [str(winner.id), str(tie_break.id), str(slow.id)]


def test_repo_target_normalization_is_preserved_in_artifacts_and_queue_fields() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    raw_request = {
        "strategy_id": "s3_migrate_cloudfront_oac_private",
        "repo_target": {
            "provider": "  gitlab  ",
            "repository": "  org/repo  ",
            "base_branch": "  main  ",
            "head_branch": "  codex/w3  ",
        },
    }
    request = normalize_grouped_request_from_action_group(SimpleNamespace(**raw_request))

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[action_one],
        group_bundle_seed={"group_key": "group-1"},
    )

    expected_repo_target = {
        "provider": "gitlab",
        "repository": "org/repo",
        "base_branch": "main",
        "head_branch": "codex/w3",
    }
    assert plan.request.repo_target == expected_repo_target
    assert plan.artifacts["repo_target"] == expected_repo_target
    queue_fields = plan.queue_payload_fields_for_schema(REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1)
    assert queue_fields["repo_target"] == expected_repo_target


def test_queue_payload_fields_for_schema_v1_do_not_leak_queue_v2_or_worker_assumptions() -> None:
    action_one = _make_action(priority=80, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        repo_target={
            "provider": "gitlab",
            "repository": "org/repo",
            "base_branch": "main",
        },
        risk_acknowledged=True,
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[action_one],
        group_bundle_seed={"group_key": "group-1"},
    )

    queue_fields = plan.queue_payload_fields_for_schema(REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1)
    assert queue_fields == {
        "group_action_ids": [str(action_one.id)],
        "strategy_id": "s3_migrate_cloudfront_oac_private",
        "repo_target": {
            "provider": "gitlab",
            "repository": "org/repo",
            "base_branch": "main",
        },
        "risk_acknowledged": True,
    }
    assert "schema_version" not in queue_fields
    assert "profile_id" not in queue_fields
    assert "action_overrides" not in queue_fields
    assert "action_resolutions" not in queue_fields


def test_queue_payload_fields_for_schema_v2_include_canonical_action_resolutions() -> None:
    action_one = _make_action(priority=80, minutes_ago=1, action_type="aws_config_enabled")
    action_two = _make_action(priority=70, minutes_ago=2, action_type="aws_config_enabled")
    request = NormalizedGroupedRunRequest(
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        repo_target={"repository": "org/repo", "base_branch": "main"},
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="aws_config_enabled"),
        actions=[action_one, action_two],
        group_bundle_seed={"group_key": "group-1"},
    )

    queue_fields = plan.queue_payload_fields_for_schema(REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2)
    assert queue_fields["group_action_ids"] == [str(action_one.id), str(action_two.id)]
    assert queue_fields["repo_target"] == {"repository": "org/repo", "base_branch": "main"}
    assert [entry["action_id"] for entry in queue_fields["action_resolutions"]] == [
        str(action_one.id),
        str(action_two.id),
    ]


def _make_action(
    *,
    priority: int,
    minutes_ago: int,
    action_type: str = "s3_bucket_block_public_access",
) -> DummyAction:
    now = datetime.now(timezone.utc)
    action_id = uuid.uuid4()
    bucket_name = f"bucket-{str(action_id)[:8]}"
    return DummyAction(
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


def _scope(action_type: str = "s3_bucket_block_public_access") -> GroupedActionScope:
    return GroupedActionScope(
        action_type=action_type,
        account_id="123456789012",
        region="eu-north-1",
        status="open",
        group_key="group-1",
    )
