from __future__ import annotations

from copy import deepcopy
from ipaddress import ip_network
from typing import Any, TypeVar


T = TypeVar("T")

ALLOWED_SG_ACCESS_PATH_PREFERENCES = {
    "close_public",
    "restrict_to_detected_public_ip",
    "restrict_to_approved_admin_cidr",
    "bastion_sg_reference",
    "ssm_only",
}

_DEFAULT_REMEDIATION_SETTINGS = {
    "sg_access_path_preference": None,
    "approved_admin_cidrs": [],
    "approved_bastion_security_group_ids": [],
    "cloudtrail": {
        "default_bucket_name": None,
        "default_kms_key_arn": None,
    },
    "config": {
        "delivery_mode": None,
        "default_bucket_name": None,
        "default_kms_key_arn": None,
    },
    "s3_access_logs": {
        "default_target_bucket_name": None,
    },
    "s3_encryption": {
        "mode": None,
        "kms_key_arn": None,
    },
}


class RemediationSettingsValidationError(ValueError):
    """Raised when remediation settings input is invalid."""


def default_remediation_settings() -> dict[str, Any]:
    return deepcopy(_DEFAULT_REMEDIATION_SETTINGS)


def normalize_remediation_settings(raw: Any) -> dict[str, Any]:
    return _coerce_settings(raw, strict=False)


def validate_remediation_settings(raw: Any) -> dict[str, Any]:
    return _coerce_settings(raw, strict=True)


def merge_remediation_settings(current: Any, patch: Any) -> dict[str, Any]:
    if not isinstance(patch, dict):
        raise RemediationSettingsValidationError("Request body must be a JSON object.")
    merged = normalize_remediation_settings(current)
    _merge_branch(merged, patch, _DEFAULT_REMEDIATION_SETTINGS)
    return validate_remediation_settings(merged)


def _coerce_settings(raw: Any, *, strict: bool) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return _error_or_default(strict, "Remediation settings must be a JSON object.", default_remediation_settings())
    if strict:
        _reject_unknown_keys(raw, _DEFAULT_REMEDIATION_SETTINGS)
    settings = default_remediation_settings()
    settings["sg_access_path_preference"] = _normalize_access_preference(raw.get("sg_access_path_preference"), strict)
    settings["approved_admin_cidrs"] = _normalize_cidrs(raw.get("approved_admin_cidrs"), strict)
    settings["approved_bastion_security_group_ids"] = _normalize_string_list(
        raw.get("approved_bastion_security_group_ids"),
        "approved_bastion_security_group_ids",
        strict,
    )
    settings["cloudtrail"] = _normalize_string_branch(raw.get("cloudtrail"), "cloudtrail", strict)
    settings["config"] = _normalize_string_branch(raw.get("config"), "config", strict)
    settings["s3_access_logs"] = _normalize_string_branch(raw.get("s3_access_logs"), "s3_access_logs", strict)
    settings["s3_encryption"] = _normalize_string_branch(raw.get("s3_encryption"), "s3_encryption", strict)
    return settings


def _merge_branch(current: dict[str, Any], patch: dict[str, Any], schema: dict[str, Any], path: str = "") -> None:
    for key, value in patch.items():
        if key not in schema:
            raise RemediationSettingsValidationError(f"Unknown remediation settings key: {_path(path, key)}")
        schema_value = schema[key]
        if isinstance(schema_value, dict):
            if value is None:
                current[key] = deepcopy(schema_value)
            elif isinstance(value, dict):
                _merge_branch(current[key], value, schema_value, _path(path, key))
            else:
                raise RemediationSettingsValidationError(f"{_path(path, key)} must be an object or null.")
            continue
        if isinstance(schema_value, list) and not isinstance(value, list):
            raise RemediationSettingsValidationError(f"{_path(path, key)} must be an array.")
        current[key] = value


def _reject_unknown_keys(raw: dict[str, Any], schema: dict[str, Any], path: str = "") -> None:
    for key in raw:
        if key in schema:
            continue
        raise RemediationSettingsValidationError(f"Unknown remediation settings key: {_path(path, key)}")


def _normalize_access_preference(value: Any, strict: bool) -> str | None:
    normalized = _normalize_optional_string(value, "sg_access_path_preference", strict)
    if normalized is None or normalized in ALLOWED_SG_ACCESS_PATH_PREFERENCES:
        return normalized
    return _error_or_default(
        strict,
        "sg_access_path_preference must be one of: "
        "close_public, restrict_to_detected_public_ip, restrict_to_approved_admin_cidr, "
        "bastion_sg_reference, ssm_only.",
        None,
    )


def _normalize_cidrs(value: Any, strict: bool) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return _error_or_default(strict, "approved_admin_cidrs must be an array.", [])
    normalized: list[str] = []
    for item in value:
        cidr = _normalize_required_string(item, "approved_admin_cidrs", strict)
        if cidr is None or "/" not in cidr:
            return _error_or_default(strict, "approved_admin_cidrs entries must be valid CIDR strings.", [])
        try:
            normalized.append(str(ip_network(cidr, strict=False)))
        except ValueError:
            return _error_or_default(strict, "approved_admin_cidrs entries must be valid CIDR strings.", [])
    return normalized


def _normalize_string_list(value: Any, path: str, strict: bool) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return _error_or_default(strict, f"{path} must be an array.", [])
    normalized: list[str] = []
    for item in value:
        text = _normalize_required_string(item, path, strict)
        if text is None:
            return []
        normalized.append(text)
    return normalized


def _normalize_string_branch(value: Any, branch: str, strict: bool) -> dict[str, str | None]:
    defaults = _DEFAULT_REMEDIATION_SETTINGS[branch]
    if value is None:
        return deepcopy(defaults)
    if not isinstance(value, dict):
        return _error_or_default(strict, f"{branch} must be an object or null.", deepcopy(defaults))
    if strict:
        _reject_unknown_keys(value, defaults, branch)
    normalized = deepcopy(defaults)
    for key in defaults:
        normalized[key] = _normalize_optional_string(value.get(key), _path(branch, key), strict)
    return normalized


def _normalize_optional_string(value: Any, path: str, strict: bool) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return _error_or_default(strict, f"{path} must be a string or null.", None)
    trimmed = value.strip()
    if trimmed:
        return trimmed
    return _error_or_default(strict, f"{path} must be a non-empty string or null.", None)


def _normalize_required_string(value: Any, path: str, strict: bool) -> str | None:
    if not isinstance(value, str):
        return _error_or_default(strict, f"{path} entries must be non-empty strings.", None)
    trimmed = value.strip()
    if trimmed:
        return trimmed
    return _error_or_default(strict, f"{path} entries must be non-empty strings.", None)


def _error_or_default(strict: bool, message: str, default: T) -> T:
    if strict:
        raise RemediationSettingsValidationError(message)
    return default


def _path(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key
