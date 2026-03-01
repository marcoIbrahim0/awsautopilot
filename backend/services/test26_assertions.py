"""Deterministic assertion helpers for Wave 7 Test 26 evidence summaries."""
from __future__ import annotations

import json
from typing import Any

_PAB_KEYS = (
    "BlockPublicAcls",
    "IgnorePublicAcls",
    "BlockPublicPolicy",
    "RestrictPublicBuckets",
)


def _normalize_statement(statement: dict[str, Any]) -> str:
    return json.dumps(statement, sort_keys=True, separators=(",", ":"))


def _is_cloudfront_statement(statement: dict[str, Any]) -> bool:
    sid = str(statement.get("Sid") or "").lower()
    if sid.startswith("allowcloudfront"):
        return True
    principal = statement.get("Principal")
    if not isinstance(principal, dict):
        return False
    service = principal.get("Service")
    if isinstance(service, str):
        return service == "cloudfront.amazonaws.com"
    if isinstance(service, list):
        return "cloudfront.amazonaws.com" in service
    return False


def build_precondition_risk_state(
    policy_doc: dict[str, Any],
    public_access_block_doc: dict[str, Any],
) -> dict[str, Any]:
    """Summarize deterministic adversarial-risk preconditions before open-visibility checks."""
    statements = list(policy_doc.get("Statement") or [])
    pab = (public_access_block_doc or {}).get("PublicAccessBlockConfiguration") or {}
    has_putobject_statement = any("s3:PutObject" in json.dumps(stmt) for stmt in statements)
    has_source_vpc_condition = any("aws:SourceVpc" in json.dumps(stmt) for stmt in statements)
    pab_all_false_confirmed = all(pab.get(key) is False for key in _PAB_KEYS)
    return {
        "statement_count": len(statements),
        "has_putobject_statement": has_putobject_statement,
        "has_source_vpc_condition": has_source_vpc_condition,
        "pab_all_false_confirmed": pab_all_false_confirmed,
        "adversarial_state_confirmed": (
            pab_all_false_confirmed
            and len(statements) >= 1
            and has_putobject_statement
            and has_source_vpc_condition
        ),
    }


def summarize_policy_preservation(
    policy_pre: dict[str, Any],
    policy_post: dict[str, Any],
    public_access_block_post_doc: dict[str, Any],
) -> dict[str, Any]:
    """Compare policy deltas and isolate CloudFront-only changes from non-risk statements."""
    pre_statements = list(policy_pre.get("Statement") or [])
    post_statements = list(policy_post.get("Statement") or [])
    pre_non_risk = {_normalize_statement(s) for s in pre_statements if not _is_cloudfront_statement(s)}
    post_non_risk = {_normalize_statement(s) for s in post_statements if not _is_cloudfront_statement(s)}
    pre_cloudfront = {_normalize_statement(s) for s in pre_statements if _is_cloudfront_statement(s)}
    post_cloudfront = {_normalize_statement(s) for s in post_statements if _is_cloudfront_statement(s)}
    pab_post = (public_access_block_post_doc or {}).get("PublicAccessBlockConfiguration") or {}
    removed_non_risk = pre_non_risk - post_non_risk
    added_non_risk = post_non_risk - pre_non_risk
    return {
        "removed_non_risk_statement_count": len(removed_non_risk),
        "added_non_risk_statement_count": len(added_non_risk),
        "removed_cloudfront_statement_count": len(pre_cloudfront - post_cloudfront),
        "added_cloudfront_statement_count": len(post_cloudfront - pre_cloudfront),
        "non_risk_invariance_pass": not removed_non_risk and not added_non_risk,
        "pab_hardened_post_apply": all(pab_post.get(key) is True for key in _PAB_KEYS),
    }


def evaluate_visibility_track(
    *,
    target_visible_in_open: bool,
    elapsed_seconds: int,
    sla_seconds: int,
) -> dict[str, Any]:
    """Evaluate Track 2 reopen visibility against SLA."""
    within_sla = elapsed_seconds <= sla_seconds
    passed = target_visible_in_open and within_sla
    if passed:
        reason = "target_visible_within_sla"
    elif not target_visible_in_open:
        reason = "target_not_visible_in_open_list"
    else:
        reason = "target_visible_after_sla"
    return {
        "pass": passed,
        "target_visible_in_open": target_visible_in_open,
        "elapsed_seconds": elapsed_seconds,
        "sla_seconds": sla_seconds,
        "reason": reason,
    }
