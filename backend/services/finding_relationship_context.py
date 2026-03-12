"""Deterministic relationship-context enrichment for persisted findings."""
from __future__ import annotations

from typing import Any

from backend.services.canonicalization import build_resource_key

_RELATIONSHIP_CONTEXT_SOURCE = "canonical_finding_metadata"


def build_finding_relationship_context(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None = None,
) -> dict[str, Any]:
    account, region_name, resource, resource_kind, key = _normalized_context_values(
        account_id=account_id, region=region, resource_id=resource_id, resource_type=resource_type, resource_key=resource_key
    )
    scope, missing_fields = _relationship_state(
        account_id=account, region=region_name, resource_id=resource, resource_type=resource_kind, resource_key=key
    )
    return _relationship_context_payload(
        account_id=account,
        region=region_name,
        resource_id=resource,
        resource_type=resource_kind,
        resource_key=key,
        scope=scope,
        missing_fields=missing_fields,
    )


def _relationship_state(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
) -> tuple[str, list[str]]:
    scope = _scope_kind(account_id=account_id, resource_id=resource_id, resource_type=resource_type, resource_key=resource_key)
    missing_fields = _missing_fields(
        scope=scope,
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
        resource_key=resource_key,
    )
    return scope, missing_fields


def _normalized_context_values(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    account = _normalized_text(account_id)
    region_name = _normalized_text(region)
    resource = _normalized_text(resource_id)
    resource_kind = _normalized_text(resource_type)
    key = _resolved_resource_key(
        account_id=account,
        region=region_name,
        resource_id=resource,
        resource_type=resource_kind,
        resource_key=resource_key,
    )
    return account, region_name, resource, resource_kind, key


def enrich_finding_raw_json(
    raw_json: Any,
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None = None,
) -> dict[str, Any]:
    payload = dict(raw_json) if isinstance(raw_json, dict) else {}
    payload["relationship_context"] = build_finding_relationship_context(
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
        resource_key=resource_key,
    )
    return payload


def _relationship_context_payload(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
    scope: str,
    missing_fields: list[str],
) -> dict[str, Any]:
    complete = not missing_fields and scope != "unknown"
    return {
        "complete": complete,
        "confidence": 1.0 if complete else 0.0,
        "scope": scope,
        "source": _RELATIONSHIP_CONTEXT_SOURCE,
        "account_id": account_id,
        "region": region,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "resource_key": resource_key,
        "missing_fields": missing_fields,
    }


def _resolved_resource_key(
    *,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
) -> str | None:
    normalized_key = _normalized_text(resource_key)
    if normalized_key is not None:
        return normalized_key
    if account_id is None:
        return None
    return build_resource_key(
        account_id=account_id,
        region=region,
        resource_id=resource_id,
        resource_type=resource_type,
    )


def _scope_kind(
    *,
    account_id: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
) -> str:
    if resource_type == "AwsAccountRegion":
        return "account_region"
    if resource_type == "AwsAccount":
        return "account"
    if resource_id and account_id and resource_id == account_id:
        return "account"
    if resource_key and resource_key.startswith("account:") and ":region:" in resource_key:
        return "account_region"
    if resource_key and resource_key.startswith("account:"):
        return "account"
    if resource_id or resource_type or resource_key:
        return "resource"
    return "unknown"


def _missing_fields(
    *,
    scope: str,
    account_id: str | None,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
    resource_key: str | None,
) -> list[str]:
    fields = {
        "account_id": account_id,
        "region": region,
        "resource_id": resource_id,
        "resource_type": resource_type,
        "resource_key": resource_key,
    }
    required = _required_fields(scope)
    return [name for name in required if fields.get(name) is None]


def _required_fields(scope: str) -> tuple[str, ...]:
    if scope == "resource":
        return ("account_id", "resource_id", "resource_type", "resource_key")
    if scope == "account_region":
        return ("account_id", "region", "resource_type", "resource_key")
    if scope == "account":
        return ("account_id", "resource_type", "resource_key")
    return ("account_id", "resource_key")


def _normalized_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
