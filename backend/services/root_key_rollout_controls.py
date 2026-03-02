from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass

from backend.config import settings

_AWS_ACCESS_KEY_PATTERN = re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{16}\b")
_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(password|secret|token|session[_-]?key|access[_-]?key)\b\s*[:=]\s*\S+"
)
_PRIVATE_KEY_PATTERN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)


@dataclass(frozen=True)
class RootKeyCanaryDecision:
    allowed: bool
    reason: str
    bucket: int | None
    percent: int
    matched_allowlist: bool


def evaluate_root_key_canary(
    *,
    tenant_id: uuid.UUID,
    account_id: str,
    enabled: bool | None = None,
    percent: int | None = None,
    tenant_allowlist: set[str] | None = None,
    account_allowlist: set[str] | None = None,
) -> RootKeyCanaryDecision:
    canary_enabled = settings.ROOT_KEY_SAFE_REMEDIATION_CANARY_ENABLED if enabled is None else bool(enabled)
    if not canary_enabled:
        return RootKeyCanaryDecision(
            allowed=True,
            reason="canary_disabled",
            bucket=None,
            percent=100,
            matched_allowlist=False,
        )

    normalized_percent = _normalize_percent(
        settings.root_key_canary_percent if percent is None else percent
    )
    tenants = settings.root_key_canary_tenant_allowlist if tenant_allowlist is None else tenant_allowlist
    accounts = settings.root_key_canary_account_allowlist if account_allowlist is None else account_allowlist

    tenant_key = str(tenant_id).strip()
    account_key = str(account_id or "").strip()
    if tenant_key in tenants or account_key in accounts:
        return RootKeyCanaryDecision(
            allowed=True,
            reason="canary_allowlist",
            bucket=None,
            percent=normalized_percent,
            matched_allowlist=True,
        )

    bucket = _rollout_bucket(tenant_id=tenant_key, account_id=account_key)
    allowed = bucket < normalized_percent
    return RootKeyCanaryDecision(
        allowed=allowed,
        reason="canary_percent_selected" if allowed else "canary_percent_excluded",
        bucket=bucket,
        percent=normalized_percent,
        matched_allowlist=False,
    )


def sanitize_operator_override_reason(reason: str | None, *, max_len: int = 240) -> str | None:
    normalized = (reason or "").strip()
    if not normalized:
        return None
    collapsed = " ".join(normalized.split())
    if _looks_like_secret(collapsed):
        return "<REDACTED>"
    return collapsed[:max_len]


def _normalize_percent(value: int) -> int:
    return max(0, min(100, int(value)))


def _rollout_bucket(*, tenant_id: str, account_id: str) -> int:
    seed = f"{tenant_id}:{account_id}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    return int(digest[:8], 16) % 100


def _looks_like_secret(value: str) -> bool:
    if _AWS_ACCESS_KEY_PATTERN.search(value):
        return True
    if _SECRET_TEXT_PATTERN.search(value):
        return True
    return _PRIVATE_KEY_PATTERN.search(value) is not None
