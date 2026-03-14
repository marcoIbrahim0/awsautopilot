from __future__ import annotations

import uuid

from backend.services.remediation_run_queue_contract import (
    grouped_run_signatures_match,
    normalize_grouped_run_artifact_signature,
    normalize_grouped_run_request_signature,
    reconstruct_resend_queue_inputs,
)
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
)


def test_reconstruct_resend_queue_inputs_prefers_canonical_single_resolution() -> None:
    resolution = {
        "strategy_id": "cloudtrail_enable_guided",
        "profile_id": "custom-cloudtrail-profile",
        "support_tier": "deterministic_bundle",
        "resolved_inputs": {"trail_name": "security-trail"},
        "missing_inputs": [],
        "missing_defaults": [],
        "blocked_reasons": [],
        "rejected_profiles": [],
        "finding_coverage": {},
        "preservation_summary": {},
        "decision_rationale": "",
        "decision_version": "resolver/v1",
    }
    queue_inputs = reconstruct_resend_queue_inputs(
        artifacts={
            "resolution": resolution,
            "selected_strategy": "cloudtrail_enable_guided",
            "strategy_inputs": {"trail_name": "legacy-trail"},
            "pr_bundle_variant": "terraform",
            "repo_target": {"repository": "acme/live", "base_branch": "main"},
            "risk_acknowledged": True,
        },
        mode="pr_only",
    )

    assert queue_inputs["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert queue_inputs["strategy_id"] == "cloudtrail_enable_guided"
    assert queue_inputs["strategy_inputs"] == {"trail_name": "legacy-trail"}
    assert queue_inputs["pr_bundle_variant"] == "terraform"
    assert queue_inputs["repo_target"] == {"repository": "acme/live", "base_branch": "main"}
    assert queue_inputs["resolution"] == resolution
    assert queue_inputs["action_resolutions"] is None


def test_reconstruct_resend_queue_inputs_prefers_canonical_grouped_action_resolutions() -> None:
    action_id = str(uuid.uuid4())
    action_resolutions = [
        {
            "action_id": action_id,
            "strategy_id": "config_enable_centralized_delivery",
            "profile_id": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "resolution": {
                "strategy_id": "config_enable_centralized_delivery",
                "profile_id": "config_enable_centralized_delivery",
                "support_tier": "review_required_bundle",
                "resolved_inputs": {"delivery_bucket": "central-config-bucket"},
                "missing_inputs": [],
                "missing_defaults": [],
                "blocked_reasons": [],
                "rejected_profiles": [],
                "finding_coverage": {},
                "preservation_summary": {},
                "decision_rationale": "",
                "decision_version": "resolver/v1",
            },
        }
    ]
    queue_inputs = reconstruct_resend_queue_inputs(
        artifacts={
            "selected_strategy": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "group_bundle": {
                "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
                "action_ids": [action_id],
                "action_resolutions": action_resolutions,
            },
        },
        mode="pr_only",
    )

    assert queue_inputs["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    assert queue_inputs["group_action_ids"] == [action_id]
    assert queue_inputs["action_resolutions"] == action_resolutions
    assert queue_inputs["resolution"] is None


def test_reconstruct_resend_queue_inputs_derives_legacy_single_resolution() -> None:
    queue_inputs = reconstruct_resend_queue_inputs(
        artifacts={
            "selected_strategy": "cloudtrail_enable_guided",
            "strategy_inputs": {"trail_name": "legacy-trail"},
            "risk_acknowledged": True,
        },
        mode="pr_only",
    )

    assert queue_inputs["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
    resolution = queue_inputs["resolution"]
    assert resolution is not None
    assert resolution["strategy_id"] == "cloudtrail_enable_guided"
    assert resolution["profile_id"] == "cloudtrail_enable_guided"
    assert resolution["support_tier"] == "review_required_bundle"
    assert resolution["resolved_inputs"] == {"trail_name": "legacy-trail"}


def test_reconstruct_resend_queue_inputs_derives_legacy_grouped_action_resolutions() -> None:
    action_one = str(uuid.uuid4())
    action_two = str(uuid.uuid4())
    queue_inputs = reconstruct_resend_queue_inputs(
        artifacts={
            "selected_strategy": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "group_bundle": {
                "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
                "action_ids": [action_one, action_two],
            },
        },
        mode="pr_only",
    )

    assert queue_inputs["schema_version"] == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
    action_resolutions = queue_inputs["action_resolutions"]
    assert queue_inputs["group_action_ids"] == [action_one, action_two]
    assert [entry["action_id"] for entry in action_resolutions] == [action_one, action_two]
    assert {entry["profile_id"] for entry in action_resolutions} == {"config_enable_centralized_delivery"}


def test_grouped_run_signatures_match_falls_back_to_legacy_identity_when_canonical_absent() -> None:
    existing_signature = normalize_grouped_run_artifact_signature(
        {
            "group_bundle": {"group_key": "s3_bucket_block_public_access|123456789012|eu-north-1|open"},
        }
    )
    request_signature = normalize_grouped_run_request_signature(
        group_key="s3_bucket_block_public_access|123456789012|eu-north-1|open",
        strategy_id="s3_migrate_cloudfront_oac_private",
        strategy_inputs=None,
        pr_bundle_variant=None,
        repo_target=None,
        action_resolutions=[
            {
                "action_id": str(uuid.uuid4()),
                "strategy_id": "s3_migrate_cloudfront_oac_private",
                "profile_id": "s3_migrate_cloudfront_oac_private",
                "strategy_inputs": {},
            }
        ],
    )

    assert grouped_run_signatures_match(existing_signature, request_signature) is True


def test_normalize_grouped_run_request_signature_is_deterministic() -> None:
    action_one = str(uuid.uuid4())
    action_two = str(uuid.uuid4())

    signature = normalize_grouped_run_request_signature(
        group_key="aws_config_enabled|123456789012|eu-north-1|open",
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        pr_bundle_variant=None,
        repo_target={"repository": "acme/live", "base_branch": "main"},
        action_resolutions=[
            {
                "action_id": action_two,
                "strategy_id": "config_enable_centralized_delivery",
                "profile_id": "config_enable_centralized_delivery",
                "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            },
            {
                "action_id": action_one,
                "strategy_id": "config_enable_account_local_delivery",
                "profile_id": "config_enable_account_local_delivery",
                "strategy_inputs": {},
            },
        ],
    )

    ordered_action_ids = [entry["action_id"] for entry in signature["action_resolutions"]]
    assert ordered_action_ids == sorted([action_one, action_two])
    normalized_entries = {entry["action_id"]: entry for entry in signature["action_resolutions"]}
    assert normalized_entries[action_one]["strategy_inputs"] is None


def test_grouped_run_signatures_match_identical_canonical_resolutions_even_with_mixed_order() -> None:
    action_one = str(uuid.uuid4())
    action_two = str(uuid.uuid4())
    canonical_resolutions = [
        {
            "action_id": action_one,
            "strategy_id": "config_enable_account_local_delivery",
            "profile_id": "config_enable_account_local_delivery",
            "strategy_inputs": {},
            "resolution": {
                "strategy_id": "config_enable_account_local_delivery",
                "profile_id": "config_enable_account_local_delivery",
                "support_tier": "deterministic_bundle",
                "resolved_inputs": {},
                "missing_inputs": [],
                "missing_defaults": [],
                "blocked_reasons": [],
                "rejected_profiles": [],
                "finding_coverage": {},
                "preservation_summary": {},
                "decision_rationale": "",
                "decision_version": "resolver/v1",
            },
        },
        {
            "action_id": action_two,
            "strategy_id": "config_enable_centralized_delivery",
            "profile_id": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "resolution": {
                "strategy_id": "config_enable_centralized_delivery",
                "profile_id": "config_enable_centralized_delivery",
                "support_tier": "deterministic_bundle",
                "resolved_inputs": {"delivery_bucket": "central-config-bucket"},
                "missing_inputs": [],
                "missing_defaults": [],
                "blocked_reasons": [],
                "rejected_profiles": [],
                "finding_coverage": {},
                "preservation_summary": {},
                "decision_rationale": "",
                "decision_version": "resolver/v1",
            },
        },
    ]

    existing_signature = normalize_grouped_run_artifact_signature(
        {
            "selected_strategy": "config_enable_centralized_delivery",
            "strategy_inputs": {"delivery_bucket": "central-config-bucket"},
            "repo_target": {"repository": "acme/live", "base_branch": "main"},
            "group_bundle": {
                "group_key": "aws_config_enabled|123456789012|eu-north-1|open",
                "action_ids": [action_two, action_one],
                "action_resolutions": list(reversed(canonical_resolutions)),
            },
        }
    )
    request_signature = normalize_grouped_run_request_signature(
        group_key="aws_config_enabled|123456789012|eu-north-1|open",
        strategy_id="config_enable_centralized_delivery",
        strategy_inputs={"delivery_bucket": "central-config-bucket"},
        pr_bundle_variant=None,
        repo_target={"repository": "acme/live", "base_branch": "main"},
        action_resolutions=canonical_resolutions,
    )

    assert grouped_run_signatures_match(existing_signature, request_signature) is True
