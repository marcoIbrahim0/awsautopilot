"""Wave 3 grouped remediation run helpers shared by both grouped entry points."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from backend.services.remediation_run_resolution import (
    RemediationRunResolutionError,
    build_single_run_resolution,
    resolve_create_profile_selection,
    resolve_create_profile_id,
)
from backend.services.remediation_profile_selection import resolve_runtime_probe_inputs
from backend.services.remediation_risk import (
    evaluate_strategy_impact,
    has_failing_checks,
    requires_risk_ack,
)
from backend.services.remediation_runtime_checks import collect_runtime_risk_signals
from backend.services.remediation_settings import normalize_remediation_settings
from backend.services.remediation_strategy import (
    RemediationStrategy,
    map_exception_strategy_inputs,
    map_legacy_variant_to_strategy,
    validate_strategy,
    validate_strategy_inputs,
)
from backend.utils.sqs import (
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1,
    REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2,
)


class GroupedRemediationRunValidationError(ValueError):
    """Raised when grouped remediation inputs cannot produce valid resolutions."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True, slots=True)
class GroupedActionScope:
    """Expected identity for the grouped action set supplied by the caller."""

    action_type: str
    account_id: str | None = None
    region: str | None = None
    status: str | None = None
    group_id: str | None = None
    group_key: str | None = None


@dataclass(frozen=True, slots=True)
class GroupedActionOverride:
    """One action-specific grouped override."""

    action_id: str
    strategy_id: str | None = None
    profile_id: str | None = None
    strategy_inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedGroupedRunRequest:
    """Shared grouped request shape used by both grouped entry points."""

    strategy_id: str | None = None
    strategy_inputs: dict[str, Any] | None = None
    action_overrides: tuple[GroupedActionOverride, ...] = ()
    repo_target: dict[str, Any] | None = None
    risk_acknowledged: bool = False
    pr_bundle_variant: str | None = None


@dataclass(frozen=True, slots=True)
class GroupedActionResolutionEntry:
    """One persisted per-action decision for a grouped run."""

    action_id: str
    strategy_id: str
    profile_id: str
    strategy_inputs: dict[str, Any]
    resolution: dict[str, Any]

    def to_artifact_payload(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "strategy_id": self.strategy_id,
            "profile_id": self.profile_id,
            "strategy_inputs": copy.deepcopy(self.strategy_inputs),
            "resolution": copy.deepcopy(self.resolution),
        }


@dataclass(frozen=True, slots=True)
class GroupedRunPersistencePlan:
    """Normalized grouped-run output ready for one-row persistence."""

    request: NormalizedGroupedRunRequest
    representative_action_id: str
    action_ids: tuple[str, ...]
    action_resolutions: tuple[GroupedActionResolutionEntry, ...]
    artifacts: dict[str, Any]

    def queue_payload_fields_for_schema(self, schema_version: int) -> dict[str, Any]:
        payload: dict[str, Any] = {"group_action_ids": list(self.action_ids)}
        _set_optional(payload, "pr_bundle_variant", self.request.pr_bundle_variant)
        _set_optional(payload, "strategy_id", self.request.strategy_id)
        _set_optional_mapping(payload, "strategy_inputs", self.request.strategy_inputs)
        _set_optional_mapping(payload, "repo_target", self.request.repo_target)
        if self.request.risk_acknowledged:
            payload["risk_acknowledged"] = True
        if schema_version == REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V2:
            payload["action_resolutions"] = [entry.to_artifact_payload() for entry in self.action_resolutions]
        elif schema_version != REMEDIATION_RUN_QUEUE_SCHEMA_VERSION_V1:
            raise ValueError(f"Unsupported remediation_run schema_version={schema_version}")
        return payload


@dataclass(frozen=True, slots=True)
class _ResolvedSelection:
    strategy: RemediationStrategy
    strategy_id: str
    strategy_inputs: dict[str, Any]
    requested_profile_id: str | None = None


def normalize_grouped_request_from_remediation_runs(raw_request: Any) -> NormalizedGroupedRunRequest:
    """Normalize the remediation-runs grouped request shape."""
    return _normalize_grouped_request(raw_request)


def normalize_grouped_request_from_action_group(raw_request: Any) -> NormalizedGroupedRunRequest:
    """Normalize the action-groups bundle-run request shape."""
    return _normalize_grouped_request(raw_request)


def build_grouped_run_persistence_plan(
    *,
    request: NormalizedGroupedRunRequest,
    scope: GroupedActionScope,
    actions: Sequence[Any],
    group_bundle_seed: Mapping[str, Any] | None = None,
    account: Any | None = None,
    tenant_settings: Mapping[str, Any] | None = None,
) -> GroupedRunPersistencePlan:
    """Build grouped artifacts and normalized queue-compatible mirrors."""
    sorted_actions = _validate_grouped_action_set(actions, scope=scope)
    default_strategy_id = _mapped_strategy_id(
        scope.action_type,
        request.strategy_id,
        request.pr_bundle_variant,
    )
    override_map = _resolve_override_map(
        request.action_overrides,
        sorted_actions,
        action_type=scope.action_type,
        tenant_settings=tenant_settings,
        default_strategy_id=default_strategy_id,
        default_strategy_inputs=request.strategy_inputs,
    )
    default_selection = _resolve_default_selection(
        request,
        sorted_actions,
        override_map,
        action_type=scope.action_type,
        tenant_settings=tenant_settings,
        default_strategy_id=default_strategy_id,
    )
    normalized_request = _normalized_request(request, default_selection)
    action_resolutions = _build_action_resolutions(
        sorted_actions,
        default_selection=default_selection,
        override_map=override_map,
        account=account,
        tenant_settings=tenant_settings,
        risk_acknowledged=normalized_request.risk_acknowledged,
    )
    artifacts = _build_grouped_artifacts(
        scope=scope,
        request=normalized_request,
        actions=sorted_actions,
        action_resolutions=action_resolutions,
        group_bundle_seed=group_bundle_seed,
    )
    return GroupedRunPersistencePlan(
        request=normalized_request,
        representative_action_id=_action_id(sorted_actions[0]),
        action_ids=tuple(_action_id(action) for action in sorted_actions),
        action_resolutions=action_resolutions,
        artifacts=artifacts,
    )


def _normalize_grouped_request(raw_request: Any) -> NormalizedGroupedRunRequest:
    return NormalizedGroupedRunRequest(
        strategy_id=_optional_text(_raw_field(raw_request, "strategy_id")),
        strategy_inputs=_normalize_optional_mapping(
            _raw_field(raw_request, "strategy_inputs"),
            field_name="strategy_inputs",
        ),
        action_overrides=_normalize_action_overrides(_raw_field(raw_request, "action_overrides")),
        repo_target=_normalize_repo_target(_raw_field(raw_request, "repo_target")),
        risk_acknowledged=_normalize_bool(_raw_field(raw_request, "risk_acknowledged")),
        pr_bundle_variant=_optional_text(_raw_field(raw_request, "pr_bundle_variant")),
    )


def _normalize_action_overrides(raw_overrides: Any) -> tuple[GroupedActionOverride, ...]:
    if raw_overrides is None:
        return ()
    if not isinstance(raw_overrides, (list, tuple)):
        raise GroupedRemediationRunValidationError(
            "invalid_action_overrides",
            "action_overrides must be an array of objects.",
        )
    return tuple(_normalize_action_override(item) for item in raw_overrides)


def _normalize_action_override(raw_override: Any) -> GroupedActionOverride:
    action_id = _required_text(_raw_field(raw_override, "action_id"), field_name="action_overrides[].action_id")
    return GroupedActionOverride(
        action_id=action_id,
        strategy_id=_optional_text(_raw_field(raw_override, "strategy_id")),
        profile_id=_optional_text(_raw_field(raw_override, "profile_id")),
        strategy_inputs=_normalize_optional_mapping(
            _raw_field(raw_override, "strategy_inputs"),
            field_name=f"action_overrides[{action_id}].strategy_inputs",
        )
        or {},
    )


def _normalize_repo_target(raw_repo_target: Any) -> dict[str, Any] | None:
    if raw_repo_target is None:
        return None
    repository = _required_text(_raw_field(raw_repo_target, "repository"), field_name="repo_target.repository")
    base_branch = _required_text(_raw_field(raw_repo_target, "base_branch"), field_name="repo_target.base_branch")
    normalized = {"repository": repository, "base_branch": base_branch}
    _set_optional(normalized, "provider", _optional_text(_raw_field(raw_repo_target, "provider")))
    _set_optional(normalized, "head_branch", _optional_text(_raw_field(raw_repo_target, "head_branch")))
    _set_optional(normalized, "root_path", _optional_text(_raw_field(raw_repo_target, "root_path")))
    return normalized


def _raw_field(raw_value: Any, field_name: str) -> Any:
    if raw_value is None:
        return None
    if isinstance(raw_value, Mapping):
        return raw_value.get(field_name)
    return getattr(raw_value, field_name, None)


def _normalize_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise GroupedRemediationRunValidationError(
        "invalid_boolean_field",
        "risk_acknowledged must be a boolean.",
    )


def _required_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GroupedRemediationRunValidationError(
            "invalid_text_field",
            f"{field_name} must be a non-empty string.",
        )
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise GroupedRemediationRunValidationError(
            "invalid_text_field",
            "Expected a string value.",
        )
    cleaned = value.strip()
    return cleaned or None


def _normalize_optional_mapping(value: Any, *, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise GroupedRemediationRunValidationError(
            "invalid_object_field",
            f"{field_name} must be an object.",
        )
    normalized = copy.deepcopy(dict(value))
    return normalized or None


def _validate_grouped_action_set(
    actions: Sequence[Any],
    *,
    scope: GroupedActionScope,
) -> tuple[Any, ...]:
    if not actions:
        raise GroupedRemediationRunValidationError("empty_grouped_action_set", "Grouped action set is empty.")
    sorted_actions = tuple(sorted(actions, key=_action_sort_key))
    for action in sorted_actions:
        _validate_grouped_action(action, scope=scope)
    return sorted_actions


def _validate_grouped_action(action: Any, *, scope: GroupedActionScope) -> None:
    expected = {
        "action_type": scope.action_type,
        "account_id": scope.account_id,
        "region": scope.region,
        "status": scope.status,
    }
    for field_name, expected_value in expected.items():
        if expected_value is None:
            continue
        if _action_field(action, field_name) != expected_value:
            raise GroupedRemediationRunValidationError(
                "grouped_action_set_mismatch",
                f"Action '{_action_id(action)}' does not belong to the expected grouped action set.",
                details={"field": field_name, "expected": expected_value, "action_id": _action_id(action)},
            )


def _resolve_override_map(
    overrides: Sequence[GroupedActionOverride],
    actions: Sequence[Any],
    *,
    action_type: str,
    tenant_settings: Mapping[str, Any] | None,
    default_strategy_id: str | None,
    default_strategy_inputs: Mapping[str, Any] | None,
) -> dict[str, _ResolvedSelection]:
    action_ids = {_action_id(action) for action in actions}
    override_map: dict[str, _ResolvedSelection] = {}
    for override in overrides:
        action_id = override.action_id
        if action_id in override_map:
            raise GroupedRemediationRunValidationError(
                "duplicate_action_override",
                f"Duplicate action override for action_id '{action_id}'.",
            )
        if action_id not in action_ids:
            raise GroupedRemediationRunValidationError(
                "override_action_not_in_group",
                f"action_id '{action_id}' is not part of this grouped action set.",
            )
        override_map[action_id] = _resolve_selection(
            action_type=action_type,
            strategy_id=_effective_override_strategy_id(
                override=override,
                default_strategy_id=default_strategy_id,
            ),
            profile_id=override.profile_id,
            strategy_inputs=_effective_override_strategy_inputs(
                override=override,
                default_strategy_id=default_strategy_id,
                default_strategy_inputs=default_strategy_inputs,
            ),
            tenant_settings=tenant_settings,
        )
    return override_map


def _resolve_default_selection(
    request: NormalizedGroupedRunRequest,
    actions: Sequence[Any],
    override_map: Mapping[str, _ResolvedSelection],
    *,
    action_type: str,
    tenant_settings: Mapping[str, Any] | None,
    default_strategy_id: str | None,
) -> _ResolvedSelection | None:
    if default_strategy_id is None:
        _ensure_every_action_overridden(actions, override_map, action_type=action_type)
        return None
    return _resolve_selection(
        action_type=action_type,
        strategy_id=default_strategy_id,
        profile_id=None,
        strategy_inputs=request.strategy_inputs,
        tenant_settings=tenant_settings,
    )


def _mapped_strategy_id(
    action_type: str,
    strategy_id: str | None,
    pr_bundle_variant: str | None,
) -> str | None:
    if pr_bundle_variant is None:
        return strategy_id
    mapped_strategy = map_legacy_variant_to_strategy(action_type, pr_bundle_variant)
    if mapped_strategy is None:
        raise GroupedRemediationRunValidationError(
            "invalid_pr_bundle_variant",
            f"Unsupported legacy pr_bundle_variant '{pr_bundle_variant}' for action_type '{action_type}'.",
        )
    if strategy_id and strategy_id != mapped_strategy:
        raise GroupedRemediationRunValidationError(
            "strategy_conflict",
            f"strategy_id '{strategy_id}' conflicts with legacy pr_bundle_variant mapping '{mapped_strategy}'.",
        )
    return mapped_strategy


def _ensure_every_action_overridden(
    actions: Sequence[Any],
    override_map: Mapping[str, _ResolvedSelection],
    *,
    action_type: str,
) -> None:
    missing_ids = [_action_id(action) for action in actions if _action_id(action) not in override_map]
    if not missing_ids:
        return
    raise GroupedRemediationRunValidationError(
        "missing_grouped_strategy_id",
        (
            f"strategy_id is required for grouped action_type '{action_type}' unless every action is "
            "covered by an explicit action_overrides entry."
        ),
        details={"action_ids_without_resolution": missing_ids},
    )


def _resolve_selection(
    *,
    action_type: str,
    strategy_id: str | None,
    profile_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
) -> _ResolvedSelection:
    if strategy_id is None:
        raise GroupedRemediationRunValidationError(
            "missing_override_strategy_id",
            "action_overrides[].strategy_id is required.",
        )
    strategy = _validated_strategy(action_type, strategy_id, strategy_inputs=strategy_inputs)
    try:
        normalized_inputs = validate_strategy_inputs(
            strategy,
            dict(strategy_inputs or {}),
            allow_missing_required_keys=_tenant_default_required_input_keys(strategy_id, tenant_settings),
        )
    except ValueError as exc:
        raise GroupedRemediationRunValidationError(
            "invalid_strategy_inputs",
            str(exc),
            details={"strategy_id": strategy_id},
        ) from exc
    resolved_profile_id = _validated_profile_id(action_type, strategy_id, profile_id)
    return _ResolvedSelection(
        strategy=strategy,
        strategy_id=strategy_id,
        strategy_inputs=normalized_inputs,
        requested_profile_id=resolved_profile_id,
    )


def _effective_override_strategy_id(
    *,
    override: GroupedActionOverride,
    default_strategy_id: str | None,
) -> str | None:
    return override.strategy_id or default_strategy_id


def _effective_override_strategy_inputs(
    *,
    override: GroupedActionOverride,
    default_strategy_id: str | None,
    default_strategy_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if override.strategy_id not in (None, default_strategy_id):
        return copy.deepcopy(dict(override.strategy_inputs))
    merged = copy.deepcopy(dict(default_strategy_inputs or {}))
    merged.update(copy.deepcopy(dict(override.strategy_inputs)))
    return merged


def _tenant_default_required_input_keys(
    strategy_id: str,
    tenant_settings: Mapping[str, Any] | None,
) -> set[str]:
    settings = normalize_remediation_settings(tenant_settings)
    if (
        strategy_id == "config_enable_centralized_delivery"
        and settings.get("config", {}).get("default_bucket_name")
    ):
        return {"delivery_bucket"}
    return set()


def _validated_strategy(
    action_type: str,
    strategy_id: str,
    *,
    strategy_inputs: Mapping[str, Any] | None,
) -> RemediationStrategy:
    try:
        strategy = validate_strategy(action_type, strategy_id, "pr_only")
    except ValueError as exc:
        raise GroupedRemediationRunValidationError(
            "invalid_override_strategy",
            str(exc),
        ) from exc
    if not strategy.get("exception_only"):
        return strategy
    raise GroupedRemediationRunValidationError(
        "exception_only_strategy",
        f"Selected strategy '{strategy_id}' is exception-only. Use Exception workflow instead of PR bundle.",
        details={"exception_flow": map_exception_strategy_inputs(dict(strategy_inputs or {}))},
    )


def _validated_profile_id(action_type: str, strategy_id: str, profile_id: str | None) -> str | None:
    if profile_id is None:
        return None
    try:
        return resolve_create_profile_id(action_type, strategy_id, profile_id)
    except RemediationRunResolutionError as exc:
        raise GroupedRemediationRunValidationError(
            "invalid_override_profile",
            str(exc),
        ) from exc


def _normalized_request(
    request: NormalizedGroupedRunRequest,
    default_selection: _ResolvedSelection | None,
) -> NormalizedGroupedRunRequest:
    if default_selection is None:
        return request
    return replace(
        request,
        strategy_id=default_selection.strategy_id,
        strategy_inputs=default_selection.strategy_inputs or None,
    )


def _build_action_resolutions(
    actions: Sequence[Any],
    *,
    default_selection: _ResolvedSelection | None,
    override_map: Mapping[str, _ResolvedSelection],
    account: Any | None,
    tenant_settings: Mapping[str, Any] | None,
    risk_acknowledged: bool,
) -> tuple[GroupedActionResolutionEntry, ...]:
    return tuple(
        _build_action_resolution(
            action,
            selection=_selection_for_action(action, default_selection, override_map),
            account=account,
            tenant_settings=tenant_settings,
            risk_acknowledged=risk_acknowledged,
        )
        for action in actions
    )


def _selection_for_action(
    action: Any,
    default_selection: _ResolvedSelection | None,
    override_map: Mapping[str, _ResolvedSelection],
) -> _ResolvedSelection:
    selection = override_map.get(_action_id(action), default_selection)
    if selection is not None:
        return selection
    raise GroupedRemediationRunValidationError(
        "missing_action_resolution",
        f"Action '{_action_id(action)}' has no grouped remediation selection.",
    )


def _build_action_resolution(
    action: Any,
    *,
    selection: _ResolvedSelection,
    account: Any | None,
    tenant_settings: Mapping[str, Any] | None,
    risk_acknowledged: bool,
) -> GroupedActionResolutionEntry:
    try:
        probe_inputs = resolve_runtime_probe_inputs(
            action_type=_action_field(action, "action_type"),
            strategy=selection.strategy,
            requested_profile_id=selection.requested_profile_id,
            explicit_inputs=selection.strategy_inputs,
            tenant_settings=tenant_settings,
            action=action,
        )
    except ValueError as exc:
        raise GroupedRemediationRunValidationError(
            "invalid_override_profile",
            str(exc),
        ) from exc
    runtime_signals = collect_runtime_risk_signals(
        action=action,
        strategy=selection.strategy,
        strategy_inputs=probe_inputs,
        account=account,
    )
    try:
        profile_selection = resolve_create_profile_selection(
            action_type=_action_field(action, "action_type"),
            strategy=selection.strategy,
            requested_profile_id=selection.requested_profile_id,
            explicit_inputs=selection.strategy_inputs,
            tenant_settings=tenant_settings,
            runtime_signals=runtime_signals,
            action=action,
        )
    except RemediationRunResolutionError as exc:
        raise GroupedRemediationRunValidationError(
            "invalid_override_profile",
            str(exc),
        ) from exc
    risk_snapshot = _risk_snapshot(
        action,
        selection=selection,
        strategy_inputs=profile_selection.persisted_strategy_inputs,
        runtime_signals=runtime_signals,
        account=account,
    )
    _validate_risk_snapshot(
        action,
        selection=selection,
        support_tier=profile_selection.support_tier,
        risk_snapshot=risk_snapshot,
        risk_acknowledged=risk_acknowledged,
    )
    resolution = build_single_run_resolution(
        strategy=selection.strategy,
        profile_selection=profile_selection,
        risk_snapshot=risk_snapshot,
        risk_acknowledged=risk_acknowledged,
        requested_profile_id=selection.requested_profile_id,
    )
    return GroupedActionResolutionEntry(
        action_id=_action_id(action),
        strategy_id=selection.strategy_id,
        profile_id=profile_selection.profile.profile_id,
        strategy_inputs=copy.deepcopy(profile_selection.persisted_strategy_inputs),
        resolution=copy.deepcopy(dict(resolution)),
    )


def _risk_snapshot(
    action: Any,
    *,
    selection: _ResolvedSelection,
    strategy_inputs: Mapping[str, Any] | None,
    runtime_signals: Mapping[str, Any] | None,
    account: Any | None,
) -> dict[str, Any]:
    return evaluate_strategy_impact(
        action,
        selection.strategy,
        strategy_inputs=strategy_inputs,
        account=account,
        runtime_signals=runtime_signals,
    )


def _validate_risk_snapshot(
    action: Any,
    *,
    selection: _ResolvedSelection,
    support_tier: str,
    risk_snapshot: Mapping[str, Any],
    risk_acknowledged: bool,
) -> None:
    checks = list(risk_snapshot.get("checks") or [])
    if has_failing_checks(checks) and support_tier == "deterministic_bundle":
        raise GroupedRemediationRunValidationError(
            "dependency_check_failed",
            (
                f"Action '{_action_id(action)}' blocked strategy '{selection.strategy_id}' "
                "because one or more dependency checks failed."
            ),
            details={"action_id": _action_id(action), "risk_snapshot": dict(risk_snapshot)},
        )
    if risk_acknowledged or not requires_risk_ack(checks):
        return
    raise GroupedRemediationRunValidationError(
        "risk_ack_required",
        (
            f"Action '{_action_id(action)}' requires risk_acknowledged=true for strategy "
            f"'{selection.strategy_id}'."
        ),
        details={"action_id": _action_id(action), "risk_snapshot": dict(risk_snapshot)},
    )


def _build_grouped_artifacts(
    *,
    scope: GroupedActionScope,
    request: NormalizedGroupedRunRequest,
    actions: Sequence[Any],
    action_resolutions: Sequence[GroupedActionResolutionEntry],
    group_bundle_seed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {
        "group_bundle": _build_group_bundle(
            scope=scope,
            actions=actions,
            action_resolutions=action_resolutions,
            group_bundle_seed=group_bundle_seed,
        )
    }
    _set_optional(artifacts, "selected_strategy", request.strategy_id)
    _set_optional(artifacts, "pr_bundle_variant", request.pr_bundle_variant)
    _set_optional_mapping(artifacts, "strategy_inputs", request.strategy_inputs)
    _set_optional_mapping(artifacts, "repo_target", request.repo_target)
    if request.risk_acknowledged:
        artifacts["risk_acknowledged"] = True
    return artifacts


def _build_group_bundle(
    *,
    scope: GroupedActionScope,
    actions: Sequence[Any],
    action_resolutions: Sequence[GroupedActionResolutionEntry],
    group_bundle_seed: Mapping[str, Any] | None,
) -> dict[str, Any]:
    group_bundle = copy.deepcopy(dict(group_bundle_seed or {}))
    _set_optional(group_bundle, "group_id", scope.group_id)
    _set_optional(group_bundle, "group_key", scope.group_key)
    group_bundle["action_type"] = scope.action_type
    _set_optional(group_bundle, "account_id", scope.account_id)
    group_bundle["region"] = scope.region
    _set_optional(group_bundle, "status", scope.status)
    group_bundle["action_count"] = len(actions)
    group_bundle["action_ids"] = [_action_id(action) for action in actions]
    group_bundle["action_resolutions"] = [entry.to_artifact_payload() for entry in action_resolutions]
    return group_bundle


def _set_optional(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _set_optional_mapping(payload: dict[str, Any], key: str, value: Mapping[str, Any] | None) -> None:
    if value:
        payload[key] = copy.deepcopy(dict(value))


def _action_sort_key(action: Any) -> tuple[int, float, float, str]:
    return (
        -_int_value(_action_field(action, "priority")),
        -_timestamp_value(_action_field(action, "updated_at")),
        -_timestamp_value(_action_field(action, "created_at")),
        _action_id(action),
    )


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _timestamp_value(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if value is None:
        return 0.0
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return 0.0


def _action_id(action: Any) -> str:
    return str(_action_field(action, "id"))


def _action_field(action: Any, field_name: str) -> Any:
    return getattr(action, field_name, None)


__all__ = [
    "GroupedActionOverride",
    "GroupedActionResolutionEntry",
    "GroupedActionScope",
    "GroupedRemediationRunValidationError",
    "GroupedRunPersistencePlan",
    "NormalizedGroupedRunRequest",
    "build_grouped_run_persistence_plan",
    "normalize_grouped_request_from_action_group",
    "normalize_grouped_request_from_remediation_runs",
]
