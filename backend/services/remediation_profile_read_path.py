"""Pure Wave 2 helpers for remediation profile options and preview metadata."""
from __future__ import annotations

from typing import Any, Mapping, TypedDict

from backend.services.remediation_profile_catalog import (
    RemediationProfileDefinition,
    get_profile_definition,
    list_profiles_for_strategy,
    recommended_profile_id_for_strategy,
)
from backend.services.remediation_profile_resolver import (
    ResolverDecision,
    build_compat_resolution_decision,
)
from backend.services.remediation_settings import normalize_remediation_settings
from backend.services.remediation_strategy import RemediationStrategy


class InvalidProfileSelection(ValueError):
    """Raised when a selected profile does not belong to the chosen strategy family."""


class RemediationProfileOptionPayload(TypedDict):
    """One additive compatibility-profile row nested beneath a strategy."""

    profile_id: str
    support_tier: str
    recommended: bool
    requires_inputs: bool
    supports_exception_flow: bool
    exception_only: bool


class RemediationStrategyProfileMetadata(TypedDict):
    """Additive remediation-options metadata derived from the Wave 1 catalog."""

    profiles: list[RemediationProfileOptionPayload]
    recommended_profile_id: str | None
    missing_defaults: list[str]
    blocked_reasons: list[str]
    decision_rationale: str


_TENANT_DEFAULT_INPUT_PATHS: dict[str, tuple[tuple[str, str], ...]] = {
    "config_enable_centralized_delivery": (
        ("delivery_bucket", "config.default_bucket_name"),
        ("existing_bucket_name", "config.default_bucket_name"),
        ("kms_key_arn", "config.default_kms_key_arn"),
    ),
    "s3_enable_access_logging_guided": (
        ("log_bucket_name", "s3_access_logs.default_target_bucket_name"),
    ),
    "s3_enable_sse_kms_guided": (
        ("kms_key_mode", "s3_encryption.mode"),
        ("kms_key_arn", "s3_encryption.kms_key_arn"),
    ),
}


def build_strategy_profile_metadata(
    *,
    action_type: str | None,
    strategy: RemediationStrategy,
    tenant_settings: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None,
    dependency_checks: list[Mapping[str, Any]] | None,
) -> RemediationStrategyProfileMetadata:
    """Build additive Wave 2 profile metadata for one remediation-options row."""
    strategy_id = strategy["strategy_id"]
    normalized_settings = normalize_remediation_settings(tenant_settings)
    profiles = _profile_payloads(action_type, strategy_id)
    blocked_reasons = _blocked_reasons(dependency_checks)
    missing_defaults = _missing_defaults(
        strategy=strategy,
        tenant_settings=normalized_settings,
        runtime_context=runtime_context,
        explicit_inputs=None,
    )
    return {
        "profiles": profiles,
        "recommended_profile_id": recommended_profile_id_for_strategy(action_type, strategy_id),
        "missing_defaults": missing_defaults,
        "blocked_reasons": blocked_reasons,
        "decision_rationale": _decision_rationale(
            strategy_id=strategy_id,
            profile_id=profiles[0]["profile_id"] if profiles else None,
            blocked_reasons=blocked_reasons,
            missing_defaults=missing_defaults,
            explicit_profile=False,
        ),
    }


def build_preview_resolution(
    *,
    action_type: str | None,
    strategy: RemediationStrategy | None,
    profile_id: str | None,
    strategy_inputs: Mapping[str, Any] | None,
    tenant_settings: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None,
    dependency_checks: list[Mapping[str, Any]] | None,
) -> ResolverDecision | None:
    """Return additive preview resolution metadata when a strategy family is known."""
    if strategy is None:
        return None
    normalized_settings = normalize_remediation_settings(tenant_settings)
    selected_profile = _select_profile(action_type, strategy["strategy_id"], profile_id)
    resolved_inputs = _resolved_inputs(
        strategy=strategy,
        tenant_settings=normalized_settings,
        runtime_context=runtime_context,
        explicit_inputs=strategy_inputs,
    )
    missing_inputs = _missing_inputs(strategy, resolved_inputs)
    missing_defaults = _missing_defaults(
        strategy=strategy,
        tenant_settings=normalized_settings,
        runtime_context=runtime_context,
        explicit_inputs=strategy_inputs,
    )
    blocked_reasons = _blocked_reasons(dependency_checks)
    return build_compat_resolution_decision(
        strategy_id=strategy["strategy_id"],
        profile_id=selected_profile.profile_id,
        support_tier=selected_profile.default_support_tier,
        resolved_inputs=resolved_inputs,
        missing_inputs=missing_inputs,
        missing_defaults=missing_defaults,
        blocked_reasons=blocked_reasons,
        preservation_summary={
            "single_profile_compatible": True,
            "strategy_only_supported": True,
        },
        decision_rationale=_decision_rationale(
            strategy_id=strategy["strategy_id"],
            profile_id=selected_profile.profile_id,
            blocked_reasons=blocked_reasons,
            missing_defaults=missing_defaults,
            explicit_profile=profile_id is not None,
        ),
    )


def _profile_payloads(
    action_type: str | None,
    strategy_id: str,
) -> list[RemediationProfileOptionPayload]:
    return [
        {
            "profile_id": profile.profile_id,
            "support_tier": profile.default_support_tier,
            "recommended": profile.recommended,
            "requires_inputs": profile.requires_inputs,
            "supports_exception_flow": profile.supports_exception_flow,
            "exception_only": profile.exception_only,
        }
        for profile in list_profiles_for_strategy(action_type, strategy_id)
    ]


def _select_profile(
    action_type: str | None,
    strategy_id: str,
    profile_id: str | None,
) -> RemediationProfileDefinition:
    selected_profile_id = profile_id or strategy_id
    profile = get_profile_definition(action_type, strategy_id, selected_profile_id)
    if profile is None:
        raise InvalidProfileSelection(
            f"profile_id '{selected_profile_id}' is not valid for strategy_id '{strategy_id}'."
        )
    return profile


def _missing_defaults(
    *,
    strategy: RemediationStrategy,
    tenant_settings: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None,
    explicit_inputs: Mapping[str, Any] | None,
) -> list[str]:
    resolved_inputs = _resolved_inputs(
        strategy=strategy,
        tenant_settings=tenant_settings,
        runtime_context=runtime_context,
        explicit_inputs=explicit_inputs,
    )
    missing: list[str] = []
    for input_key, settings_path in _TENANT_DEFAULT_INPUT_PATHS.get(strategy["strategy_id"], ()):
        if _present(resolved_inputs.get(input_key)):
            continue
        if not _field_required(strategy, input_key):
            continue
        missing.append(settings_path)
    return missing


def _resolved_inputs(
    *,
    strategy: RemediationStrategy,
    tenant_settings: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None,
    explicit_inputs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values = _schema_defaults(strategy)
    values.update(_runtime_default_inputs(runtime_context))
    values.update(_tenant_default_inputs(strategy["strategy_id"], tenant_settings))
    values.update(dict(explicit_inputs or {}))
    return {key: value for key, value in values.items() if _present(value)}


def _schema_defaults(strategy: RemediationStrategy) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in strategy["input_schema"].get("fields", []):
        default_value = field.get("default_value")
        if _present(default_value):
            values[field["key"]] = default_value
            continue
        safe_default = field.get("safe_default_value")
        if _concrete_safe_default(safe_default):
            values[field["key"]] = safe_default
    return values


def _runtime_default_inputs(runtime_context: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(runtime_context, Mapping):
        return {}
    default_inputs = runtime_context.get("default_inputs")
    return dict(default_inputs) if isinstance(default_inputs, Mapping) else {}


def _tenant_default_inputs(
    strategy_id: str,
    tenant_settings: Mapping[str, Any] | None,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for input_key, settings_path in _TENANT_DEFAULT_INPUT_PATHS.get(strategy_id, ()):
        raw_value = _settings_value(tenant_settings, settings_path)
        translated = _translate_setting_value(strategy_id, input_key, raw_value)
        if _present(translated):
            values[input_key] = translated
    return values


def _missing_inputs(strategy: RemediationStrategy, resolved_inputs: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in strategy["input_schema"].get("fields", []):
        if field["required"] and not _present(resolved_inputs.get(field["key"])):
            missing.append(field["key"])
    return missing


def _field_required(strategy: RemediationStrategy, input_key: str) -> bool:
    for field in strategy["input_schema"].get("fields", []):
        if field["key"] == input_key:
            return bool(field["required"])
    return False


def _settings_value(tenant_settings: Mapping[str, Any] | None, settings_path: str) -> Any:
    current: Any = tenant_settings or {}
    for segment in settings_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return current


def _translate_setting_value(strategy_id: str, input_key: str, value: Any) -> Any:
    if strategy_id != "s3_enable_sse_kms_guided" or input_key != "kms_key_mode":
        return value
    if value == "customer_managed":
        return "custom"
    return value


def _blocked_reasons(dependency_checks: list[Mapping[str, Any]] | None) -> list[str]:
    reasons: list[str] = []
    for check in dependency_checks or []:
        if check.get("status") != "fail":
            continue
        message = str(check.get("message") or check.get("code") or "").strip()
        if message and message not in reasons:
            reasons.append(message)
    return reasons


def _decision_rationale(
    *,
    strategy_id: str,
    profile_id: str | None,
    blocked_reasons: list[str],
    missing_defaults: list[str],
    explicit_profile: bool,
) -> str:
    if profile_id is None:
        return ""
    selection = "preserved the explicit profile" if explicit_profile else "defaulted to the single compatible profile"
    parts = [f"Wave 2 compatibility {selection} '{profile_id}' for strategy '{strategy_id}'."]
    if missing_defaults:
        parts.append(f"Missing tenant defaults: {', '.join(missing_defaults)}.")
    if blocked_reasons:
        parts.append(f"Blocking checks: {', '.join(blocked_reasons)}.")
    return " ".join(parts)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _concrete_safe_default(value: Any) -> bool:
    return isinstance(value, str) and value.strip() and "{{" not in value


__all__ = [
    "InvalidProfileSelection",
    "RemediationProfileOptionPayload",
    "RemediationStrategyProfileMetadata",
    "build_preview_resolution",
    "build_strategy_profile_metadata",
]
