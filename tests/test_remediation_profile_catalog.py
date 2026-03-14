from __future__ import annotations

import copy

from backend.services.remediation_profile_catalog import (
    PROFILE_REGISTRY,
    build_profile_registry,
    default_profile_id_for_strategy,
    get_profile_definition,
    list_profiles_for_action_type,
    list_profiles_for_strategy,
    recommended_profile_id_for_strategy,
)
from backend.services.remediation_strategy import STRATEGY_REGISTRY, RemediationStrategy


def _iter_strategy_rows() -> list[tuple[str, RemediationStrategy]]:
    rows: list[tuple[str, RemediationStrategy]] = []
    for action_type, strategies in STRATEGY_REGISTRY.items():
        for strategy in strategies:
            rows.append((action_type, strategy))
    return rows


def _expected_support_tier(strategy: RemediationStrategy) -> str:
    if strategy["exception_only"]:
        return "manual_guidance_only"
    return "deterministic_bundle"


def test_every_strategy_row_has_a_seeded_profile() -> None:
    assert set(PROFILE_REGISTRY) == set(STRATEGY_REGISTRY)
    for action_type, strategies in STRATEGY_REGISTRY.items():
        assert len(list_profiles_for_action_type(action_type)) == len(strategies)
        for strategy in strategies:
            profiles = list_profiles_for_strategy(action_type, strategy["strategy_id"])
            assert len(profiles) == 1
            profile = profiles[0]
            assert profile.action_type == action_type
            assert profile.strategy_id == strategy["strategy_id"]
            assert profile.default_support_tier == _expected_support_tier(strategy)
            assert profile.recommended is strategy["recommended"]
            assert profile.requires_inputs is strategy["requires_inputs"]
            assert profile.supports_exception_flow is strategy["supports_exception_flow"]
            assert profile.exception_only is strategy["exception_only"]


def test_wave1_seeded_profiles_use_strategy_ids_as_profile_ids() -> None:
    for action_type, strategy in _iter_strategy_rows():
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
        assert len(first_lookup) == 1
        profile = first_lookup[0]
        assert get_profile_definition(action_type, strategy_id, profile.profile_id) == profile
        assert default_profile_id_for_strategy(action_type, strategy_id) == profile.profile_id
        assert recommended_profile_id_for_strategy(action_type, strategy_id) == profile.profile_id


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
        profile = rebuilt_registry[action_type][strategy["strategy_id"]][0]
        assert profile.strategy_id == strategy["strategy_id"]
        assert profile.profile_id == strategy["strategy_id"]
