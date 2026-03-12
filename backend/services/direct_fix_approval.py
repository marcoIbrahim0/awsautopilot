"""Explicit approval-gate helpers for direct-fix execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import uuid


DIRECT_FIX_APPROVAL_ARTIFACT_KEY = "direct_fix_approval"
DIRECT_FIX_APPROVAL_KIND = "direct_fix_execute"
DIRECT_FIX_APPROVAL_PATH_API_CREATE = "api.remediation_runs.create_direct_fix"
ALLOWLISTED_DIRECT_FIX_APPROVAL_PATHS = frozenset({DIRECT_FIX_APPROVAL_PATH_API_CREATE})


@dataclass(frozen=True)
class DirectFixApprovalDecision:
    """Resolved approval-gate decision for a direct-fix execution request."""

    allowed: bool
    reason: str
    detail: str
    approval_path: str | None = None


def build_direct_fix_approval_metadata(
    *,
    approved_by_user_id: uuid.UUID | None,
    approval_path: str = DIRECT_FIX_APPROVAL_PATH_API_CREATE,
    approved_at: datetime | None = None,
) -> dict[str, str]:
    """Persist the explicit approval proof required for direct-fix execution."""
    stamp = approved_at or datetime.now(timezone.utc)
    return {
        "kind": DIRECT_FIX_APPROVAL_KIND,
        "mode": "direct_fix",
        "approval_path": approval_path,
        "approved_at": stamp.isoformat(),
        "approved_by_user_id": _normalize_token(approved_by_user_id),
    }


def evaluate_direct_fix_approval(run: Any, *, requested_mode: str) -> DirectFixApprovalDecision:
    """Fail closed unless the stored run carries an allowlisted direct-fix approval record."""
    if _normalize_token(requested_mode) != "direct_fix":
        return _reject("requested_mode_invalid", "Requested mode is not direct_fix.", None)
    if _run_mode(run) != "direct_fix":
        return _reject("run_mode_mismatch", "Stored remediation run mode is not direct_fix.", None)
    metadata = _approval_metadata(run)
    if not metadata:
        return _reject("missing_direct_fix_approval", "Run is missing direct-fix approval metadata.", None)
    if _normalize_token(metadata.get("kind")) != DIRECT_FIX_APPROVAL_KIND:
        return _reject("approval_kind_invalid", "Approval metadata kind is not valid for direct-fix execution.", None)
    if _normalize_token(metadata.get("mode")) != "direct_fix":
        return _reject("approval_mode_mismatch", "Approval metadata mode is not direct_fix.", None)
    approval_path = _normalize_token(metadata.get("approval_path"))
    if approval_path not in ALLOWLISTED_DIRECT_FIX_APPROVAL_PATHS:
        return _reject("approval_path_not_allowlisted", "Approval path is not in the direct-fix allowlist.", approval_path)
    if not _approver_matches(run, metadata):
        return _reject("approval_actor_mismatch", "Approval metadata does not match the stored approver.", approval_path)
    return DirectFixApprovalDecision(True, "approved", "Direct-fix approval gate passed.", approval_path)


def _approval_metadata(run: Any) -> dict[str, Any]:
    artifacts = getattr(run, "artifacts", None)
    if not isinstance(artifacts, dict):
        return {}
    payload = artifacts.get(DIRECT_FIX_APPROVAL_ARTIFACT_KEY)
    if not isinstance(payload, dict):
        return {}
    return payload


def _approver_matches(run: Any, metadata: dict[str, Any]) -> bool:
    metadata_user = _normalize_token(metadata.get("approved_by_user_id"))
    run_user = _normalize_token(getattr(run, "approved_by_user_id", None))
    if not metadata_user:
        return False
    if not run_user:
        return True
    return metadata_user == run_user


def _run_mode(run: Any) -> str:
    value = getattr(run, "mode", None)
    return _normalize_token(getattr(value, "value", value))


def _reject(reason: str, detail: str, approval_path: str | None) -> DirectFixApprovalDecision:
    return DirectFixApprovalDecision(False, reason, detail, approval_path)


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


__all__ = [
    "ALLOWLISTED_DIRECT_FIX_APPROVAL_PATHS",
    "DIRECT_FIX_APPROVAL_ARTIFACT_KEY",
    "DIRECT_FIX_APPROVAL_KIND",
    "DIRECT_FIX_APPROVAL_PATH_API_CREATE",
    "DirectFixApprovalDecision",
    "build_direct_fix_approval_metadata",
    "evaluate_direct_fix_approval",
]
