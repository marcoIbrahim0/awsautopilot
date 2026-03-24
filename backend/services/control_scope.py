"""
In-scope controls: control_id mapping and PR bundle coverage.

Single source of truth for mapped action types. The table in IN_SCOPE_CONTROLS
lists one primary control per action type. Additional control aliases that
share the same remediation are defined separately and map into the same
action_type for safe action merging.

Out-of-scope controls map to pr_only and receive guidance placeholder.
"""
from __future__ import annotations

import re
from typing import TypedDict

# ---------------------------------------------------------------------------
# In-scope control list
# ---------------------------------------------------------------------------
# action_type          | control_id(s)        | Direct fix | PR bundle | Subsection
# ---------------------|----------------------|------------|-----------|------------
# s3_block_public_access | S3.1               | Y          | Y         | 9.2, 9.5
# enable_security_hub  | SecurityHub.1        | Y          | Y         | 9.3, 9.5
# enable_guardduty      | GuardDuty.1         | Y          | Y         | 9.4, 9.5
# s3_bucket_block_public_access | S3.2     | N          | Y         | 9.9, 9.5
# s3_bucket_encryption | S3.4                 | N          | Y         | 9.10, 9.5
# sg_restrict_public_ports | EC2.53           | N          | Y         | 9.11, 9.5
# cloudtrail_enabled    | CloudTrail.1        | N          | Y         | 9.12, 9.5
# aws_config_enabled    | Config.1            | N          | Y         | phase1
# ssm_block_public_sharing | SSM.7            | N          | Y         | phase1
# ebs_snapshot_block_public_access | EC2.182  | N          | Y         | phase1
# ebs_default_encryption | EC2.7              | Y          | Y         | phase1
# s3_bucket_require_ssl | S3.5                | N          | Y         | phase1
# iam_root_access_key_absent | IAM.4          | N          | Y         | phase1
# s3_bucket_access_logging | S3.9             | N          | Y         | phase1
# s3_bucket_lifecycle_configuration | S3.11   | N          | Y         | phase1
# s3_bucket_encryption_kms | S3.15            | N          | Y         | phase1
# pr_only               | (unmapped)          | N          | guidance  | fallback
# ---------------------------------------------------------------------------


class InScopeControl(TypedDict):
    """One row of the in-scope control table."""

    control_id: str
    action_type: str
    direct_fix: bool
    pr_bundle: bool
    subsection: str


class UnsupportedControlDecision(TypedDict):
    """Explicit support decision for controls intentionally out of remediation scope."""

    control_id: str
    action_type: str
    remediation_classification: str
    support_status: str
    reason: str


# Canonical list for documentation and tests (one primary control per action type).
IN_SCOPE_CONTROLS: tuple[InScopeControl, ...] = (
    InScopeControl(
        control_id="S3.1",
        action_type="s3_block_public_access",
        direct_fix=True,
        pr_bundle=True,
        subsection="9.2, 9.5",
    ),
    InScopeControl(
        control_id="SecurityHub.1",
        action_type="enable_security_hub",
        direct_fix=True,
        pr_bundle=True,
        subsection="9.3, 9.5",
    ),
    InScopeControl(
        control_id="GuardDuty.1",
        action_type="enable_guardduty",
        direct_fix=True,
        pr_bundle=True,
        subsection="9.4, 9.5",
    ),
    InScopeControl(
        control_id="S3.2",
        action_type="s3_bucket_block_public_access",
        direct_fix=False,
        pr_bundle=True,
        subsection="9.9, 9.5",
    ),
    InScopeControl(
        control_id="S3.4",
        action_type="s3_bucket_encryption",
        direct_fix=False,
        pr_bundle=True,
        subsection="9.10, 9.5",
    ),
    InScopeControl(
        control_id="EC2.53",
        action_type="sg_restrict_public_ports",
        direct_fix=False,
        pr_bundle=True,
        subsection="9.11, 9.5",
    ),
    InScopeControl(
        control_id="CloudTrail.1",
        action_type="cloudtrail_enabled",
        direct_fix=False,
        pr_bundle=True,
        subsection="9.12, 9.5",
    ),
    InScopeControl(
        control_id="Config.1",
        action_type="aws_config_enabled",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="SSM.7",
        action_type="ssm_block_public_sharing",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="EC2.182",
        action_type="ebs_snapshot_block_public_access",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="EC2.7",
        action_type="ebs_default_encryption",
        direct_fix=True,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="S3.5",
        action_type="s3_bucket_require_ssl",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="IAM.4",
        action_type="iam_root_access_key_absent",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="S3.9",
        action_type="s3_bucket_access_logging",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="S3.11",
        action_type="s3_bucket_lifecycle_configuration",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
    InScopeControl(
        control_id="S3.15",
        action_type="s3_bucket_encryption_kms",
        direct_fix=False,
        pr_bundle=True,
        subsection="phase1",
    ),
)

# Primary control_id -> action_type mapping (one canonical control per action type).
CONTROL_TO_ACTION_TYPE: dict[str, str] = {c["control_id"]: c["action_type"] for c in IN_SCOPE_CONTROLS}

# Safe aliases: controls whose remediation is equivalent to a canonical action type.
# Keep this conservative; only add aliases when the generated remediation is truly compatible.
CONTROL_ALIAS_TO_ACTION_TYPE: dict[str, str] = {
    "S3.3": "s3_bucket_block_public_access",
    "S3.8": "s3_bucket_block_public_access",
    # AWS now surfaces the lifecycle family on S3.13; keep the product family canonicalized to S3.11.
    "S3.13": "s3_bucket_lifecycle_configuration",
    # AWS now surfaces the SSE-KMS family on S3.17 in the current standards catalog.
    "S3.17": "s3_bucket_encryption_kms",
    # EC2 security group hardening: treat these controls as equivalent remediation for MVP.
    # Canonical control_id stored on the action is EC2.53.
    "EC2.13": "sg_restrict_public_ports",
    "EC2.19": "sg_restrict_public_ports",
    # Back-compat with earlier canonical mapping (Step 9.11 previously used EC2.18).
    "EC2.18": "sg_restrict_public_ports",
}

# Normalized lookup maps used by action_type_from_control().
# Normalization is case-insensitive and extracts trailing ControlId-like tokens
# from values such as ".../Config.1".
_CONTROL_TO_ACTION_TYPE_NORMALIZED: dict[str, str] = {
    control_id.upper(): action_type for control_id, action_type in CONTROL_TO_ACTION_TYPE.items()
}
_CONTROL_ALIAS_TO_ACTION_TYPE_NORMALIZED: dict[str, str] = {
    control_id.upper(): action_type for control_id, action_type in CONTROL_ALIAS_TO_ACTION_TYPE.items()
}
_CONTROL_ID_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9]*\.\d+)$")

# Action type -> primary control_id for deterministic dedupe target_id and UI metadata.
PRIMARY_CONTROL_FOR_ACTION_TYPE: dict[str, str] = {
    c["action_type"]: c["control_id"] for c in IN_SCOPE_CONTROLS
}

# Canonical control IDs that receive real IaC (PR bundle or direct fix).
IN_SCOPE_CONTROL_IDS: frozenset[str] = frozenset(CONTROL_TO_ACTION_TYPE.keys())

# Controls considered "in scope" for ingestion and UI filtering. Includes aliases.
IN_SCOPE_CONTROL_TOKENS: frozenset[str] = frozenset(
    set(CONTROL_TO_ACTION_TYPE.keys()) | set(CONTROL_ALIAS_TO_ACTION_TYPE.keys())
)

# Default action type when control is not in scope.
ACTION_TYPE_DEFAULT = "pr_only"

# Explicitly unsupported controls: known inventory signals with no implemented remediation.
UNSUPPORTED_CONTROL_DECISIONS: dict[str, UnsupportedControlDecision] = {
    "RDS.PUBLIC_ACCESS": UnsupportedControlDecision(
        control_id="RDS.PUBLIC_ACCESS",
        action_type=ACTION_TYPE_DEFAULT,
        remediation_classification="UNSUPPORTED",
        support_status="unsupported",
        reason=(
            "Inventory-only visibility exists, but no mapped remediation action type, "
            "strategy, direct-fix executor, or PR-bundle generator is implemented."
        ),
    ),
    "RDS.ENCRYPTION": UnsupportedControlDecision(
        control_id="RDS.ENCRYPTION",
        action_type=ACTION_TYPE_DEFAULT,
        remediation_classification="UNSUPPORTED",
        support_status="unsupported",
        reason=(
            "Inventory-only visibility exists, but no mapped remediation action type, "
            "strategy, direct-fix executor, or PR-bundle generator is implemented."
        ),
    ),
    "EKS.PUBLIC_ENDPOINT": UnsupportedControlDecision(
        control_id="EKS.PUBLIC_ENDPOINT",
        action_type=ACTION_TYPE_DEFAULT,
        remediation_classification="UNSUPPORTED",
        support_status="unsupported",
        reason=(
            "Inventory-only visibility exists, but no mapped remediation action type, "
            "strategy, direct-fix executor, or PR-bundle generator is implemented."
        ),
    ),
}
_UNSUPPORTED_CONTROL_DECISIONS_NORMALIZED: dict[str, UnsupportedControlDecision] = {
    control_id.upper(): decision for control_id, decision in UNSUPPORTED_CONTROL_DECISIONS.items()
}


def _normalize_control_id(control_id: str | None) -> str | None:
    """
    Normalize control IDs for stable mapping.

    - trims whitespace
    - extracts trailing token like EC2.19 from values such as ".../EC2.19"
    - compares case-insensitively
    """
    if not control_id:
        return None
    raw = control_id.strip()
    if not raw:
        return None
    match = _CONTROL_ID_PATTERN.search(raw)
    if match:
        raw = match.group(1)
    return raw.upper()


def action_type_from_control(control_id: str | None) -> str:
    """Derive action_type from control_id; default pr_only (Step 9.8)."""
    normalized = _normalize_control_id(control_id)
    if not normalized:
        return ACTION_TYPE_DEFAULT
    if normalized in _CONTROL_TO_ACTION_TYPE_NORMALIZED:
        return _CONTROL_TO_ACTION_TYPE_NORMALIZED[normalized]
    if normalized in _UNSUPPORTED_CONTROL_DECISIONS_NORMALIZED:
        return ACTION_TYPE_DEFAULT
    return _CONTROL_ALIAS_TO_ACTION_TYPE_NORMALIZED.get(normalized, ACTION_TYPE_DEFAULT)


def unsupported_control_decision(control_id: str | None) -> UnsupportedControlDecision | None:
    """Return explicit unsupported-control metadata when a control is intentionally unsupported."""
    normalized = _normalize_control_id(control_id)
    if not normalized:
        return None
    return _UNSUPPORTED_CONTROL_DECISIONS_NORMALIZED.get(normalized)


def canonical_control_id_for_action_type(action_type: str, observed_control_id: str | None) -> str | None:
    """
    Return deterministic control_id to use for grouped actions.

    - For canonical action types, use the primary control_id.
    - For pr_only/unmapped action types, keep the observed control_id.
    """
    canonical = PRIMARY_CONTROL_FOR_ACTION_TYPE.get((action_type or "").strip())
    if canonical:
        return canonical
    if not observed_control_id:
        return None
    normalized = observed_control_id.strip()
    return normalized or None


def equivalent_control_ids_for_control(control_id: str | None) -> tuple[str, ...]:
    """
    Return the canonical control plus any runtime-safe aliases for the same family.

    This is used for UI filtering/search so flat action queries can match the same
    remediation family regardless of whether the caller uses a canonical ID or an alias.
    """
    normalized = _normalize_control_id(control_id)
    if not normalized:
        return ()

    action_type = action_type_from_control(normalized)
    if action_type == ACTION_TYPE_DEFAULT:
        return (normalized,)

    canonical = canonical_control_id_for_action_type(action_type, normalized) or normalized
    aliases = sorted(
        control_id
        for control_id, alias_action_type in CONTROL_ALIAS_TO_ACTION_TYPE.items()
        if alias_action_type == action_type
    )
    return tuple(dict.fromkeys([canonical, *aliases]))
