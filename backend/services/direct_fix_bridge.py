"""
Bridge helpers for optional direct-fix worker module imports.

Some API deployments package only backend modules (without the worker package).
These helpers prevent runtime import crashes and allow API routes to degrade
gracefully when direct-fix runtime code is unavailable.
"""
from __future__ import annotations

from typing import Any

DIRECT_FIX_OUT_OF_SCOPE_MESSAGE = (
    "Direct-fix execution and customer WriteRole are currently out of scope. "
    "Use PR bundle mode instead."
)


class DirectFixModuleUnavailable(RuntimeError):
    """Raised when direct-fix runtime module is not available in this image."""


def get_supported_direct_fix_action_types() -> frozenset[str]:
    """Direct-fix is intentionally disabled; active surfaces must stay PR-only."""
    return frozenset()


def run_remediation_preview_bridge(
    session: Any,
    action_type: str,
    account_id: str,
    region: str | None,
    strategy_id: str | None = None,
    strategy_inputs: dict[str, Any] | None = None,
) -> Any:
    """Direct-fix preview is intentionally disabled while the scope stays PR-only."""
    raise DirectFixModuleUnavailable(DIRECT_FIX_OUT_OF_SCOPE_MESSAGE)
