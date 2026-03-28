from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
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
from backend.services.remediation_profile_read_path import build_preview_resolution
from backend.services.remediation_risk import evaluate_strategy_impact as real_evaluate_strategy_impact
from backend.services.remediation_strategy import validate_strategy
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
    assert inherited.strategy_inputs == {
        "recording_scope": "keep_existing",
        "delivery_bucket_mode": "use_existing",
        "delivery_bucket": "central-config-bucket",
        "encrypt_with_kms": False,
    }
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


def test_s3_access_logging_grouped_plan_splits_bucket_and_account_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bucket_action = DummyAction(
        id=uuid.uuid4(),
        action_type="s3_bucket_access_logging",
        account_id="123456789012",
        region="eu-north-1",
        status="open",
        priority=100,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        target_id="123456789012|eu-north-1|arn:aws:s3:::config-bucket-123456789012|S3.9",
        resource_id="arn:aws:s3:::config-bucket-123456789012",
    )
    account_action = DummyAction(
        id=uuid.uuid4(),
        action_type="s3_bucket_access_logging",
        account_id="123456789012",
        region="eu-north-1",
        status="open",
        priority=90,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        target_id="123456789012|eu-north-1|AWS::::Account:123456789012|S3.9",
        resource_id="AWS::::Account:123456789012",
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_enable_access_logging_guided",
        strategy_inputs={"log_bucket_name": "security-autopilot-access-logs-123456789012"},
        risk_acknowledged=True,
    )

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **kwargs: {
            "s3_access_logging_destination_safe": True,
            "s3_access_logging_destination_bucket_reachable": True,
            "support_bucket_probe": {"safe": True},
        }
        if "arn:aws:s3:::" in str(getattr(kwargs["action"], "target_id", ""))
        else {},
    )
    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
        real_evaluate_strategy_impact,
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="s3_bucket_access_logging"),
        actions=[account_action, bucket_action],
        group_bundle_seed={"group_key": "group-1"},
    )

    resolutions = {entry.action_id: entry.resolution for entry in plan.action_resolutions}
    strategy_inputs = {entry.action_id: entry.strategy_inputs for entry in plan.action_resolutions}
    assert resolutions[str(bucket_action.id)]["support_tier"] == "deterministic_bundle"
    assert resolutions[str(account_action.id)]["support_tier"] == "review_required_bundle"
    assert plan.artifacts["group_bundle"]["action_resolutions"][0]["strategy_id"] == "s3_enable_access_logging_guided"
    assert plan.artifacts["group_bundle"]["action_resolutions"][1]["strategy_id"] == "s3_enable_access_logging_guided"


def test_s3_ssl_grouped_plan_persists_bucket_policy_evidence_for_executable_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = replace(
        _make_action(priority=100, minutes_ago=1, action_type="s3_bucket_require_ssl"),
        target_id="123456789012|eu-north-1|arn:aws:s3:::ssl-bucket|S3.5",
        resource_id="arn:aws:s3:::ssl-bucket",
    )
    existing_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowTrustedRead",
                    "Effect": "Allow",
                    "Principal": {"AWS": "arn:aws:iam::123456789012:role/Reader"},
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::ssl-bucket/*",
                }
            ],
        }
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_enforce_ssl_strict_deny",
        risk_acknowledged=True,
    )

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {
            "s3_policy_analysis_possible": True,
            "evidence": {
                "existing_bucket_policy_statement_count": 1,
                "existing_bucket_policy_json": existing_policy,
            },
        },
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="s3_bucket_require_ssl"),
        actions=[action],
        group_bundle_seed={"group_key": "group-1"},
    )

    persisted_inputs = plan.action_resolutions[0].strategy_inputs
    assert persisted_inputs["existing_bucket_policy_statement_count"] == 1
    assert persisted_inputs["existing_bucket_policy_json"] == existing_policy
    bundle_entry = plan.artifacts["group_bundle"]["action_resolutions"][0]
    assert bundle_entry["strategy_inputs"]["existing_bucket_policy_statement_count"] == 1
    assert bundle_entry["strategy_inputs"]["existing_bucket_policy_json"] == existing_policy


def test_s3_ssl_grouped_plan_keeps_apply_time_merge_executable_without_policy_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = replace(
        _make_action(priority=100, minutes_ago=1, action_type="s3_bucket_require_ssl"),
        target_id="123456789012|eu-north-1|arn:aws:s3:::ssl-bucket|S3.5",
        resource_id="arn:aws:s3:::ssl-bucket",
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_enforce_ssl_strict_deny",
        risk_acknowledged=True,
    )

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {
            "s3_policy_analysis_possible": False,
            "s3_policy_analysis_error": "AccessDenied",
            "evidence": {
                "target_bucket": "ssl-bucket",
                "existing_bucket_policy_capture_error": "AccessDenied",
            },
        },
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="s3_bucket_require_ssl"),
        actions=[action],
        group_bundle_seed={"group_key": "group-1"},
    )

    resolution = plan.action_resolutions[0].resolution
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert resolution["preservation_summary"]["apply_time_merge"] is True
    assert resolution["preservation_summary"]["merge_safe_policy_available"] is False
    assert "existing_bucket_policy_json" not in plan.action_resolutions[0].strategy_inputs


def test_s3_2_oac_grouped_plan_keeps_apply_time_merge_executable_without_policy_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = replace(
        _make_action(priority=100, minutes_ago=1),
        target_id="123456789012|eu-north-1|arn:aws:s3:::oac-bucket|S3.2",
        resource_id="arn:aws:s3:::oac-bucket",
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_cloudfront_oac_private",
        risk_acknowledged=True,
    )

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {
            "s3_bucket_policy_public": False,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": False,
            "access_path_evidence_reason": "Unable to capture existing bucket policy (AccessDenied).",
            "evidence": {
                "target_bucket": "oac-bucket",
                "existing_bucket_policy_capture_error": "AccessDenied",
            },
        },
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[action],
        group_bundle_seed={"group_key": "group-1"},
    )

    resolution = plan.action_resolutions[0].resolution
    assert resolution["support_tier"] == "deterministic_bundle"
    assert resolution["blocked_reasons"] == []
    assert resolution["preservation_summary"]["apply_time_merge"] is True
    assert "AccessDenied" in resolution["preservation_summary"]["apply_time_merge_reason"]
    assert "existing_bucket_policy_json" not in plan.action_resolutions[0].strategy_inputs


def test_s3_2_standard_grouped_plan_uses_review_policy_scrub_for_public_non_website_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = replace(
        _make_action(priority=100, minutes_ago=1),
        target_id="123456789012|eu-north-1|arn:aws:s3:::public-bucket|S3.2",
        resource_id="arn:aws:s3:::public-bucket",
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_bucket_block_public_access_standard",
        risk_acknowledged=True,
    )

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {
            "s3_bucket_policy_public": True,
            "s3_bucket_website_configured": False,
            "access_path_evidence_available": True,
        },
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[action],
        group_bundle_seed={"group_key": "group-public-scrub"},
    )

    resolution = plan.action_resolutions[0].resolution
    assert resolution["profile_id"] == "s3_bucket_block_public_access_review_public_policy_scrub"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["preservation_summary"]["public_policy_scrub_available"] is True
    assert resolution["preservation_summary"]["manual_preservation_required"] is False


def test_ec2_53_grouped_plan_matches_preview_for_executable_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable_action = replace(
        _make_action(priority=100, minutes_ago=1, action_type="sg_restrict_public_ports"),
        target_id="123456789012|eu-north-1|sg-0123456789abcdef0|EC2.53",
        resource_id="sg-0123456789abcdef0",
    )
    manual_action = replace(
        _make_action(priority=90, minutes_ago=2, action_type="sg_restrict_public_ports"),
        target_id="123456789012|eu-north-1|sg-0fedcba9876543210|EC2.53",
        resource_id="sg-0fedcba9876543210",
    )
    request = NormalizedGroupedRunRequest(
        strategy_id="sg_restrict_public_ports_guided",
        risk_acknowledged=True,
        action_overrides=(
            GroupedActionOverride(
                action_id=str(executable_action.id),
                profile_id="close_and_revoke",
            ),
            GroupedActionOverride(
                action_id=str(manual_action.id),
                profile_id="bastion_sg_reference",
            ),
        ),
    )
    strategy = validate_strategy("sg_restrict_public_ports", "sg_restrict_public_ports_guided", "pr_only")

    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.collect_runtime_risk_signals",
        lambda **_: {},
    )
    monkeypatch.setattr(
        "backend.services.grouped_remediation_runs.evaluate_strategy_impact",
        real_evaluate_strategy_impact,
    )

    preview = build_preview_resolution(
        action_type="sg_restrict_public_ports",
        strategy=strategy,
        profile_id="close_and_revoke",
        strategy_inputs={"access_mode": "close_and_revoke"},
        tenant_settings={},
        runtime_signals={},
        dependency_checks=None,
        action=executable_action,
    )
    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="sg_restrict_public_ports"),
        actions=[manual_action, executable_action],
        group_bundle_seed={"group_key": "group-1"},
        tenant_settings={"approved_bastion_security_group_ids": ["sg-bastion-1", "sg-bastion-2"]},
    )

    assert preview is not None
    resolutions = {entry.action_id: entry.resolution for entry in plan.action_resolutions}
    strategy_inputs = {entry.action_id: entry.strategy_inputs for entry in plan.action_resolutions}
    assert preview["profile_id"] == "close_and_revoke"
    assert preview["support_tier"] == "deterministic_bundle"
    assert resolutions[str(executable_action.id)]["profile_id"] == preview["profile_id"]
    assert resolutions[str(executable_action.id)]["support_tier"] == preview["support_tier"]
    assert resolutions[str(manual_action.id)]["profile_id"] == "bastion_sg_reference"
    assert resolutions[str(manual_action.id)]["support_tier"] == "deterministic_bundle"
    assert strategy_inputs[str(manual_action.id)] == {
        "access_mode": "bastion_sg_reference",
        "approved_bastion_security_group_ids": ["sg-bastion-1", "sg-bastion-2"],
    }


def test_grouped_run_persistence_plan_keeps_ssm_only_executable() -> None:
    executable_action = _make_action(priority=100, minutes_ago=1, action_type="sg_restrict_public_ports")
    executable_action.target_id = "123456789012|eu-north-1|sg-0123456789abcdef0|EC2.53"
    sibling_action = _make_action(priority=90, minutes_ago=2, action_type="sg_restrict_public_ports")
    sibling_action.target_id = "123456789012|eu-north-1|sg-0fedcba9876543210|EC2.53"

    request = NormalizedGroupedRunRequest(
        strategy_id="sg_restrict_public_ports_guided",
        risk_acknowledged=True,
        action_overrides=(
            GroupedActionOverride(
                action_id=str(executable_action.id),
                profile_id="ssm_only",
            ),
        ),
    )
    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="sg_restrict_public_ports"),
        actions=[sibling_action, executable_action],
        group_bundle_seed={"group_key": "group-ssm"},
    )

    resolutions = {entry.action_id: entry.resolution for entry in plan.action_resolutions}
    assert resolutions[str(executable_action.id)]["profile_id"] == "ssm_only"
    assert resolutions[str(executable_action.id)]["support_tier"] == "deterministic_bundle"


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


def test_grouped_website_strategy_rejects_top_level_selection() -> None:
    action = _make_action(priority=100, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_migrate_website_cloudfront_private",
        strategy_inputs={
            "aliases": ["www.example.com"],
            "route53_hosted_zone_id": "Z123456ABCDEFG",
            "acm_certificate_arn": "arn:aws:acm:us-east-1:123456789012:certificate/abc",
        },
    )

    with pytest.raises(GroupedRemediationRunValidationError) as exc:
        build_grouped_run_persistence_plan(
            request=request,
            scope=_scope(),
            actions=[action],
            group_bundle_seed={"group_key": "group-website"},
        )

    assert exc.value.code == "grouped_website_strategy_requires_action_overrides"


def test_grouped_website_override_without_dns_inputs_downgrades_to_review_required() -> None:
    action = _make_action(priority=100, minutes_ago=1)
    request = NormalizedGroupedRunRequest(
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action.id),
                strategy_id="s3_migrate_website_cloudfront_private",
            ),
        ),
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(),
        actions=[action],
        group_bundle_seed={"group_key": "group-website"},
    )

    resolution = plan.action_resolutions[0].resolution
    assert plan.action_resolutions[0].strategy_id == "s3_migrate_website_cloudfront_private"
    assert resolution["profile_id"] == "s3_migrate_website_cloudfront_private_review_required"
    assert resolution["support_tier"] == "review_required_bundle"
    assert any("strategy_inputs.aliases" in reason for reason in resolution["blocked_reasons"])


def test_same_strategy_profile_overrides_inherit_top_level_strategy_inputs() -> None:
    action_one = _make_action(priority=100, minutes_ago=1, action_type="s3_bucket_access_logging")
    action_two = _make_action(priority=90, minutes_ago=2, action_type="s3_bucket_access_logging")
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_enable_access_logging_guided",
        strategy_inputs={"log_bucket_name": "dedicated-access-log-bucket"},
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action_one.id),
                profile_id="s3_enable_access_logging_review_destination_safety",
            ),
            GroupedActionOverride(
                action_id=str(action_two.id),
                profile_id="s3_enable_access_logging_review_destination_safety",
            ),
        ),
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="s3_bucket_access_logging"),
        actions=[action_two, action_one],
        group_bundle_seed={"group_key": "group-1"},
    )

    for entry in plan.action_resolutions:
        assert entry.strategy_id == "s3_enable_access_logging_guided"
        assert entry.profile_id == "s3_enable_access_logging_review_destination_safety"
        assert entry.strategy_inputs == {"log_bucket_name": "dedicated-access-log-bucket"}


def test_same_strategy_profile_overrides_derive_s3_9_log_bucket_name_for_bucket_scope() -> None:
    action = _make_action(priority=100, minutes_ago=1, action_type="s3_bucket_access_logging")
    request = NormalizedGroupedRunRequest(
        strategy_id="s3_enable_access_logging_guided",
        action_overrides=(
            GroupedActionOverride(
                action_id=str(action.id),
                profile_id="s3_enable_access_logging_review_destination_safety",
            ),
        ),
    )

    plan = build_grouped_run_persistence_plan(
        request=request,
        scope=_scope(action_type="s3_bucket_access_logging"),
        actions=[action],
        group_bundle_seed={"group_key": "group-1"},
    )

    assert plan.action_resolutions[0].strategy_inputs == {
        "log_bucket_name": f"{action.resource_id.split(':::')[-1]}-access-logs",
    }
    assert plan.action_resolutions[0].resolution["support_tier"] == "review_required_bundle"


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
