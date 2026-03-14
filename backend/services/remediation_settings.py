from __future__ import annotations

from copy import deepcopy
from ipaddress import ip_network
from typing import Any, Mapping, TypeVar

T = TypeVar("T")


SG_ACCESS_PATH_PREFERENCES = (
    "close_public",
    "restrict_to_detected_public_ip",
    "restrict_to_approved_admin_cidr",
    "bastion_sg_reference",
    "ssm_only",
)
CONFIG_DELIVERY_MODES = ("account_local_delivery", "centralized_delivery")
S3_ENCRYPTION_MODES = ("aws_managed", "customer_managed")

_DEFAULT_REMEDIATION_SETTINGS = {
    "sg_access_path_preference": None,
    "approved_bastion_security_group_ids": [],
    "approved_admin_cidrs": [],
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
    return _normalize_settings(raw, strict=False)


def merge_remediation_settings(current: Any, patch: Any) -> dict[str, Any]:
    if not isinstance(patch, Mapping):
        raise RemediationSettingsValidationError("Request body must be a JSON object.")
    merged = _deep_merge(normalize_remediation_settings(current), patch)
    return _normalize_settings(merged, strict=True)


def _normalize_settings(raw: Any, *, strict: bool) -> dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        return _error_or_default(
            strict,
            "Remediation settings must be a JSON object.",
            default_remediation_settings(),
        )
    _reject_unknown_keys(raw, _DEFAULT_REMEDIATION_SETTINGS, field_name="remediation_settings", strict=strict)
    return {
        "sg_access_path_preference": _normalize_optional_enum(
            raw.get("sg_access_path_preference"),
            field_name="sg_access_path_preference",
            allowed_values=SG_ACCESS_PATH_PREFERENCES,
            strict=strict,
        ),
        "approved_bastion_security_group_ids": _normalize_string_list(
            raw.get("approved_bastion_security_group_ids"),
            field_name="approved_bastion_security_group_ids",
            strict=strict,
        ),
        "approved_admin_cidrs": _normalize_cidrs(
            raw.get("approved_admin_cidrs"),
            field_name="approved_admin_cidrs",
            strict=strict,
        ),
        "cloudtrail": _normalize_cloudtrail(raw.get("cloudtrail"), strict=strict),
        "config": _normalize_config(raw.get("config"), strict=strict),
        "s3_access_logs": _normalize_s3_access_logs(raw.get("s3_access_logs"), strict=strict),
        "s3_encryption": _normalize_s3_encryption(raw.get("s3_encryption"), strict=strict),
    }


def _normalize_cloudtrail(value: Any, *, strict: bool) -> dict[str, str | None]:
    branch = _normalize_branch(
        value,
        branch_name="cloudtrail",
        strict=strict,
    )
    return {
        "default_bucket_name": _normalize_optional_text(
            branch.get("default_bucket_name"),
            field_name="cloudtrail.default_bucket_name",
            strict=strict,
        ),
        "default_kms_key_arn": _normalize_optional_text(
            branch.get("default_kms_key_arn"),
            field_name="cloudtrail.default_kms_key_arn",
            strict=strict,
        ),
    }


def _normalize_config(value: Any, *, strict: bool) -> dict[str, str | None]:
    branch = _normalize_branch(
        value,
        branch_name="config",
        strict=strict,
    )
    return {
        "delivery_mode": _normalize_optional_enum(
            branch.get("delivery_mode"),
            field_name="config.delivery_mode",
            allowed_values=CONFIG_DELIVERY_MODES,
            strict=strict,
        ),
        "default_bucket_name": _normalize_optional_text(
            branch.get("default_bucket_name"),
            field_name="config.default_bucket_name",
            strict=strict,
        ),
        "default_kms_key_arn": _normalize_optional_text(
            branch.get("default_kms_key_arn"),
            field_name="config.default_kms_key_arn",
            strict=strict,
        ),
    }


def _normalize_s3_access_logs(value: Any, *, strict: bool) -> dict[str, str | None]:
    branch = _normalize_branch(
        value,
        branch_name="s3_access_logs",
        strict=strict,
    )
    return {
        "default_target_bucket_name": _normalize_optional_text(
            branch.get("default_target_bucket_name"),
            field_name="s3_access_logs.default_target_bucket_name",
            strict=strict,
        )
    }


def _normalize_s3_encryption(value: Any, *, strict: bool) -> dict[str, str | None]:
    branch = _normalize_branch(
        value,
        branch_name="s3_encryption",
        strict=strict,
    )
    return {
        "mode": _normalize_optional_enum(
            branch.get("mode"),
            field_name="s3_encryption.mode",
            allowed_values=S3_ENCRYPTION_MODES,
            strict=strict,
        ),
        "kms_key_arn": _normalize_optional_text(
            branch.get("kms_key_arn"),
            field_name="s3_encryption.kms_key_arn",
            strict=strict,
        ),
    }


def _normalize_branch(
    value: Any,
    *,
    branch_name: str,
    strict: bool,
) -> dict[str, Any]:
    defaults = deepcopy(_DEFAULT_REMEDIATION_SETTINGS[branch_name])
    if value is None:
        return defaults
    if not isinstance(value, Mapping):
        return _error_or_default(
            strict,
            f"{branch_name} must be an object or null.",
            defaults,
        )
    _reject_unknown_keys(value, defaults, field_name=branch_name, strict=strict)
    return dict(value)


def _reject_unknown_keys(
    value: Mapping[str, Any],
    allowed_shape: Mapping[str, Any],
    *,
    field_name: str,
    strict: bool,
) -> None:
    unknown_keys = [key for key in value if key not in allowed_shape]
    if not unknown_keys and strict:
        return
    if not unknown_keys:
        return
    message = f"Unknown remediation settings key: {field_name}.{unknown_keys[0]}"
    _error_or_default(strict, message, None)


def _normalize_optional_enum(
    value: Any,
    *,
    field_name: str,
    allowed_values: tuple[str, ...],
    strict: bool,
) -> str | None:
    normalized = _normalize_optional_text(value, field_name=field_name, strict=strict)
    if normalized is None or normalized in allowed_values:
        return normalized
    joined_values = ", ".join(allowed_values)
    return _error_or_default(
        strict,
        f"{field_name} must be one of: {joined_values}.",
        None,
    )


def _normalize_optional_text(value: Any, *, field_name: str, strict: bool) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return _error_or_default(strict, f"{field_name} must be a string or null.", None)
    normalized = value.strip()
    if normalized:
        return normalized
    return _error_or_default(
        strict,
        f"{field_name} must be a non-empty string or null.",
        None,
    )


def _normalize_string_list(value: Any, *, field_name: str, strict: bool) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return _error_or_default(strict, f"{field_name} must be an array.", [])
    normalized_items: list[str] = []
    for item in value:
        normalized = _normalize_optional_text(item, field_name=field_name, strict=strict)
        if normalized is None:
            return _error_or_default(
                strict,
                f"{field_name} entries must be non-empty strings.",
                [],
            )
        normalized_items.append(normalized)
    return normalized_items


def _normalize_cidrs(value: Any, *, field_name: str, strict: bool) -> list[str]:
    normalized_items = _normalize_string_list(value, field_name=field_name, strict=strict)
    cidrs: list[str] = []
    for cidr in normalized_items:
        try:
            cidrs.append(str(ip_network(cidr, strict=False)))
        except ValueError:
            return _error_or_default(
                strict,
                f"{field_name} entries must be valid CIDR strings.",
                [],
            )
    return cidrs


def _deep_merge(current: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(current)
    for key, value in patch.items():
        merged[key] = _merged_value(merged.get(key), value)
    return merged


def _merged_value(current: Any, patch_value: Any) -> Any:
    if isinstance(current, Mapping) and isinstance(patch_value, Mapping):
        return _deep_merge(dict(current), patch_value)
    return deepcopy(patch_value)


def _error_or_default(strict: bool, message: str, default: T) -> T:
    if strict:
        raise RemediationSettingsValidationError(message)
    return default
