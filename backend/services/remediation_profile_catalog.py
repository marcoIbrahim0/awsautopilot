"""
Wave 1 remediation profile catalog seeded from the public strategy catalog.

Profiles are an internal namespace beneath public strategies. Wave 1 keeps a
one-to-one compatibility mapping where `profile_id == strategy_id`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from backend.services.root_key_resolution_adapter import (
    root_key_default_support_tier,
    root_key_family_resolver_kind,
)
from backend.services.s3_family_resolution_adapter import (
    S3_11_FAMILY_RESOLVER_KIND,
    S3_11_STRATEGY_ID,
    S3_2_FAMILY_RESOLVER_KIND,
    S3_2_OAC_MANUAL_PROFILE_ID,
    S3_2_OAC_STRATEGY_ID,
    S3_2_STANDARD_MANUAL_PROFILE_ID,
    S3_2_STANDARD_STRATEGY_ID,
    S3_5_EXEMPTION_STRATEGY_ID,
    S3_5_FAMILY_RESOLVER_KIND,
    S3_5_STRICT_STRATEGY_ID,
)
from backend.services.remediation_strategy import STRATEGY_REGISTRY, RemediationStrategy

SupportTier = Literal[
    "deterministic_bundle",
    "review_required_bundle",
    "manual_guidance_only",
]


@dataclass(frozen=True, slots=True)
class RemediationProfileDefinition:
    """Internal resolver-owned profile definition for one strategy/profile row."""

    action_type: str
    strategy_id: str
    profile_id: str
    label: str
    default_support_tier: SupportTier
    recommended: bool
    requires_inputs: bool
    supports_exception_flow: bool
    exception_only: bool
    family_resolver_kind: str = "compatibility"
    default_inputs: Mapping[str, Any] = field(default_factory=dict)
    legacy_input_hints: Mapping[str, Any] = field(default_factory=dict)


StrategyProfileRegistry = dict[str, tuple[RemediationProfileDefinition, ...]]
ProfileRegistry = dict[str, StrategyProfileRegistry]


def _normalize_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _default_support_tier(action_type: str, strategy: RemediationStrategy) -> SupportTier:
    # Wave 1 seeds compatibility rows only, so explicit exception paths are the
    # only strategies that default away from executable bundle semantics.
    root_key_tier = root_key_default_support_tier(action_type)
    if root_key_tier is not None:
        return root_key_tier
    if strategy["exception_only"]:
        return "manual_guidance_only"
    return "deterministic_bundle"


def _seed_profile_definition(
    action_type: str,
    strategy: RemediationStrategy,
) -> RemediationProfileDefinition:
    strategy_id = strategy["strategy_id"]
    return RemediationProfileDefinition(
        action_type=action_type,
        strategy_id=strategy_id,
        profile_id=strategy_id,
        label=strategy["label"],
        default_support_tier=_default_support_tier(action_type, strategy),
        recommended=strategy["recommended"],
        requires_inputs=strategy["requires_inputs"],
        supports_exception_flow=strategy["supports_exception_flow"],
        exception_only=strategy["exception_only"],
        family_resolver_kind=root_key_family_resolver_kind(action_type),
    )


def _ec2_53_family_profiles() -> tuple[RemediationProfileDefinition, ...]:
    action_type = "sg_restrict_public_ports"
    strategy_id = "sg_restrict_public_ports_guided"
    family_kind = "ec2_53_access_path"
    return (
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="close_public",
            label="Close all public access",
            default_support_tier="deterministic_bundle",
            recommended=True,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
            default_inputs={"access_mode": "close_public"},
            legacy_input_hints={"access_mode": "close_public"},
        ),
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="close_and_revoke",
            label="Close public and auto-remove old rules",
            default_support_tier="deterministic_bundle",
            recommended=False,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
            default_inputs={"access_mode": "close_and_revoke"},
            legacy_input_hints={"access_mode": "close_and_revoke"},
        ),
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="restrict_to_ip",
            label="Restrict to my IP",
            default_support_tier="deterministic_bundle",
            recommended=False,
            requires_inputs=True,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
            default_inputs={"access_mode": "restrict_to_ip"},
            legacy_input_hints={"access_mode": "restrict_to_ip"},
        ),
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="restrict_to_cidr",
            label="Restrict to custom CIDR",
            default_support_tier="deterministic_bundle",
            recommended=False,
            requires_inputs=True,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
            default_inputs={"access_mode": "restrict_to_cidr"},
            legacy_input_hints={"access_mode": "restrict_to_cidr"},
        ),
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="ssm_only",
            label="Use SSM only",
            default_support_tier="manual_guidance_only",
            recommended=False,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
        ),
        RemediationProfileDefinition(
            action_type=action_type,
            strategy_id=strategy_id,
            profile_id="bastion_sg_reference",
            label="Reference bastion security group",
            default_support_tier="review_required_bundle",
            recommended=False,
            requires_inputs=True,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=family_kind,
        ),
    )


def _s3_2_standard_family_profiles() -> tuple[RemediationProfileDefinition, ...]:
    return (
        RemediationProfileDefinition(
            action_type="s3_bucket_block_public_access",
            strategy_id=S3_2_STANDARD_STRATEGY_ID,
            profile_id=S3_2_STANDARD_STRATEGY_ID,
            label="Block public access on bucket",
            default_support_tier="deterministic_bundle",
            recommended=False,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=S3_2_FAMILY_RESOLVER_KIND,
        ),
        RemediationProfileDefinition(
            action_type="s3_bucket_block_public_access",
            strategy_id=S3_2_STANDARD_STRATEGY_ID,
            profile_id=S3_2_STANDARD_MANUAL_PROFILE_ID,
            label="Manual website/public preservation review",
            default_support_tier="manual_guidance_only",
            recommended=False,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=S3_2_FAMILY_RESOLVER_KIND,
        ),
    )


def _s3_2_oac_family_profiles() -> tuple[RemediationProfileDefinition, ...]:
    return (
        RemediationProfileDefinition(
            action_type="s3_bucket_block_public_access",
            strategy_id=S3_2_OAC_STRATEGY_ID,
            profile_id=S3_2_OAC_STRATEGY_ID,
            label="Migrate to CloudFront + OAC + private S3",
            default_support_tier="deterministic_bundle",
            recommended=True,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=S3_2_FAMILY_RESOLVER_KIND,
        ),
        RemediationProfileDefinition(
            action_type="s3_bucket_block_public_access",
            strategy_id=S3_2_OAC_STRATEGY_ID,
            profile_id=S3_2_OAC_MANUAL_PROFILE_ID,
            label="Manual CloudFront/OAC preservation review",
            default_support_tier="manual_guidance_only",
            recommended=False,
            requires_inputs=False,
            supports_exception_flow=False,
            exception_only=False,
            family_resolver_kind=S3_2_FAMILY_RESOLVER_KIND,
        ),
    )


def _family_clone(
    action_type: str,
    strategy: RemediationStrategy,
    *,
    family_kind: str,
) -> tuple[RemediationProfileDefinition, ...]:
    profile = _seed_profile_definition(action_type, strategy)
    return (
        RemediationProfileDefinition(
            action_type=profile.action_type,
            strategy_id=profile.strategy_id,
            profile_id=profile.profile_id,
            label=profile.label,
            default_support_tier=profile.default_support_tier,
            recommended=profile.recommended,
            requires_inputs=profile.requires_inputs,
            supports_exception_flow=profile.supports_exception_flow,
            exception_only=profile.exception_only,
            family_resolver_kind=family_kind,
            default_inputs=profile.default_inputs,
            legacy_input_hints=profile.legacy_input_hints,
        ),
    )


def _profile_rows_for_strategy(
    action_type: str,
    strategy: RemediationStrategy,
) -> tuple[RemediationProfileDefinition, ...]:
    strategy_id = strategy["strategy_id"]
    if (
        action_type == "sg_restrict_public_ports"
        and strategy_id == "sg_restrict_public_ports_guided"
    ):
        return _ec2_53_family_profiles()
    if action_type == "s3_bucket_block_public_access" and strategy_id == S3_2_STANDARD_STRATEGY_ID:
        return _s3_2_standard_family_profiles()
    if action_type == "s3_bucket_block_public_access" and strategy_id == S3_2_OAC_STRATEGY_ID:
        return _s3_2_oac_family_profiles()
    if action_type == "s3_bucket_require_ssl" and strategy_id in {
        S3_5_STRICT_STRATEGY_ID,
        S3_5_EXEMPTION_STRATEGY_ID,
    }:
        return _family_clone(action_type, strategy, family_kind=S3_5_FAMILY_RESOLVER_KIND)
    if action_type == "s3_bucket_lifecycle_configuration" and strategy_id == S3_11_STRATEGY_ID:
        return _family_clone(action_type, strategy, family_kind=S3_11_FAMILY_RESOLVER_KIND)
    return (_seed_profile_definition(action_type, strategy),)


def _build_action_profile_registry(
    action_type: str,
    strategies: tuple[RemediationStrategy, ...],
) -> StrategyProfileRegistry:
    return {
        strategy["strategy_id"]: _profile_rows_for_strategy(action_type, strategy)
        for strategy in strategies
    }


def build_profile_registry(
    strategy_registry: dict[str, tuple[RemediationStrategy, ...]] | None = None,
) -> ProfileRegistry:
    source_registry = STRATEGY_REGISTRY if strategy_registry is None else strategy_registry
    return {
        action_type: _build_action_profile_registry(action_type, strategies)
        for action_type, strategies in source_registry.items()
    }


PROFILE_REGISTRY: ProfileRegistry = build_profile_registry()


def _registry_for_action_type(action_type: str | None) -> StrategyProfileRegistry:
    normalized_action = _normalize_key(action_type)
    if normalized_action is None:
        return {}
    return PROFILE_REGISTRY.get(normalized_action, {})


def _profiles_for_strategy(
    action_type: str | None,
    strategy_id: str | None,
) -> tuple[RemediationProfileDefinition, ...]:
    normalized_strategy = _normalize_key(strategy_id)
    if normalized_strategy is None:
        return ()
    return _registry_for_action_type(action_type).get(normalized_strategy, ())


def list_profiles_for_action_type(action_type: str | None) -> list[RemediationProfileDefinition]:
    profiles: list[RemediationProfileDefinition] = []
    for strategy_profiles in _registry_for_action_type(action_type).values():
        profiles.extend(strategy_profiles)
    return profiles


def list_profiles_for_strategy(
    action_type: str | None,
    strategy_id: str | None,
) -> list[RemediationProfileDefinition]:
    return list(_profiles_for_strategy(action_type, strategy_id))


def get_profile_definition(
    action_type: str | None,
    strategy_id: str | None,
    profile_id: str | None,
) -> RemediationProfileDefinition | None:
    normalized_profile = _normalize_key(profile_id)
    if normalized_profile is None:
        return None
    for profile in _profiles_for_strategy(action_type, strategy_id):
        if profile.profile_id == normalized_profile:
            return profile
    return None


def default_profile_id_for_strategy(action_type: str | None, strategy_id: str | None) -> str | None:
    profiles = _profiles_for_strategy(action_type, strategy_id)
    if not profiles:
        return None
    return profiles[0].profile_id


def recommended_profile_id_for_strategy(
    action_type: str | None,
    strategy_id: str | None,
) -> str | None:
    profiles = _profiles_for_strategy(action_type, strategy_id)
    if not profiles:
        return None
    for profile in profiles:
        if profile.recommended:
            return profile.profile_id
    return profiles[0].profile_id


__all__ = [
    "PROFILE_REGISTRY",
    "ProfileRegistry",
    "RemediationProfileDefinition",
    "SupportTier",
    "build_profile_registry",
    "default_profile_id_for_strategy",
    "get_profile_definition",
    "list_profiles_for_action_type",
    "list_profiles_for_strategy",
    "recommended_profile_id_for_strategy",
]
