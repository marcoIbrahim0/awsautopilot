from __future__ import annotations

import re

from backend.services.control_scope import action_type_from_control, canonical_control_id_for_action_type

_CONTROL_ID_TOKEN_RE = re.compile(r"([A-Za-z][A-Za-z0-9]*\.\d+)$")
_AWS_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")
_AWS_ACCOUNT_REGION_RE = re.compile(r"^(\d{12}):([a-z0-9-]+)$")
_SG_ID_RE = re.compile(r"\bsg-[0-9a-f]{8,17}\b")


def normalize_control_id_token(raw: str | None) -> str | None:
    """
    Normalize a Security Hub-style control token.

    Examples:
    - "EC2.19" -> "EC2.19"
    - "something/EC2.19" -> "EC2.19"
    """
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    match = _CONTROL_ID_TOKEN_RE.search(value)
    if match:
        value = match.group(1)
    value = value.strip()
    return value.upper() if value else None


def canonicalize_control_id(observed_control_id: str | None) -> str | None:
    """
    Map an observed control_id into a canonical control_id suitable for joins/dedupe.

    Uses the action mapping registry in backend.services.control_scope so aliases
    (for example EC2.19) normalize into a single canonical control (EC2.53).
    """
    normalized = normalize_control_id_token(observed_control_id)
    if not normalized:
        return None

    action_type = action_type_from_control(normalized)
    canonical = canonical_control_id_for_action_type(action_type, normalized) or normalized
    return normalize_control_id_token(canonical) or normalized


def _bucket_name_from_any(value: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    if v.startswith("arn:aws:s3:::"):
        v = v.replace("arn:aws:s3:::", "", 1)
    return v.strip() or None


def _security_group_id_from_any(value: str) -> str | None:
    v = (value or "").strip()
    if not v:
        return None
    match = _SG_ID_RE.search(v)
    return match.group(0) if match else None


def build_resource_key(
    *,
    account_id: str,
    region: str | None,
    resource_id: str | None,
    resource_type: str | None,
) -> str | None:
    """
    Normalize resource identifiers into a stable key for joins/dedupe.

    Key format examples:
    - "sg:sg-0123abcd..." (EC2 Security Group)
    - "s3:my-bucket" (S3 bucket)
    - "account:123456789012" (account-scoped)
    - "account:123456789012:region:eu-north-1" (account+region scoped)
    - "rid:<raw>" (fallback; stable but less pretty)
    """
    rid = (resource_id or "").strip()
    rtype = (resource_type or "").strip()

    # Account/region scoped: prefer explicit resource_type when available.
    if rtype == "AwsAccount":
        return f"account:{account_id}"
    if rtype == "AwsAccountRegion":
        reg = (region or "").strip()
        if reg:
            return f"account:{account_id}:region:{reg}"

    # Parse structured resource_id shapes.
    if rid:
        m = _AWS_ACCOUNT_REGION_RE.match(rid)
        if m:
            return f"account:{m.group(1)}:region:{m.group(2)}"
        if _AWS_ACCOUNT_ID_RE.match(rid):
            return f"account:{rid}"

    # Service-specific keys.
    sg_id = _security_group_id_from_any(rid)
    if sg_id:
        return f"sg:{sg_id}"

    if rtype == "AwsS3Bucket" or rid.startswith("arn:aws:s3:::"):
        bucket = _bucket_name_from_any(rid)
        if bucket:
            return f"s3:{bucket}"

    if not rid:
        return None

    # Fallback: stable per exact resource_id.
    return f"rid:{rid[:500]}"

