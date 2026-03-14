"""Pure remediation profile resolver contracts and compatibility helpers."""
from __future__ import annotations

import copy
from typing import Any, Literal, Mapping, TypedDict, cast

from typing_extensions import NotRequired

RESOLVER_DECISION_VERSION_V1 = "resolver/v1"

SupportTier = Literal[
    "deterministic_bundle",
    "review_required_bundle",
    "manual_guidance_only",
]

_SUPPORTED_SUPPORT_TIERS = {
    "deterministic_bundle",
    "review_required_bundle",
    "manual_guidance_only",
}


class ResolverRejectedProfile(TypedDict, total=False):
    """One rejected remediation profile candidate."""

    profile_id: str
    reason: str
    detail: NotRequired[str]


class ResolverDecisionInput(TypedDict, total=False):
    """Loose input payload for building a canonical resolver decision."""

    strategy_id: str
    profile_id: str
    support_tier: str
    resolved_inputs: dict[str, Any]
    missing_inputs: list[str]
    missing_defaults: list[str]
    blocked_reasons: list[str]
    rejected_profiles: list[ResolverRejectedProfile]
    finding_coverage: dict[str, Any]
    preservation_summary: dict[str, Any]
    decision_rationale: str
    decision_version: str


class ResolverDecision(TypedDict):
    """Canonical phase-1 resolver decision object."""

    strategy_id: str
    profile_id: str
    support_tier: SupportTier
    resolved_inputs: dict[str, Any]
    missing_inputs: list[str]
    missing_defaults: list[str]
    blocked_reasons: list[str]
    rejected_profiles: list[ResolverRejectedProfile]
    finding_coverage: dict[str, Any]
    preservation_summary: dict[str, Any]
    decision_rationale: str
    decision_version: str


def normalize_support_tier(value: Any) -> SupportTier:
    """Validate and normalize a support tier into the canonical enum."""
    if not isinstance(value, str):
        raise ValueError("support_tier must be a string.")
    normalized = value.strip().lower().replace("-", "_")
    if normalized not in _SUPPORTED_SUPPORT_TIERS:
        raise ValueError(f"Unsupported support_tier '{value}'.")
    return cast(SupportTier, normalized)


def default_profile_id(
    strategy_id: str,
    profile_id: Any,
    *,
    single_profile_compatible: bool = True,
) -> str:
    """Apply the phase-1 single-profile compatibility default."""
    normalized_strategy_id = _normalize_required_text(strategy_id, field_name="strategy_id")
    normalized_profile_id = _normalize_optional_text(profile_id, field_name="profile_id")
    if normalized_profile_id is not None:
        return normalized_profile_id
    if single_profile_compatible:
        return normalized_strategy_id
    raise ValueError("profile_id is required when single_profile_compatible is False.")


def resolve_decision_version(value: Any) -> str:
    """Return the canonical decision version when no explicit version is provided."""
    normalized = _normalize_optional_text(value, field_name="decision_version")
    if normalized is not None:
        return normalized
    return RESOLVER_DECISION_VERSION_V1


def normalize_resolution_decision(
    raw_decision: Mapping[str, Any],
    *,
    single_profile_compatible: bool = True,
) -> ResolverDecision:
    """Normalize a plain mapping into the canonical resolver decision schema."""
    strategy_id = _normalize_required_text(raw_decision.get("strategy_id"), field_name="strategy_id")
    return {
        **_normalize_scalar_fields(
            raw_decision,
            strategy_id=strategy_id,
            single_profile_compatible=single_profile_compatible,
        ),
        **_normalize_collection_fields(raw_decision),
    }


def build_compat_resolution_decision(
    *, strategy_id: str, support_tier: str, profile_id: str | None = None,
    resolved_inputs: Mapping[str, Any] | None = None, missing_inputs: list[str] | None = None,
    missing_defaults: list[str] | None = None, blocked_reasons: list[str] | None = None,
    rejected_profiles: list[ResolverRejectedProfile] | None = None,
    finding_coverage: Mapping[str, Any] | None = None,
    preservation_summary: Mapping[str, Any] | None = None,
    decision_rationale: str | None = None, decision_version: str | None = None,
) -> ResolverDecision:
    """Build a phase-1-compatible canonical decision from plain inputs."""
    return normalize_resolution_decision(
        _build_compat_input(
            strategy_id=strategy_id,
            support_tier=support_tier,
            profile_id=profile_id,
            resolved_inputs=resolved_inputs,
            missing_inputs=missing_inputs,
            missing_defaults=missing_defaults,
            blocked_reasons=blocked_reasons,
            rejected_profiles=rejected_profiles,
            finding_coverage=finding_coverage,
            preservation_summary=preservation_summary,
            decision_rationale=decision_rationale,
            decision_version=decision_version,
        ),
        single_profile_compatible=True,
    )


def _normalize_scalar_fields(
    raw_decision: Mapping[str, Any],
    *,
    strategy_id: str,
    single_profile_compatible: bool,
) -> dict[str, Any]:
    return {
        "strategy_id": strategy_id,
        "profile_id": default_profile_id(
            strategy_id,
            raw_decision.get("profile_id"),
            single_profile_compatible=single_profile_compatible,
        ),
        "support_tier": normalize_support_tier(raw_decision.get("support_tier")),
        "decision_rationale": _normalize_optional_text(
            raw_decision.get("decision_rationale"),
            field_name="decision_rationale",
        )
        or "",
        "decision_version": resolve_decision_version(raw_decision.get("decision_version")),
    }


def _normalize_collection_fields(raw_decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "resolved_inputs": _copy_mapping(raw_decision.get("resolved_inputs"), field_name="resolved_inputs"),
        "missing_inputs": _copy_string_list(raw_decision.get("missing_inputs"), field_name="missing_inputs"),
        "missing_defaults": _copy_string_list(
            raw_decision.get("missing_defaults"),
            field_name="missing_defaults",
        ),
        "blocked_reasons": _copy_string_list(
            raw_decision.get("blocked_reasons"),
            field_name="blocked_reasons",
        ),
        "rejected_profiles": _copy_rejected_profiles(raw_decision.get("rejected_profiles")),
        "finding_coverage": _copy_mapping(
            raw_decision.get("finding_coverage"),
            field_name="finding_coverage",
        ),
        "preservation_summary": _copy_mapping(
            raw_decision.get("preservation_summary"),
            field_name="preservation_summary",
        ),
    }


def _build_compat_input(
    *, strategy_id: str, support_tier: str, profile_id: str | None,
    resolved_inputs: Mapping[str, Any] | None,
    missing_inputs: list[str] | None, missing_defaults: list[str] | None,
    blocked_reasons: list[str] | None, rejected_profiles: list[ResolverRejectedProfile] | None,
    finding_coverage: Mapping[str, Any] | None, preservation_summary: Mapping[str, Any] | None,
    decision_rationale: str | None, decision_version: str | None,
) -> ResolverDecisionInput:
    raw_decision: ResolverDecisionInput = {
        "strategy_id": strategy_id,
        "support_tier": support_tier,
        "resolved_inputs": dict(resolved_inputs or {}),
        "missing_inputs": list(missing_inputs or []),
        "missing_defaults": list(missing_defaults or []),
        "blocked_reasons": list(blocked_reasons or []),
        "rejected_profiles": list(rejected_profiles or []),
        "finding_coverage": dict(finding_coverage or {}),
        "preservation_summary": dict(preservation_summary or {}),
        "decision_rationale": decision_rationale or "",
    }
    if profile_id is not None:
        raw_decision["profile_id"] = profile_id
    if decision_version is not None:
        raw_decision["decision_version"] = decision_version
    return raw_decision


def _normalize_required_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


def _normalize_optional_text(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when provided.")
    normalized = value.strip()
    if not normalized:
        return None
    return normalized


def _copy_mapping(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object.")
    return copy.deepcopy(dict(value))


def _copy_string_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be an array of strings.")
    if any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must contain only strings.")
    return list(copy.deepcopy(value))


def _copy_rejected_profiles(value: Any) -> list[ResolverRejectedProfile]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise ValueError("rejected_profiles must be an array of objects.")
    rejected: list[ResolverRejectedProfile] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("rejected_profiles must contain only objects.")
        rejected.append(cast(ResolverRejectedProfile, copy.deepcopy(dict(item))))
    return rejected
