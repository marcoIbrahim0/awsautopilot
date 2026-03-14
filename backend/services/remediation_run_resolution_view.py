"""Compatibility helpers for remediation-run detail resolution hydration."""
from __future__ import annotations

from typing import Any, Mapping

from backend.services.remediation_profile_resolver import (
    ResolverDecision,
    build_compat_resolution_decision,
    normalize_resolution_decision,
)


def build_run_detail_resolution(*, mode: str | None, artifacts: Any) -> ResolverDecision | None:
    safe_artifacts = _artifact_dict(artifacts)
    canonical = _canonical_resolution(safe_artifacts)
    if canonical is not None:
        return canonical
    return _compat_resolution(mode=mode, artifacts=safe_artifacts)


def _artifact_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _canonical_resolution(artifacts: Mapping[str, Any]) -> ResolverDecision | None:
    raw_resolution = artifacts.get("resolution")
    if not isinstance(raw_resolution, Mapping):
        return None
    try:
        return normalize_resolution_decision(raw_resolution)
    except ValueError:
        return None


def _compat_resolution(*, mode: str | None, artifacts: Mapping[str, Any]) -> ResolverDecision | None:
    if mode != "pr_only":
        return None
    strategy_id = _clean_text(artifacts.get("selected_strategy"))
    if strategy_id is None:
        return None
    support_tier = _compat_support_tier(artifacts)
    resolved_inputs = _resolved_inputs(artifacts.get("strategy_inputs"))
    return build_compat_resolution_decision(
        strategy_id=strategy_id,
        support_tier=support_tier,
        resolved_inputs=resolved_inputs,
        decision_rationale="Synthesized from legacy remediation run artifact mirrors.",
    )


def _compat_support_tier(artifacts: Mapping[str, Any]) -> str:
    if artifacts.get("risk_acknowledged") is True:
        return "review_required_bundle"
    return "deterministic_bundle"


def _resolved_inputs(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return dict(value)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


__all__ = ["build_run_detail_resolution"]
