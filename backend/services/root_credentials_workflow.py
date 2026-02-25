"""
Shared helpers for root-credentials-required remediation workflows.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

ROOT_CREDENTIALS_REQUIRED_ACTION_TYPE = "iam_root_access_key_absent"
ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH = (
    "docs/prod-readiness/root-credentials-required-iam-root-access-key-absent.md"
)
ROOT_CREDENTIALS_REQUIRED_MESSAGE = (
    "Root credentials required. This remediation is manual/high-risk and must follow the runbook."
)
MANUAL_HIGH_RISK_MARKER = "MANUAL_HIGH_RISK_ROOT_CREDENTIALS_REQUIRED"


def is_root_credentials_required_action(action_type: str | None) -> bool:
    """Return True when action_type requires root credentials for execution."""
    if not isinstance(action_type, str):
        return False
    return action_type.strip().lower() == ROOT_CREDENTIALS_REQUIRED_ACTION_TYPE


def root_credentials_required_error_detail() -> dict[str, str]:
    """Structured API error payload for blocked SaaS execution attempts."""
    return {
        "error": "Root credentials required",
        "detail": (
            "Root credentials required. This remediation cannot run in SaaS executor mode. "
            f"Follow runbook: {ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH}."
        ),
        "runbook_url": ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
    }


def build_manual_high_risk_marker(
    *,
    approved_by_user_id: uuid.UUID | None,
    strategy_id: str | None,
    action_type: str | None = ROOT_CREDENTIALS_REQUIRED_ACTION_TYPE,
) -> dict[str, Any]:
    """Build marker payload persisted in remediation_runs.artifacts for auditability."""
    normalized_strategy = (strategy_id or "").strip()
    return {
        "marker": MANUAL_HIGH_RISK_MARKER,
        "message": ROOT_CREDENTIALS_REQUIRED_MESSAGE,
        "action_type": (action_type or ROOT_CREDENTIALS_REQUIRED_ACTION_TYPE).strip().lower(),
        "requires_root_credentials": True,
        "execution_path": "manual",
        "risk_level": "high",
        "runbook_url": ROOT_CREDENTIALS_REQUIRED_RUNBOOK_PATH,
        "approved_by_user_id": str(approved_by_user_id) if approved_by_user_id else "",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "strategy_id": normalized_strategy,
    }
