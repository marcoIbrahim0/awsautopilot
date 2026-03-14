"""Queue-contract helpers for remediation-run duplicate detection and resend reconstruction."""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from backend.services.remediation_profile_resolver import build_compat_resolution_decision
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
)


def normalize_single_run_request_signature(
    *,
    mode: str,
    strategy_id: str | None,
    profile_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    pr_bundle_variant: str | None,
    repo_target: Mapping[str, Any] | None,
) -> dict[str, Any]:
    mode_value = _normalized_text(mode) or ""
    strategy_value = _normalized_text(strategy_id)
    signature = {
        "mode": mode_value,
        "strategy_id": strategy_value,
        "strategy_inputs": _normalized_mapping(strategy_inputs),
        "pr_bundle_variant": _normalized_text(pr_bundle_variant),
        "repo_target": _normalized_mapping(repo_target),
    }
    if mode_value == "pr_only":
        signature["profile_id"] = _normalized_text(profile_id) or strategy_value
    return signature


def normalize_single_run_artifact_signature(
    *,
    mode: str,
    artifacts: Mapping[str, Any] | None,
) -> dict[str, Any]:
    artifacts_dict = _artifacts_dict(artifacts)
    resolution = _canonical_resolution(artifacts_dict.get("resolution"))
    strategy_id = _preferred_strategy_id(artifacts_dict, resolution)
    return normalize_single_run_request_signature(
        mode=mode,
        strategy_id=strategy_id,
        profile_id=_preferred_profile_id(mode=mode, strategy_id=strategy_id, resolution=resolution),
        strategy_inputs=_normalized_mapping(artifacts_dict.get("strategy_inputs")),
        pr_bundle_variant=_normalized_text(artifacts_dict.get("pr_bundle_variant")),
        repo_target=_normalized_mapping(artifacts_dict.get("repo_target")),
    )


def normalize_grouped_run_request_signature(
    *,
    group_key: str | None,
    strategy_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    pr_bundle_variant: str | None,
    repo_target: Mapping[str, Any] | None,
    action_resolutions: Sequence[Any] | None,
) -> dict[str, Any]:
    return {
        "group_key": _normalized_text(group_key),
        "strategy_id": _normalized_text(strategy_id),
        "strategy_inputs": _normalized_mapping(strategy_inputs),
        "pr_bundle_variant": _normalized_text(pr_bundle_variant),
        "repo_target": _normalized_mapping(repo_target),
        "action_resolutions": _action_resolution_signatures(action_resolutions),
    }


def normalize_grouped_run_artifact_signature(artifacts: Mapping[str, Any] | None) -> dict[str, Any]:
    artifacts_dict = _artifacts_dict(artifacts)
    group_bundle = _artifacts_dict(artifacts_dict.get("group_bundle"))
    return normalize_grouped_run_request_signature(
        group_key=_normalized_text(group_bundle.get("group_key")),
        strategy_id=_normalized_text(artifacts_dict.get("selected_strategy")),
        strategy_inputs=_normalized_mapping(artifacts_dict.get("strategy_inputs")),
        pr_bundle_variant=_normalized_text(artifacts_dict.get("pr_bundle_variant")),
        repo_target=_normalized_mapping(artifacts_dict.get("repo_target")),
        action_resolutions=_canonical_or_legacy_group_action_resolutions(artifacts_dict),
    )


def grouped_run_signatures_match(
    existing_signature: Mapping[str, Any],
    request_signature: Mapping[str, Any],
) -> bool:
    existing_resolutions = list(existing_signature.get("action_resolutions") or [])
    request_resolutions = list(request_signature.get("action_resolutions") or [])
    if existing_resolutions and request_resolutions:
        return _canonical_grouped_identity(existing_signature) == _canonical_grouped_identity(request_signature)
    return _legacy_grouped_signature_matches(existing_signature, request_signature)


def reconstruct_resend_queue_inputs(
    *,
    artifacts: Mapping[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    artifacts_dict = _artifacts_dict(artifacts)
    group_action_ids = _group_action_ids(artifacts_dict) or None
    canonical_resolution = _canonical_resolution(artifacts_dict.get("resolution"))
    canonical_action_resolutions = None
    resolution = None
    action_resolutions = None
    schema_version = REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1
    if _normalized_text(mode) == "pr_only":
        if group_action_ids:
            canonical_action_resolutions = _canonical_group_action_resolutions(artifacts_dict)
            action_resolutions = canonical_action_resolutions or _legacy_group_action_resolutions(artifacts_dict)
            if canonical_action_resolutions:
                schema_version = REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
        else:
            resolution = canonical_resolution or _canonical_or_legacy_single_resolution(artifacts_dict)
            if canonical_resolution is not None:
                schema_version = REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2
    return {
        "schema_version": schema_version,
        "pr_bundle_variant": _normalized_text(artifacts_dict.get("pr_bundle_variant")),
        "strategy_id": _preferred_strategy_id(artifacts_dict, resolution),
        "strategy_inputs": _normalized_mapping(artifacts_dict.get("strategy_inputs")),
        "risk_acknowledged": bool(artifacts_dict.get("risk_acknowledged")),
        "group_action_ids": group_action_ids,
        "repo_target": _normalized_mapping(artifacts_dict.get("repo_target")),
        "resolution": resolution,
        "action_resolutions": action_resolutions,
    }


def _canonical_grouped_identity(signature: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "group_key": signature.get("group_key"),
        "pr_bundle_variant": signature.get("pr_bundle_variant"),
        "repo_target": signature.get("repo_target"),
        "action_resolutions": list(signature.get("action_resolutions") or []),
    }


def _legacy_grouped_signature_matches(
    existing_signature: Mapping[str, Any],
    request_signature: Mapping[str, Any],
) -> bool:
    if _legacy_grouped_base(existing_signature) != _legacy_grouped_base(request_signature):
        return False
    if not _legacy_grouped_field_matches(existing_signature, request_signature, "strategy_id"):
        return False
    return _legacy_grouped_field_matches(existing_signature, request_signature, "strategy_inputs")


def _legacy_grouped_base(signature: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "group_key": signature.get("group_key"),
        "pr_bundle_variant": signature.get("pr_bundle_variant"),
        "repo_target": signature.get("repo_target"),
    }


def _legacy_grouped_field_matches(
    existing_signature: Mapping[str, Any],
    request_signature: Mapping[str, Any],
    field_name: str,
) -> bool:
    expected = existing_signature.get(field_name)
    return expected is None or expected == request_signature.get(field_name)


def _canonical_or_legacy_single_resolution(artifacts: Mapping[str, Any]) -> dict[str, Any] | None:
    canonical = _canonical_resolution(artifacts.get("resolution"))
    if canonical is not None:
        return canonical
    strategy_id = _normalized_text(artifacts.get("selected_strategy"))
    if strategy_id is None:
        return None
    return _build_compat_resolution(
        strategy_id=strategy_id,
        profile_id=strategy_id,
        strategy_inputs=_normalized_mapping(artifacts.get("strategy_inputs")) or {},
        risk_acknowledged=bool(artifacts.get("risk_acknowledged")),
    )


def _canonical_or_legacy_group_action_resolutions(
    artifacts: Mapping[str, Any],
) -> list[dict[str, Any]] | None:
    canonical = _canonical_group_action_resolutions(artifacts)
    if canonical:
        return canonical
    return _legacy_group_action_resolutions(artifacts)


def _canonical_group_action_resolutions(artifacts: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    group_bundle = _artifacts_dict(artifacts.get("group_bundle"))
    canonical = _normalized_action_resolution_payloads(
        group_bundle.get("action_resolutions"),
        risk_acknowledged=bool(artifacts.get("risk_acknowledged")),
    )
    return canonical or None


def _legacy_group_action_resolutions(artifacts: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    strategy_id = _normalized_text(artifacts.get("selected_strategy"))
    group_action_ids = _group_action_ids(artifacts)
    if strategy_id is None or not group_action_ids:
        return None
    strategy_inputs = _normalized_mapping(artifacts.get("strategy_inputs")) or {}
    resolution = _build_compat_resolution(
        strategy_id=strategy_id,
        profile_id=strategy_id,
        strategy_inputs=strategy_inputs,
        risk_acknowledged=bool(artifacts.get("risk_acknowledged")),
    )
    return [
        {
            "action_id": action_id,
            "strategy_id": strategy_id,
            "profile_id": strategy_id,
            "strategy_inputs": copy.deepcopy(strategy_inputs),
            "resolution": copy.deepcopy(resolution),
        }
        for action_id in group_action_ids
    ]


def _normalized_action_resolution_payloads(
    raw_entries: Sequence[Any] | None,
    *,
    risk_acknowledged: bool,
) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, (list, tuple)):
        return []
    entries = [
        entry
        for raw_entry in raw_entries
        if (entry := _normalized_action_resolution_payload(raw_entry, risk_acknowledged=risk_acknowledged))
        is not None
    ]
    return sorted(entries, key=lambda item: item["action_id"])


def _normalized_action_resolution_payload(
    raw_entry: Any,
    *,
    risk_acknowledged: bool,
) -> dict[str, Any] | None:
    action_id = _normalized_text(_field(raw_entry, "action_id"))
    strategy_id = _normalized_text(_field(raw_entry, "strategy_id"))
    if action_id is None or strategy_id is None:
        return None
    strategy_inputs = _normalized_mapping(_field(raw_entry, "strategy_inputs")) or {}
    profile_id = _normalized_text(_field(raw_entry, "profile_id")) or strategy_id
    resolution = _canonical_resolution(_field(raw_entry, "resolution")) or _build_compat_resolution(
        strategy_id=strategy_id,
        profile_id=profile_id,
        strategy_inputs=strategy_inputs,
        risk_acknowledged=risk_acknowledged,
    )
    return {
        "action_id": action_id,
        "strategy_id": strategy_id,
        "profile_id": profile_id,
        "strategy_inputs": copy.deepcopy(strategy_inputs),
        "resolution": resolution,
    }


def _action_resolution_signatures(raw_entries: Sequence[Any] | None) -> list[dict[str, Any]]:
    payloads = _normalized_action_resolution_payloads(raw_entries, risk_acknowledged=False)
    signatures = [_action_resolution_signature(payload) for payload in payloads]
    return sorted(signatures, key=lambda item: item["action_id"])


def _action_resolution_signature(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "action_id": payload.get("action_id"),
        "strategy_id": payload.get("strategy_id"),
        "profile_id": payload.get("profile_id"),
        "strategy_inputs": _normalized_mapping(payload.get("strategy_inputs")),
    }


def _group_action_ids(artifacts: Mapping[str, Any]) -> list[str]:
    group_bundle = _artifacts_dict(artifacts.get("group_bundle"))
    raw_ids = group_bundle.get("action_ids")
    if not isinstance(raw_ids, list):
        return []
    action_ids = [_normalized_text(raw_id) for raw_id in raw_ids]
    return [action_id for action_id in action_ids if action_id is not None]


def _preferred_strategy_id(
    artifacts: Mapping[str, Any],
    resolution: Mapping[str, Any] | None,
) -> str | None:
    if resolution is not None:
        strategy_id = _normalized_text(resolution.get("strategy_id"))
        if strategy_id is not None:
            return strategy_id
    return _normalized_text(artifacts.get("selected_strategy"))


def _preferred_profile_id(
    *,
    mode: str,
    strategy_id: str | None,
    resolution: Mapping[str, Any] | None,
) -> str | None:
    if _normalized_text(mode) != "pr_only":
        return None
    if resolution is not None:
        profile_id = _normalized_text(resolution.get("profile_id"))
        if profile_id is not None:
            return profile_id
    return strategy_id


def _build_compat_resolution(
    *,
    strategy_id: str,
    profile_id: str,
    strategy_inputs: Mapping[str, Any],
    risk_acknowledged: bool,
) -> dict[str, Any]:
    support_tier = "review_required_bundle" if risk_acknowledged else "deterministic_bundle"
    return build_compat_resolution_decision(
        strategy_id=strategy_id,
        profile_id=profile_id,
        support_tier=support_tier,
        resolved_inputs=strategy_inputs,
    )


def _canonical_resolution(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    strategy_id = _normalized_text(value.get("strategy_id"))
    if strategy_id is None:
        return None
    return copy.deepcopy(dict(value))


def _artifacts_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _normalized_mapping(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    normalized = copy.deepcopy(dict(value))
    return normalized or None


def _normalized_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _field(raw_value: Any, field_name: str) -> Any:
    if raw_value is None:
        return None
    if isinstance(raw_value, Mapping):
        return raw_value.get(field_name)
    return getattr(raw_value, field_name, None)


__all__ = [
    "grouped_run_signatures_match",
    "normalize_grouped_run_artifact_signature",
    "normalize_grouped_run_request_signature",
    "normalize_single_run_artifact_signature",
    "normalize_single_run_request_signature",
    "reconstruct_resend_queue_inputs",
]
