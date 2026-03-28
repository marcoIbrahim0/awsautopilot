"""Shared S3 lifecycle preservation analysis and Terraform rendering helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping, TypedDict


class S3LifecyclePreservationAnalysis(TypedDict):
    """Shared analysis result for resolver and bundle generation."""

    rule_count: int | None
    existing_document_captured: bool
    equivalent_safe_state: bool
    merge_renderable: bool
    render_failure_reason: str | None
    preserved_rules: list[dict[str, Any]]
    has_equivalent_abort_rule: bool


class LifecycleRenderError(ValueError):
    """Raised when a captured lifecycle document cannot be rendered safely."""


def analyze_lifecycle_preservation(
    lifecycle_json: str | None,
    *,
    abort_days: int,
) -> S3LifecyclePreservationAnalysis:
    parsed, parse_error = _parse_lifecycle_document(lifecycle_json)
    if parse_error is not None:
        return _invalid_analysis(parse_error)
    if parsed is None:
        return _empty_analysis(lifecycle_json)
    rules = _extract_rules(parsed)
    if rules is None:
        return _invalid_analysis("Captured lifecycle document is missing a valid Rules list.")
    if not rules:
        return _zero_rule_analysis()
    if _document_is_equivalent_safe_state(rules, abort_days=abort_days):
        return _equivalent_analysis(len(rules))
    return _merge_analysis(rules, abort_days=abort_days)


def lifecycle_rules_to_terraform(existing_rules: list[dict[str, Any]]) -> str:
    blocks = [_render_rule_block(rule) for rule in existing_rules]
    return "\n\n".join(blocks)


def rule_is_equivalent_abort_incomplete(rule: Any, *, abort_days: int) -> bool:
    if not isinstance(rule, Mapping):
        return False
    if _status_value(rule) != "enabled":
        return False
    if _rule_has_non_abort_actions(rule):
        return False
    if _abort_days(rule.get("AbortIncompleteMultipartUpload")) != abort_days:
        return False
    return _filter_is_equivalent_empty(rule)


def _empty_analysis(lifecycle_json: str | None) -> S3LifecyclePreservationAnalysis:
    return {
        "rule_count": None,
        "existing_document_captured": lifecycle_json is not None,
        "equivalent_safe_state": False,
        "merge_renderable": False,
        "render_failure_reason": None,
        "preserved_rules": [],
        "has_equivalent_abort_rule": False,
    }


def _invalid_analysis(reason: str) -> S3LifecyclePreservationAnalysis:
    analysis = _empty_analysis("captured")
    analysis["render_failure_reason"] = reason
    return analysis


def _zero_rule_analysis() -> S3LifecyclePreservationAnalysis:
    analysis = _empty_analysis("captured")
    analysis["rule_count"] = 0
    analysis["merge_renderable"] = True
    return analysis


def _equivalent_analysis(rule_count: int) -> S3LifecyclePreservationAnalysis:
    analysis = _empty_analysis("captured")
    analysis["rule_count"] = rule_count
    analysis["equivalent_safe_state"] = True
    analysis["merge_renderable"] = True
    analysis["has_equivalent_abort_rule"] = True
    return analysis


def _merge_analysis(
    rules: list[dict[str, Any]],
    *,
    abort_days: int,
) -> S3LifecyclePreservationAnalysis:
    preserved_rules = _remove_equivalent_abort_rules(rules, abort_days=abort_days)
    try:
        lifecycle_rules_to_terraform(preserved_rules)
    except LifecycleRenderError as exc:
        return _failed_merge_analysis(rules, preserved_rules, str(exc))
    return _successful_merge_analysis(rules, preserved_rules, abort_days=abort_days)


def _failed_merge_analysis(
    rules: list[dict[str, Any]],
    preserved_rules: list[dict[str, Any]],
    reason: str,
) -> S3LifecyclePreservationAnalysis:
    analysis = _empty_analysis("captured")
    analysis["rule_count"] = len(rules)
    analysis["preserved_rules"] = preserved_rules
    analysis["render_failure_reason"] = reason
    analysis["has_equivalent_abort_rule"] = len(preserved_rules) != len(rules)
    return analysis


def _successful_merge_analysis(
    rules: list[dict[str, Any]],
    preserved_rules: list[dict[str, Any]],
    *,
    abort_days: int,
) -> S3LifecyclePreservationAnalysis:
    analysis = _empty_analysis("captured")
    analysis["rule_count"] = len(rules)
    analysis["merge_renderable"] = True
    analysis["preserved_rules"] = preserved_rules
    analysis["has_equivalent_abort_rule"] = any(
        rule_is_equivalent_abort_incomplete(rule, abort_days=abort_days) for rule in rules
    )
    return analysis


def _parse_lifecycle_document(lifecycle_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if lifecycle_json is None:
        return None, None
    try:
        parsed = json.loads(lifecycle_json)
    except (TypeError, ValueError):
        return None, "Captured lifecycle document could not be parsed for additive merge."
    if isinstance(parsed, list):
        return {"Rules": parsed}, None
    if isinstance(parsed, dict):
        return parsed, None
    return None, "Captured lifecycle document is not a JSON object or list."


def _extract_rules(parsed: dict[str, Any]) -> list[dict[str, Any]] | None:
    rules = parsed.get("Rules")
    if rules is None:
        return []
    if not isinstance(rules, list):
        return None
    if not all(isinstance(rule, dict) for rule in rules):
        return None
    return [dict(rule) for rule in rules]


def _document_is_equivalent_safe_state(rules: list[dict[str, Any]], *, abort_days: int) -> bool:
    if len(rules) != 1:
        return False
    return rule_is_equivalent_abort_incomplete(rules[0], abort_days=abort_days)


def _remove_equivalent_abort_rules(
    rules: list[dict[str, Any]],
    *,
    abort_days: int,
) -> list[dict[str, Any]]:
    return [
        dict(rule)
        for rule in rules
        if not rule_is_equivalent_abort_incomplete(rule, abort_days=abort_days)
    ]


def _status_value(rule: Mapping[str, Any]) -> str:
    return str(rule.get("Status") or "").strip().lower()


def _rule_has_non_abort_actions(rule: Mapping[str, Any]) -> bool:
    return any(
        rule.get(field)
        for field in (
            "Expiration",
            "Transitions",
            "NoncurrentVersionExpiration",
            "NoncurrentVersionTransitions",
        )
    )


def _abort_days(block: Any) -> int | None:
    if not isinstance(block, Mapping):
        return None
    return _coerce_int(block.get("DaysAfterInitiation"))


def _filter_is_equivalent_empty(rule: Mapping[str, Any]) -> bool:
    if rule.get("Prefix") not in (None, ""):
        return False
    filter_value = rule.get("Filter")
    if filter_value is None:
        return True
    if not isinstance(filter_value, Mapping):
        return False
    if not filter_value:
        return True
    return filter_value.get("Prefix") == "" and len(filter_value) == 1


def _render_rule_block(rule: Mapping[str, Any]) -> str:
    _ensure_supported_rule_keys(rule)
    lines = _rule_opening_lines(rule)
    lines.extend(_render_filter(rule))
    lines.extend(_render_abort(rule))
    lines.extend(_render_expiration(rule))
    lines.extend(_render_transitions(rule))
    lines.extend(_render_noncurrent_expiration(rule))
    lines.extend(_render_noncurrent_transitions(rule))
    lines.append("  }")
    return "\n".join(lines)


def _rule_opening_lines(rule: Mapping[str, Any]) -> list[str]:
    rule_id = _string_value(rule.get("ID")) or _string_value(rule.get("Id")) or "preserved-rule"
    status = _string_value(rule.get("Status")) or "Enabled"
    return [
        "  rule {",
        f"    id     = {json.dumps(rule_id)}",
        f"    status = {json.dumps(status)}",
        "    # Preserved from captured lifecycle configuration.",
    ]


def _ensure_supported_rule_keys(rule: Mapping[str, Any]) -> None:
    allowed = {
        "ID",
        "Id",
        "Status",
        "Filter",
        "Prefix",
        "AbortIncompleteMultipartUpload",
        "Expiration",
        "Transitions",
        "NoncurrentVersionExpiration",
        "NoncurrentVersionTransitions",
    }
    _raise_unknown_keys(rule, allowed, "lifecycle rule")


def _render_filter(rule: Mapping[str, Any]) -> list[str]:
    filter_value = _rule_filter(rule)
    if filter_value == {}:
        return ["    filter {}"]
    if not isinstance(filter_value, Mapping):
        raise LifecycleRenderError("Captured lifecycle filter shape is unsupported for additive merge.")
    return _filter_lines(filter_value)


def _rule_filter(rule: Mapping[str, Any]) -> dict[str, Any]:
    filter_value = rule.get("Filter")
    if filter_value is None:
        prefix = _string_value(rule.get("Prefix"))
        return {} if prefix in (None, "") else {"Prefix": prefix}
    if isinstance(filter_value, Mapping):
        return dict(filter_value)
    raise LifecycleRenderError("Captured lifecycle filter shape is unsupported for additive merge.")


def _filter_lines(filter_value: Mapping[str, Any]) -> list[str]:
    _raise_unknown_keys(filter_value, {"Prefix", "Tag", "And", "ObjectSizeGreaterThan", "ObjectSizeLessThan"}, "lifecycle filter")
    if filter_value.get("And") is not None:
        return _filter_with_and(filter_value)
    if filter_value.get("Tag") is not None:
        return _filter_with_tag(filter_value)
    return _filter_with_scalars(filter_value)


def _filter_with_and(filter_value: Mapping[str, Any]) -> list[str]:
    if any(filter_value.get(key) is not None for key in ("Prefix", "Tag", "ObjectSizeGreaterThan", "ObjectSizeLessThan")):
        raise LifecycleRenderError("Lifecycle filter mixes And with sibling conditions; additive merge would be unsafe.")
    and_value = filter_value.get("And")
    if not isinstance(and_value, Mapping):
        raise LifecycleRenderError("Lifecycle filter And block is not a mapping.")
    lines = ["    filter {", "      and {"]
    lines.extend(_and_body_lines(and_value))
    lines.extend(["      }", "    }"])
    return lines


def _filter_with_tag(filter_value: Mapping[str, Any]) -> list[str]:
    if any(filter_value.get(key) is not None for key in ("Prefix", "ObjectSizeGreaterThan", "ObjectSizeLessThan")):
        raise LifecycleRenderError("Lifecycle filter mixes Tag with sibling conditions; additive merge would be unsafe.")
    tag_value = filter_value.get("Tag")
    tag = _single_tag_dict(tag_value)
    return [
        "    filter {",
        "      tag {",
        f"        key   = {json.dumps(tag['key'])}",
        f"        value = {json.dumps(tag['value'])}",
        "      }",
        "    }",
    ]


def _filter_with_scalars(filter_value: Mapping[str, Any]) -> list[str]:
    entries = _scalar_filter_entries(filter_value)
    if not entries:
        return ["    filter {}"]
    if len(entries) == 1:
        return ["    filter {", f"      {entries[0]}", "    }"]
    return ["    filter {", "      and {", *[f"        {entry}" for entry in entries], "      }", "    }"]


def _and_body_lines(and_value: Mapping[str, Any]) -> list[str]:
    _raise_unknown_keys(and_value, {"Prefix", "Tags", "ObjectSizeGreaterThan", "ObjectSizeLessThan"}, "lifecycle filter And block")
    lines = _scalar_filter_entries(and_value)
    tags_value = and_value.get("Tags")
    if tags_value is not None:
        lines.append(_tags_map_line(tags_value))
    if not lines:
        raise LifecycleRenderError("Lifecycle filter And block is empty; additive merge would be unsafe.")
    return [f"        {entry}" for entry in lines]


def _scalar_filter_entries(filter_value: Mapping[str, Any]) -> list[str]:
    entries: list[str] = []
    prefix = _string_value(filter_value.get("Prefix"))
    if prefix is not None:
        entries.append(f"prefix = {json.dumps(prefix)}")
    entries.extend(_object_size_entries(filter_value))
    return entries


def _object_size_entries(filter_value: Mapping[str, Any]) -> list[str]:
    entries: list[str] = []
    greater_than = _coerce_int(filter_value.get("ObjectSizeGreaterThan"))
    less_than = _coerce_int(filter_value.get("ObjectSizeLessThan"))
    if filter_value.get("ObjectSizeGreaterThan") is not None and greater_than is None:
        raise LifecycleRenderError("Lifecycle filter ObjectSizeGreaterThan must be an integer.")
    if filter_value.get("ObjectSizeLessThan") is not None and less_than is None:
        raise LifecycleRenderError("Lifecycle filter ObjectSizeLessThan must be an integer.")
    if greater_than is not None:
        entries.append(f"object_size_greater_than = {greater_than}")
    if less_than is not None:
        entries.append(f"object_size_less_than = {less_than}")
    return entries


def _render_abort(rule: Mapping[str, Any]) -> list[str]:
    block = rule.get("AbortIncompleteMultipartUpload")
    if block is None:
        return []
    days = _abort_days(block)
    if days is None:
        raise LifecycleRenderError("Lifecycle abort block is missing DaysAfterInitiation.")
    return [
        "    abort_incomplete_multipart_upload {",
        f"      days_after_initiation = {days}",
        "    }",
    ]


def _render_expiration(rule: Mapping[str, Any]) -> list[str]:
    block = rule.get("Expiration")
    if block is None:
        return []
    if not isinstance(block, Mapping):
        raise LifecycleRenderError("Lifecycle expiration block is not a mapping.")
    _raise_unknown_keys(block, {"Date", "Days", "ExpiredObjectDeleteMarker"}, "lifecycle expiration block")
    lines = _block_lines("expiration", _date_days_bool_entries(block, "ExpiredObjectDeleteMarker"))
    if lines is None:
        raise LifecycleRenderError("Lifecycle expiration block is empty.")
    return lines


def _render_transitions(rule: Mapping[str, Any]) -> list[str]:
    blocks = rule.get("Transitions")
    if blocks is None:
        return []
    if not isinstance(blocks, list):
        raise LifecycleRenderError("Lifecycle transitions block is not a list.")
    return [line for block in blocks for line in _transition_block_lines(block)]


def _transition_block_lines(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        raise LifecycleRenderError("Lifecycle transition entry is not a mapping.")
    _raise_unknown_keys(block, {"Date", "Days", "StorageClass"}, "lifecycle transition block")
    entries = _date_days_entries(block)
    storage_class = _string_value(block.get("StorageClass"))
    if storage_class is None:
        raise LifecycleRenderError("Lifecycle transition block is missing StorageClass.")
    entries.append(f"storage_class = {json.dumps(storage_class)}")
    return _required_block_lines("transition", entries, "Lifecycle transition block is empty.")


def _render_noncurrent_expiration(rule: Mapping[str, Any]) -> list[str]:
    block = rule.get("NoncurrentVersionExpiration")
    if block is None:
        return []
    if not isinstance(block, Mapping):
        raise LifecycleRenderError("Lifecycle noncurrent expiration block is not a mapping.")
    _raise_unknown_keys(block, {"NoncurrentDays", "NewerNoncurrentVersions"}, "lifecycle noncurrent expiration block")
    entries = _noncurrent_entries(block)
    return _required_block_lines(
        "noncurrent_version_expiration",
        entries,
        "Lifecycle noncurrent expiration block is empty.",
    )


def _render_noncurrent_transitions(rule: Mapping[str, Any]) -> list[str]:
    blocks = rule.get("NoncurrentVersionTransitions")
    if blocks is None:
        return []
    if not isinstance(blocks, list):
        raise LifecycleRenderError("Lifecycle noncurrent transitions block is not a list.")
    return [line for block in blocks for line in _noncurrent_transition_lines(block)]


def _noncurrent_transition_lines(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        raise LifecycleRenderError("Lifecycle noncurrent transition entry is not a mapping.")
    _raise_unknown_keys(
        block,
        {"NoncurrentDays", "NewerNoncurrentVersions", "StorageClass"},
        "lifecycle noncurrent transition block",
    )
    entries = _noncurrent_entries(block)
    storage_class = _string_value(block.get("StorageClass"))
    if storage_class is None:
        raise LifecycleRenderError("Lifecycle noncurrent transition block is missing StorageClass.")
    entries.append(f"storage_class = {json.dumps(storage_class)}")
    return _required_block_lines(
        "noncurrent_version_transition",
        entries,
        "Lifecycle noncurrent transition block is empty.",
    )


def _date_days_bool_entries(block: Mapping[str, Any], bool_key: str) -> list[str]:
    entries = _date_days_entries(block)
    if block.get(bool_key) is not None:
        bool_value = _coerce_bool(block.get(bool_key))
        if bool_value is None:
            raise LifecycleRenderError(f"Lifecycle block field {bool_key} must be a boolean.")
        entries.append(f"expired_object_delete_marker = {_bool_literal(bool_value)}")
    return entries


def _date_days_entries(block: Mapping[str, Any]) -> list[str]:
    entries: list[str] = []
    date_value = _string_value(block.get("Date"))
    if date_value is not None:
        entries.append(f"date = {json.dumps(date_value)}")
    days_value = _coerce_int(block.get("Days"))
    if block.get("Days") is not None and days_value is None:
        raise LifecycleRenderError("Lifecycle block Days field must be an integer.")
    if days_value is not None:
        entries.append(f"days = {days_value}")
    return entries


def _noncurrent_entries(block: Mapping[str, Any]) -> list[str]:
    entries: list[str] = []
    noncurrent_days = _coerce_int(block.get("NoncurrentDays"))
    newer_versions = _coerce_int(block.get("NewerNoncurrentVersions"))
    if block.get("NoncurrentDays") is not None and noncurrent_days is None:
        raise LifecycleRenderError("Lifecycle noncurrent block NoncurrentDays must be an integer.")
    if block.get("NewerNoncurrentVersions") is not None and newer_versions is None:
        raise LifecycleRenderError("Lifecycle noncurrent block NewerNoncurrentVersions must be an integer.")
    if noncurrent_days is not None:
        entries.append(f"noncurrent_days = {noncurrent_days}")
    if newer_versions is not None:
        entries.append(f"newer_noncurrent_versions = {newer_versions}")
    return entries


def _required_block_lines(block_name: str, entries: list[str], detail: str) -> list[str]:
    lines = _block_lines(block_name, entries)
    if lines is None:
        raise LifecycleRenderError(detail)
    return lines


def _block_lines(block_name: str, entries: list[str]) -> list[str] | None:
    if not entries:
        return None
    return [f"    {block_name} {{", *[f"      {entry}" for entry in entries], "    }"]


def _tags_map_line(tags_value: Any) -> str:
    tags = _tag_mapping(tags_value)
    if not tags:
        raise LifecycleRenderError("Lifecycle filter tags mapping is empty.")
    rendered = ", ".join(f"{json.dumps(key)} = {json.dumps(value)}" for key, value in sorted(tags.items()))
    return f"tags = {{{rendered}}}"


def _single_tag_dict(tag_value: Any) -> dict[str, str]:
    if not isinstance(tag_value, Mapping):
        raise LifecycleRenderError("Lifecycle filter Tag block is not a mapping.")
    _raise_unknown_keys(tag_value, {"Key", "Value"}, "lifecycle filter Tag block")
    key = _string_value(tag_value.get("Key"))
    value = _string_value(tag_value.get("Value"))
    if key is None or value is None:
        raise LifecycleRenderError("Lifecycle filter Tag block requires Key and Value.")
    return {"key": key, "value": value}


def _tag_mapping(tags_value: Any) -> dict[str, str]:
    if isinstance(tags_value, Mapping):
        return _tag_mapping_from_dict(tags_value)
    if isinstance(tags_value, list):
        return _tag_mapping_from_list(tags_value)
    raise LifecycleRenderError("Lifecycle filter tags shape is unsupported for additive merge.")


def _tag_mapping_from_dict(tags_value: Mapping[str, Any]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for key, value in tags_value.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise LifecycleRenderError("Lifecycle filter tags mapping must contain string pairs.")
        tags[key] = value
    return tags


def _tag_mapping_from_list(tags_value: list[Any]) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in tags_value:
        tag = _single_tag_dict(item)
        tags[tag["key"]] = tag["value"]
    return tags


def _raise_unknown_keys(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(key for key in value if key not in allowed)
    if unknown:
        raise LifecycleRenderError(f"Captured {label} uses unsupported fields: {', '.join(unknown)}.")


def _string_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in {"true", "1", "yes"}:
            return True
        if value.strip().lower() in {"false", "0", "no"}:
            return False
    return None


def _bool_literal(value: bool) -> str:
    return "true" if value else "false"
