"""Deterministic action ownership resolution for owner-based queues."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

UNASSIGNED_OWNER_TYPE = "unassigned"
UNASSIGNED_OWNER_KEY = "unassigned"
UNASSIGNED_OWNER_LABEL = "Unassigned"

_USER_KEYS = ("owner_email", "owner_user", "assigned_to", "user", "email")
_TEAM_KEYS = ("team", "owner_team", "owning_team", "squad", "group")
_SERVICE_KEYS = ("service", "service_name", "application", "app", "system", "workload")
_AMBIGUOUS_OWNER_KEYS = ("owner",)

_ACTION_TYPE_SERVICE_FALLBACKS: dict[str, tuple[str, str]] = {
    "aws_config_enabled": ("config", "AWS Config"),
    "cloudtrail_enabled": ("cloudtrail", "AWS CloudTrail"),
    "ebs_default_encryption": ("ebs", "Amazon EBS"),
    "ebs_snapshot_block_public_access": ("ebs", "Amazon EBS"),
    "enable_guardduty": ("guardduty", "Amazon GuardDuty"),
    "enable_security_hub": ("securityhub", "AWS Security Hub"),
    "iam_root_access_key_absent": ("iam", "AWS IAM"),
    "s3_block_public_access": ("s3", "Amazon S3"),
    "s3_bucket_access_logging": ("s3", "Amazon S3"),
    "s3_bucket_block_public_access": ("s3", "Amazon S3"),
    "s3_bucket_encryption": ("s3", "Amazon S3"),
    "s3_bucket_encryption_kms": ("s3", "Amazon S3"),
    "s3_bucket_lifecycle_configuration": ("s3", "Amazon S3"),
    "s3_bucket_require_ssl": ("s3", "Amazon S3"),
    "sg_restrict_public_ports": ("ec2", "Amazon EC2"),
    "ssm_block_public_sharing": ("ssm", "AWS Systems Manager"),
}

_RESOURCE_TYPE_SERVICE_FALLBACKS: dict[str, tuple[str, str]] = {
    "AwsAccount": ("aws-account", "AWS Account"),
    "AwsEc2SecurityGroup": ("ec2", "Amazon EC2"),
    "AwsEksCluster": ("eks", "Amazon EKS"),
    "AwsIamAccessKey": ("iam", "AWS IAM"),
    "AwsIamUser": ("iam", "AWS IAM"),
    "AwsRdsDbInstance": ("rds", "Amazon RDS"),
    "AwsS3Bucket": ("s3", "Amazon S3"),
    "AwsSsmDocument": ("ssm", "AWS Systems Manager"),
}


@dataclass(frozen=True)
class ActionOwnerResolution:
    owner_type: str
    owner_key: str
    owner_label: str


def unassigned_owner() -> ActionOwnerResolution:
    return ActionOwnerResolution(
        owner_type=UNASSIGNED_OWNER_TYPE,
        owner_key=UNASSIGNED_OWNER_KEY,
        owner_label=UNASSIGNED_OWNER_LABEL,
    )


def resolve_action_owner(
    findings: list[Any],
    *,
    action_type: str | None,
    resource_type: str | None,
) -> ActionOwnerResolution:
    explicit = _explicit_owner_resolution(findings)
    if explicit is not None:
        return explicit
    derived = _derived_service_owner(action_type, resource_type)
    if derived is not None:
        return derived
    return unassigned_owner()


def normalize_owner_lookup_key(owner_key: str, owner_type: str | None = None) -> str:
    raw = (owner_key or "").strip()
    if not raw:
        return UNASSIGNED_OWNER_KEY
    normalized_type = (owner_type or "").strip().lower()
    if raw.lower() == UNASSIGNED_OWNER_KEY or normalized_type == UNASSIGNED_OWNER_TYPE:
        return UNASSIGNED_OWNER_KEY
    if normalized_type == "user" or "@" in raw:
        return raw.lower()
    return _slugify(raw)


def _explicit_owner_resolution(findings: list[Any]) -> ActionOwnerResolution | None:
    for owner_type in ("user", "team", "service"):
        resolution = _first_candidate(findings, owner_type)
        if resolution is not None:
            return resolution
    return None


def _first_candidate(findings: list[Any], owner_type: str) -> ActionOwnerResolution | None:
    for finding in findings:
        for source in _candidate_sources(finding):
            resolution = _candidate_from_source(source, owner_type)
            if resolution is not None:
                return resolution
    return None


def _candidate_sources(finding: Any) -> tuple[dict[str, str], ...]:
    raw = getattr(finding, "raw_json", None)
    if not isinstance(raw, dict):
        return ()
    sources: list[dict[str, str]] = []
    product_fields = _string_map(raw.get("ProductFields"))
    if product_fields:
        sources.append(product_fields)
    for resource in _list_of_dicts(raw.get("Resources")):
        sources.extend(_find_tag_maps(resource))
    return tuple(sources)


def _candidate_from_source(source: dict[str, str], owner_type: str) -> ActionOwnerResolution | None:
    value = _named_candidate_value(source, owner_type)
    if value:
        return _resolution(owner_type, value)
    return _ambiguous_owner_resolution(source, owner_type)


def _named_candidate_value(source: dict[str, str], owner_type: str) -> str | None:
    keys = _hint_keys_for_type(owner_type)
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return None


def _hint_keys_for_type(owner_type: str) -> tuple[str, ...]:
    if owner_type == "user":
        return _USER_KEYS
    if owner_type == "team":
        return _TEAM_KEYS
    return _SERVICE_KEYS


def _ambiguous_owner_resolution(source: dict[str, str], owner_type: str) -> ActionOwnerResolution | None:
    for key in _AMBIGUOUS_OWNER_KEYS:
        value = source.get(key)
        if not value:
            continue
        if owner_type == "user" and "@" in value:
            return _resolution("user", value)
        if owner_type == "team" and "@" not in value:
            return _resolution("team", value)
    return None


def _resolution(owner_type: str, raw_value: str) -> ActionOwnerResolution | None:
    label = _clean_label(raw_value)
    if not label:
        return None
    owner_key = normalize_owner_lookup_key(label, owner_type)
    if not owner_key:
        return None
    return ActionOwnerResolution(owner_type=owner_type, owner_key=owner_key, owner_label=label)


def _derived_service_owner(
    action_type: str | None,
    resource_type: str | None,
) -> ActionOwnerResolution | None:
    fallback = _ACTION_TYPE_SERVICE_FALLBACKS.get((action_type or "").strip().lower())
    if fallback is None:
        fallback = _RESOURCE_TYPE_SERVICE_FALLBACKS.get((resource_type or "").strip())
    if fallback is None:
        return None
    owner_key, owner_label = fallback
    return ActionOwnerResolution(owner_type="service", owner_key=owner_key, owner_label=owner_label)


def _find_tag_maps(node: Any) -> list[dict[str, str]]:
    if isinstance(node, list):
        maps: list[dict[str, str]] = []
        for item in node:
            maps.extend(_find_tag_maps(item))
        return maps
    if not isinstance(node, dict):
        return []
    maps: list[dict[str, str]] = []
    for key in sorted(node):
        value = node[key]
        if str(key).strip().lower() == "tags":
            tag_map = _string_map(value)
            if tag_map:
                maps.append(tag_map)
        maps.extend(_find_tag_maps(value))
    return maps


def _string_map(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return _normalized_text_map(value.items())
    if isinstance(value, list):
        return _tag_list_map(value)
    return {}


def _normalized_text_map(items: Any) -> dict[str, str]:
    output: dict[str, str] = {}
    for raw_key, raw_value in items:
        key = _clean_key(raw_key)
        value = _clean_label(raw_value)
        if key and value:
            output[key] = value
    return output


def _tag_list_map(values: list[Any]) -> dict[str, str]:
    items: list[tuple[Any, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        items.append((item.get("Key"), item.get("Value")))
    return _normalized_text_map(items)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _clean_key(value: Any) -> str:
    text = _clean_label(value)
    return _slugify(text).replace("-", "_")


def _clean_label(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9@._-]+", "-", lowered)
    return slug.strip("-")
