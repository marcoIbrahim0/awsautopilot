from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from backend.config import settings

ALGORITHM = "HS256"


def _secret() -> str:
    configured = (getattr(settings, "BUNDLE_REPORTING_TOKEN_SECRET", "") or "").strip()
    return configured or settings.JWT_SECRET


def issue_group_run_reporting_token(
    *,
    tenant_id: uuid.UUID,
    group_run_id: uuid.UUID,
    group_id: uuid.UUID,
    allowed_action_ids: list[uuid.UUID],
    ttl_seconds: int | None = None,
) -> tuple[str, str, datetime]:
    expires_in = max(60, int(ttl_seconds or settings.BUNDLE_REPORTING_TOKEN_TTL_SECONDS))
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in)
    jti = str(uuid.uuid4())
    payload = {
        "tenant_id": str(tenant_id),
        "group_run_id": str(group_run_id),
        "group_id": str(group_id),
        "allowed_action_ids": [str(action_id) for action_id in allowed_action_ids],
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    return token, jti, expires_at


def verify_group_run_reporting_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    required = {"tenant_id", "group_run_id", "group_id", "allowed_action_ids", "jti", "exp"}
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"missing token claims: {', '.join(sorted(missing))}")

    if not isinstance(payload.get("allowed_action_ids"), list):
        raise ValueError("allowed_action_ids claim must be a list")
    return payload
