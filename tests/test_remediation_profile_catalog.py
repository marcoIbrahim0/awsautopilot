from __future__ import annotations

import copy

from backend.services.remediation_profile_catalog import (
    CLOUDTRAIL_FAMILY_RESOLVER_KIND,
    CONFIG_FAMILY_RESOLVER_KIND,
    PROFILE_REGISTRY,
    build_profile_registry,
    default_profile_id_for_strategy,
    get_profile_definition,
    list_profiles_for_action_type,
    list_profiles_for_strategy,
    recommended_profile_id_for_strategy,
)
from backend.services.root_key_resolution_adapter import ROOT_KEY_FAMILY_RESOLVER_KIND
from backend.services.s3_family_resolution_adapter import (
    S3_11_CREATE_PROFILE_ID,
    S3_11_FAMILY_RESOLVER_KIND,
    S3_15_CREATE_PROFILE_ID,
    S3_15_CUSTOMER_MANAGED_PROFILE_ID,
    S3_15_FAMILY_RESOLVER_KIND,
    S3_2_OAC_CREATE_PROFILE_ID,
    S3_2_FAMILY_RESOLVER_KIND,
    S3_5_EXEMPTION_CREATE_PROFILE_ID,
    S3_5_FAMILY_RESOLVER_KIND,
    S3_5_STRICT_CREATE_PROFILE_ID,
    S3_9_CREATE_PROFILE_ID,
    S3_9_FAMILY_RESOLVER_KIND,
)
from backend.services.remediation_strategy import STRATEGY_REGISTRY, RemediationStrategy

EC2_53_ACTION_TYPE = "sg_restrict_public_ports"
EC2_53_STRATEGY_ID = "sg_restrict_public_ports_guided"
IAM_4_ACTION_TYPE = "iam_root_access_key_absent"
S3_2_ACTION_TYPE = "s3_bucket_block_public_access"
S3_2_STANDARD_STRATEGY_ID = "s3_bucket_block_public_access_standard"
S3_2_OAC_STRATEGY_ID = "s3_migrate_cloudfront_oac_private"
S3_2_WEBSITE_STRATEGY_ID = "s3_migrate_website_cloudfront_private"
EC2_53_PROFILE_IDS = [
    "close_public",
    "close_and_revoke",
    "restrict_to_ip",
    "restrict_to_cidr",
    "ssm_only",
    "bastion_sg_reference",
]
S3_2_STANDARD_PROFILE_IDS = [
    "s3_bucket_block_public_access_standard",
    "s3_bucket_block_public_access_manual_preservation",
    "s3_bucket_block_public_access_review_public_policy_scrub",
]
S3_2_OAC_PROFILE_IDS = [
    "s3_migrate_cloudfront_oac_private",
    S3_2_OAC_CREATE_PROFILE_ID,
    "s3_migrate_cloudfront_oac_private_manual_preservation",
]
S3_2_WEBSITE_PROFILE_IDS = [
    "s3_migrate_website_cloudfront_private",
    "s3_migrate_website_cloudfront_private_review_required",
]
S3_9_PROFILE_IDS = [
    "s3_enable_access_logging_guided",
    S3_9_CREATE_PROFILE_ID,
    "s3_enable_access_logging_review_destination_safety",
]
S3_5_STRICT_PROFILE_IDS = [
    "s3_enforce_ssl_strict_deny",
    S3_5_STRICT_CREATE_PROFILE_ID,
]
S3_5_EXEMPTION_PROFILE_IDS = [
    "s3_enforce_ssl_with_principal_exemptions",
    S3_5_EXEMPTION_CREATE_PROFILE_ID,
]
S3_11_PROFILE_IDS = [
    "s3_enable_abort_incomplete_uploads",
    S3_11_CREATE_PROFILE_ID,
]
S3_15_PROFILE_IDS = [
    "s3_enable_sse_kms_guided",
    S3_15_CREATE_PROFILE_ID,
    S3_15_CUSTOMER_MANAGED_PROFILE_ID,
]


def _iter_strategy_rows() -> list[tuple[str, RemediationStrategy]]:
    rows: list[tuple[str, RemediationStrategy]] = []
    for action_type, strategies in STRATEGY_REGISTRY.items():
        for strategy in strategies:
            rows.append((action_type, strategy))
    return rows


def _expected_profile_ids(action_type: str, strategy: RemediationStrategy) -> list[str]:
    if action_type == EC2_53_ACTION_TYPE and strategy["strategy_id"] == EC2_53_STRATEGY_ID:
        return list(EC2_53_PROFILE_IDS)
    if action_type == S3_2_ACTION_TYPE and strategy["strategy_id"] == S3_2_STANDARD_STRATEGY_ID:
        return list(S3_2_STANDARD_PROFILE_IDS)
    if action_type == S3_2_ACTION_TYPE and strategy["strategy_id"] == S3_2_OAC_STRATEGY_ID:
        return list(S3_2_OAC_PROFILE_IDS)
    if action_type == S3_2_ACTION_TYPE and strategy["strategy_id"] == S3_2_WEBSITE_STRATEGY_ID:
        return list(S3_2_WEBSITE_PROFILE_IDS)
    if action_type == "s3_bucket_access_logging" and strategy["strategy_id"] == "s3_enable_access_logging_guided":
        return list(S3_9_PROFILE_IDS)
    if action_type == "s3_bucket_require_ssl" and strategy["strategy_id"] == "s3_enforce_ssl_strict_deny":
        return list(S3_5_STRICT_PROFILE_IDS)
    if action_type == "s3_bucket_require_ssl" and strategy["strategy_id"] == "s3_enforce_ssl_with_principal_exemptions":
        return list(S3_5_EXEMPTION_PROFILE_IDS)
    if action_type == "s3_bucket_lifecycle_configuration" and strategy["strategy_id"] == "s3_enable_abort_incomplete_uploads":
        return list(S3_11_PROFILE_IDS)
    if action_type == "s3_bucket_encryption_kms" and strategy["strategy_id"] == "s3_enable_sse_kms_guided":
        return list(S3_15_PROFILE_IDS)
    return [strategy["strategy_id"]]


def _expected_support_tier(action_type: str, strategy: RemediationStrategy) -> str:
    if action_type == IAM_4_ACTION_TYPE:
        return "manual_guidance_only"
    if strategy["exception_only"]:
        return "manual_guidance_only"
    return "deterministic_bundle"


def _profile_expected_support_tier(
    action_type: str,
    strategy: RemediationStrategy,
    profile_id: str,
) -> str:
    if profile_id in {
        "s3_bucket_block_public_access_manual_preservation",
        "s3_bucket_block_public_access_review_public_policy_scrub",
        "s3_migrate_cloudfront_oac_private_manual_preservation",
        "s3_migrate_website_cloudfront_private_review_required",
    }:
        return (
            "review_required_bundle"
            if profile_id in {
                "s3_bucket_block_public_access_review_public_policy_scrub",
                "s3_migrate_website_cloudfront_private_review_required",
            }
            else "manual_guidance_only"
        )
    if profile_id in {
        "s3_enable_access_logging_review_destination_safety",
        S3_15_CUSTOMER_MANAGED_PROFILE_ID,
    }:
        return "review_required_bundle"
    return _expected_support_tier(action_type, strategy)


def _profile_expected_recommended(strategy: RemediationStrategy, profile_id: str) -> bool:
    if profile_id in {
        "s3_bucket_block_public_access_manual_preservation",
        "s3_bucket_block_public_access_review_public_policy_scrub",
        "s3_migrate_cloudfront_oac_private_manual_preservation",
        "s3_migrate_website_cloudfront_private_review_required",
        "s3_enable_access_logging_review_destination_safety",
        S3_2_OAC_CREATE_PROFILE_ID,
        S3_5_STRICT_CREATE_PROFILE_ID,
        S3_5_EXEMPTION_CREATE_PROFILE_ID,
        S3_9_CREATE_PROFILE_ID,
        S3_11_CREATE_PROFILE_ID,
        S3_15_CREATE_PROFILE_ID,
        S3_15_CUSTOMER_MANAGED_PROFILE_ID,
    }:
        return False
    if profile_id == S3_2_WEBSITE_STRATEGY_ID:
        return True
    return strategy["recommended"]


def test_every_strategy_row_has_a_seeded_profile() -> None:
    assert set(PROFILE_REGISTRY) == set(STRATEGY_REGISTRY)
    for action_type, strategies in STRATEGY_REGISTRY.items():
        assert len(list_profiles_for_action_type(action_type)) == sum(
            len(_expected_profile_ids(action_type, strategy))
            for strategy in strategies
        )
        for strategy in strategies:
            profiles = list_profiles_for_strategy(action_type, strategy["strategy_id"])
            assert [profile.profile_id for profile in profiles] == _expected_profile_ids(action_type, strategy)
            for profile in profiles:
                assert profile.action_type == action_type
                assert profile.strategy_id == strategy["strategy_id"]
                assert profile.supports_exception_flow is strategy["supports_exception_flow"]
                assert profile.exception_only is strategy["exception_only"]
                if action_type == EC2_53_ACTION_TYPE and strategy["strategy_id"] == EC2_53_STRATEGY_ID:
                    continue
                    assert profile.default_support_tier == _profile_expected_support_tier(
                        action_type,
                        strategy,
                        profile.profile_id,
                    )
                assert profile.recommended is _profile_expected_recommended(strategy, profile.profile_id)
                assert profile.requires_inputs is strategy["requires_inputs"]


def test_compatibility_profiles_use_strategy_ids_as_profile_ids() -> None:
    for action_type, strategy in _iter_strategy_rows():
        if action_type == EC2_53_ACTION_TYPE and strategy["strategy_id"] == EC2_53_STRATEGY_ID:
            continue
        profile = get_profile_definition(
            action_type,
            strategy["strategy_id"],
            strategy["strategy_id"],
        )
        assert profile is not None
        assert profile.profile_id == strategy["strategy_id"]
        assert profile.strategy_id == strategy["strategy_id"]


def test_lookup_helpers_are_stable_for_valid_strategies() -> None:
    for action_type, strategy in _iter_strategy_rows():
        strategy_id = strategy["strategy_id"]
        first_lookup = list_profiles_for_strategy(action_type, strategy_id)
        second_lookup = list_profiles_for_strategy(action_type, strategy_id)
        assert first_lookup == second_lookup
        assert [profile.profile_id for profile in first_lookup] == _expected_profile_ids(action_type, strategy)
        for profile in first_lookup:
            assert get_profile_definition(action_type, strategy_id, profile.profile_id) == profile
        assert default_profile_id_for_strategy(action_type, strategy_id) == first_lookup[0].profile_id
        assert recommended_profile_id_for_strategy(action_type, strategy_id) == first_lookup[0].profile_id


def test_ec2_53_family_profiles_expose_expected_support_tiers() -> None:
    profiles = {
        profile.profile_id: profile
        for profile in list_profiles_for_strategy(EC2_53_ACTION_TYPE, EC2_53_STRATEGY_ID)
    }

    assert set(profiles) == set(EC2_53_PROFILE_IDS)
    assert profiles["close_public"].default_support_tier == "deterministic_bundle"
    assert profiles["close_and_revoke"].default_support_tier == "deterministic_bundle"
    assert profiles["restrict_to_ip"].default_support_tier == "deterministic_bundle"
    assert profiles["restrict_to_cidr"].default_support_tier == "deterministic_bundle"
    assert profiles["ssm_only"].default_support_tier == "deterministic_bundle"
    assert profiles["ssm_only"].default_inputs == {"access_mode": "ssm_only"}
    assert profiles["ssm_only"].legacy_input_hints == {"access_mode": "ssm_only"}
    assert profiles["bastion_sg_reference"].default_support_tier == "deterministic_bundle"
    assert profiles["bastion_sg_reference"].default_inputs == {"access_mode": "bastion_sg_reference"}
    assert profiles["bastion_sg_reference"].legacy_input_hints == {"access_mode": "bastion_sg_reference"}
    assert profiles["close_public"].recommended is True
    assert profiles["close_public"].family_resolver_kind == "ec2_53_access_path"


def test_iam_4_profiles_are_guidance_only_catalog_rows() -> None:
    profiles = list_profiles_for_strategy(IAM_4_ACTION_TYPE, "iam_root_key_disable")

    assert len(profiles) == 1
    profile = profiles[0]
    assert profile.profile_id == "iam_root_key_disable"
    assert profile.default_support_tier == "manual_guidance_only"
    assert profile.family_resolver_kind == ROOT_KEY_FAMILY_RESOLVER_KIND


def test_s3_family_profiles_use_resolver_owned_family_kinds() -> None:
    s3_2_standard = list_profiles_for_strategy(S3_2_ACTION_TYPE, S3_2_STANDARD_STRATEGY_ID)
    s3_2_oac = list_profiles_for_strategy(S3_2_ACTION_TYPE, S3_2_OAC_STRATEGY_ID)
    s3_9 = list_profiles_for_strategy("s3_bucket_access_logging", "s3_enable_access_logging_guided")
    s3_5_strict = list_profiles_for_strategy("s3_bucket_require_ssl", "s3_enforce_ssl_strict_deny")
    s3_11 = list_profiles_for_strategy("s3_bucket_lifecycle_configuration", "s3_enable_abort_incomplete_uploads")
    s3_15 = list_profiles_for_strategy("s3_bucket_encryption_kms", "s3_enable_sse_kms_guided")

    assert [profile.profile_id for profile in s3_2_standard] == S3_2_STANDARD_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_2_standard] == [
        S3_2_FAMILY_RESOLVER_KIND,
        S3_2_FAMILY_RESOLVER_KIND,
        S3_2_FAMILY_RESOLVER_KIND,
    ]
    assert [profile.profile_id for profile in s3_2_oac] == S3_2_OAC_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_2_oac] == [
        S3_2_FAMILY_RESOLVER_KIND,
        S3_2_FAMILY_RESOLVER_KIND,
        S3_2_FAMILY_RESOLVER_KIND,
    ]
    assert [profile.profile_id for profile in s3_9] == S3_9_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_9] == [
        S3_9_FAMILY_RESOLVER_KIND,
        S3_9_FAMILY_RESOLVER_KIND,
        S3_9_FAMILY_RESOLVER_KIND,
    ]
    assert [profile.profile_id for profile in s3_5_strict] == S3_5_STRICT_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_5_strict] == [
        S3_5_FAMILY_RESOLVER_KIND,
        S3_5_FAMILY_RESOLVER_KIND,
    ]
    assert [profile.profile_id for profile in s3_11] == S3_11_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_11] == [
        S3_11_FAMILY_RESOLVER_KIND,
        S3_11_FAMILY_RESOLVER_KIND,
    ]
    assert [profile.profile_id for profile in s3_15] == S3_15_PROFILE_IDS
    assert [profile.family_resolver_kind for profile in s3_15] == [
        S3_15_FAMILY_RESOLVER_KIND,
        S3_15_FAMILY_RESOLVER_KIND,
        S3_15_FAMILY_RESOLVER_KIND,
    ]


def test_cloudtrail_and_config_profiles_use_family_resolver_kinds() -> None:
    cloudtrail = list_profiles_for_strategy("cloudtrail_enabled", "cloudtrail_enable_guided")
    config_local = list_profiles_for_strategy("aws_config_enabled", "config_enable_account_local_delivery")
    config_central = list_profiles_for_strategy("aws_config_enabled", "config_enable_centralized_delivery")
    config_exception = list_profiles_for_strategy("aws_config_enabled", "config_keep_exception")

    assert len(cloudtrail) == 1
    assert cloudtrail[0].family_resolver_kind == CLOUDTRAIL_FAMILY_RESOLVER_KIND
    assert len(config_local) == 1
    assert config_local[0].family_resolver_kind == CONFIG_FAMILY_RESOLVER_KIND
    assert len(config_central) == 1
    assert config_central[0].family_resolver_kind == CONFIG_FAMILY_RESOLVER_KIND
    assert len(config_exception) == 1
    assert config_exception[0].family_resolver_kind == CONFIG_FAMILY_RESOLVER_KIND


def test_invalid_profile_catalog_combinations_fail_safely() -> None:
    first_action_type, first_strategies = next(iter(STRATEGY_REGISTRY.items()))
    first_strategy_id = first_strategies[0]["strategy_id"]
    other_action_type = next(
        action_type
        for action_type in STRATEGY_REGISTRY
        if action_type != first_action_type
    )

    assert list_profiles_for_action_type(None) == []
    assert list_profiles_for_action_type("not_real") == []
    assert list_profiles_for_strategy(first_action_type, None) == []
    assert list_profiles_for_strategy(first_action_type, "not_real") == []
    assert get_profile_definition(first_action_type, first_strategy_id, None) is None
    assert get_profile_definition(first_action_type, first_strategy_id, "not_real") is None
    assert get_profile_definition(other_action_type, first_strategy_id, first_strategy_id) is None
    assert default_profile_id_for_strategy(first_action_type, "not_real") is None
    assert recommended_profile_id_for_strategy("not_real", first_strategy_id) is None


def test_profile_catalog_build_is_additive_and_does_not_mutate_strategies() -> None:
    snapshot = copy.deepcopy(STRATEGY_REGISTRY)
    rebuilt_registry = build_profile_registry(STRATEGY_REGISTRY)

    assert STRATEGY_REGISTRY == snapshot
    assert rebuilt_registry == PROFILE_REGISTRY
    for action_type, strategy in _iter_strategy_rows():
        assert "profile_id" not in strategy
        profiles = rebuilt_registry[action_type][strategy["strategy_id"]]
        assert [profile.profile_id for profile in profiles] == _expected_profile_ids(action_type, strategy)
        for profile in profiles:
            assert profile.strategy_id == strategy["strategy_id"]
