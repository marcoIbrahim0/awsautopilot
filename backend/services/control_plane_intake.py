"""
Control-plane event intake helpers.

Shared by:
- Public intake endpoint (EventBridge API Destination)
- Internal intake endpoint (for alternative wiring / cron)

Phase 1 intentionally supports a small allowlist of management API calls only.
"""

from __future__ import annotations

from typing import Any

from backend.services.control_plane_event_allowlist import (
    SUPPORTED_CONTROL_PLANE_DETAIL_TYPE,
    SUPPORTED_CONTROL_PLANE_EVENT_NAMES,
)


def is_supported_control_plane_event(event: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate that the event is a CloudTrail management event in our allowlist.

    Returns (supported, reason). Reason is only set when supported=False.
    """
    detail_type = str(event.get("detail-type") or "")
    if detail_type != SUPPORTED_CONTROL_PLANE_DETAIL_TYPE:
        return False, "unsupported_detail_type"

    detail = event.get("detail") or {}
    event_name = str(detail.get("eventName") or "")
    if event_name not in SUPPORTED_CONTROL_PLANE_EVENT_NAMES:
        return False, "unsupported_event_name"

    event_category = str(detail.get("eventCategory") or "").upper()
    # Some EventBridge deliveries omit eventCategory for management APIs; allow missing.
    if event_category and event_category != "MANAGEMENT":
        return False, "unsupported_event_category"

    return True, None
