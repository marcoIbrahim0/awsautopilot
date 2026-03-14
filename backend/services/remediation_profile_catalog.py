"""
Wave 1 remediation profile catalog seeded from the public strategy catalog.

Profiles are an internal namespace beneath public strategies. Wave 1 keeps a
one-to-one compatibility mapping where `profile_id == strategy_id`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
    default_support_tier: SupportTier
    recommended: bool
    requires_inputs: bool
    supports_exception_flow: bool
    exception_only: bool


StrategyProfileRegistry = dict[str, tuple[RemediationProfileDefinition, ...]]
ProfileRegistry = dict[str, StrategyProfileRegistry]


def _normalize_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _default_support_tier(strategy: RemediationStrategy) -> SupportTier:
    # Wave 1 seeds compatibility rows only, so explicit exception paths are the
    # only strategies that default away from executable bundle semantics.
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
        default_support_tier=_default_support_tier(strategy),
        recommended=strategy["recommended"],
        requires_inputs=strategy["requires_inputs"],
        supports_exception_flow=strategy["supports_exception_flow"],
        exception_only=strategy["exception_only"],
    )


def _build_action_profile_registry(
    action_type: str,
    strategies: tuple[RemediationStrategy, ...],
) -> StrategyProfileRegistry:
    return {
        strategy["strategy_id"]: (_seed_profile_definition(action_type, strategy),)
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
