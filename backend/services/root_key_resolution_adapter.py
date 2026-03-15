"""IAM.4 metadata and authority helpers for generic remediation surfaces."""
from __future__ import annotations

from typing import Any, TypedDict

from backend.services.remediation_profile_resolver import SupportTier
from backend.services.root_credentials_workflow import ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH

ROOT_KEY_ACTION_TYPE = "iam_root_access_key_absent"
ROOT_KEY_EXECUTION_AUTHORITY_PATH = "/api/root-key-remediation-runs"
ROOT_KEY_FAMILY_RESOLVER_KIND = "iam_4_root_key_authority"
ROOT_KEY_GUIDANCE_SUPPORT_TIER: SupportTier = "manual_guidance_only"
ROOT_KEY_STRATEGY_IDS = {
    "iam_root_key_disable",
    "iam_root_key_delete",
    "iam_root_key_keep_exception",
}
ROOT_KEY_EXECUTION_AUTHORITY_REASON = (
    "IAM.4 execution is handled exclusively by /api/root-key-remediation-runs."
)
ROOT_KEY_GENERIC_ROUTE_ERROR = "Dedicated root-key route required"
ROOT_KEY_GENERIC_ROUTE_REASON = "root_key_execution_authority"


class RootKeyGuidanceMetadata(TypedDict):
    support_tier: SupportTier
    blocked_reasons: list[str]
    decision_rationale: str
    preservation_summary: dict[str, Any]


def is_root_key_action_type(action_type: str | None) -> bool:
    return isinstance(action_type, str) and action_type.strip().lower() == ROOT_KEY_ACTION_TYPE


def root_key_family_resolver_kind(action_type: str | None) -> str:
    if is_root_key_action_type(action_type):
        return ROOT_KEY_FAMILY_RESOLVER_KIND
    return "compatibility"


def root_key_default_support_tier(action_type: str | None) -> SupportTier | None:
    if not is_root_key_action_type(action_type):
        return None
    return ROOT_KEY_GUIDANCE_SUPPORT_TIER


def is_root_key_strategy_id(strategy_id: str | None) -> bool:
    return isinstance(strategy_id, str) and strategy_id.strip() in ROOT_KEY_STRATEGY_IDS


def build_root_key_guidance_metadata(
    *,
    strategy_id: str,
    blocked_reasons: list[str] | None = None,
) -> RootKeyGuidanceMetadata:
    reasons = _dedupe_strings([*(blocked_reasons or []), ROOT_KEY_EXECUTION_AUTHORITY_REASON])
    return {
        "support_tier": ROOT_KEY_GUIDANCE_SUPPORT_TIER,
        "blocked_reasons": reasons,
        "decision_rationale": _guidance_rationale(strategy_id),
        "preservation_summary": {
            "guidance_only": True,
            "generic_execution_allowed": False,
            "execution_authority": ROOT_KEY_EXECUTION_AUTHORITY_PATH,
            "runbook_url": ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
        },
    }


def build_root_key_execution_authority_error(*, strategy_id: str | None = None) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "error": ROOT_KEY_GENERIC_ROUTE_ERROR,
        "reason": ROOT_KEY_GENERIC_ROUTE_REASON,
        "detail": (
            "IAM.4 execution is handled exclusively by /api/root-key-remediation-runs. "
            "Generic remediation-run routes expose IAM.4 guidance only."
        ),
        "execution_authority": ROOT_KEY_EXECUTION_AUTHORITY_PATH,
        "runbook_url": ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    }
    if isinstance(strategy_id, str) and strategy_id.strip():
        detail["strategy_id"] = strategy_id.strip()
    return detail


def _guidance_rationale(strategy_id: str) -> str:
    return (
        f"IAM.4 strategy '{strategy_id}' is exposed here as metadata only. "
        f"Use {ROOT_KEY_EXECUTION_AUTHORITY_PATH} for root-key lifecycle execution."
    )


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return deduped
