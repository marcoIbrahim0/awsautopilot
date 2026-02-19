"""
Bridge helpers for optional direct-fix worker module imports.

Some API deployments package only backend modules (without the worker package).
These helpers prevent runtime import crashes and allow API routes to degrade
gracefully when direct-fix runtime code is unavailable.
"""
from __future__ import annotations

from typing import Any


class DirectFixModuleUnavailable(RuntimeError):
    """Raised when direct-fix runtime module is not available in this image."""


def get_supported_direct_fix_action_types() -> frozenset[str]:
    """Best-effort list of direct-fix action types; empty when module unavailable."""
    try:
        from worker.services.direct_fix import SUPPORTED_ACTION_TYPES
    except ModuleNotFoundError:
        return frozenset()
    return frozenset(str(action_type) for action_type in SUPPORTED_ACTION_TYPES)


def run_remediation_preview_bridge(
    session: Any,
    action_type: str,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict[str, Any] | None = None,
) -> Any:
    """Run worker direct-fix preview or raise an explicit availability error."""
    try:
        from worker.services.direct_fix import run_remediation_preview
    except ModuleNotFoundError as exc:
        raise DirectFixModuleUnavailable(
            "Direct-fix preview runtime is not available in this API deployment."
        ) from exc
    return run_remediation_preview(
        session,
        action_type,
        account_id,
        region,
        strategy_id,
        strategy_inputs,
    )
