"""
In-scope controls: control_id mapping and PR bundle coverage (Step 9.8).

Single source of truth for the MVP in-scope control list. Every in-scope
Security Hub control maps to one action_type and gets real IaC (no pr_only
/ README.tf fallback). Out-of-scope controls map to pr_only and receive
guidance placeholder.

Process for new controls: (1) add control_id to CONTROL_TO_ACTION_TYPE and
to IN_SCOPE_CONTROLS; (2) if action_type is new, implement generator in
pr_bundle (9.9-style); if existing, no code change.
"""
from __future__ import annotations

from typing import TypedDict

# ---------------------------------------------------------------------------
# In-scope control list (Step 9.8 table)
# ---------------------------------------------------------------------------
# action_type          | control_id(s)        | Direct fix | PR bundle | Subsection
# ---------------------|----------------------|------------|-----------|------------
# s3_block_public_access | S3.1               | Y          | Y         | 9.2, 9.5
# enable_security_hub  | SecurityHub.1        | Y          | Y         | 9.3, 9.5
# enable_guardduty      | GuardDuty.1         | Y          | Y         | 9.4, 9.5
# s3_bucket_block_public_access | S3.2     | N          | Y         | 9.9, 9.5
# s3_bucket_encryption | S3.4                 | N          | Y         | 9.10, 9.5
# sg_restrict_public_ports | EC2.18 (FSBP)    | N          | Y         | 9.11, 9.5
# cloudtrail_enabled    | CloudTrail.1        | N          | Y         | 9.12, 9.5
# pr_only               | (unmapped)          | N          | guidance  | 9.1 fallback
# ---------------------------------------------------------------------------


class InScopeControl(TypedDict):
    """One row of the Step 9.8 in-scope control table."""

    control_id: str
    action_type: str
    direct_fix: bool
    pr_bundle: bool
    subsection: str


# Canonical list for documentation and tests; CONTROL_TO_ACTION_TYPE is the mapping used by action_engine.
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
        control_id="EC2.18",
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
)

# Map Security Hub control_id → action_type. Used by action_engine (Step 9.8).
# Unmapped controls default to pr_only (guidance placeholder).
CONTROL_TO_ACTION_TYPE: dict[str, str] = {c["control_id"]: c["action_type"] for c in IN_SCOPE_CONTROLS}

# All control IDs that receive real IaC (PR bundle or direct fix).
IN_SCOPE_CONTROL_IDS: frozenset[str] = frozenset(CONTROL_TO_ACTION_TYPE.keys())

# Default action type when control is not in scope.
ACTION_TYPE_DEFAULT = "pr_only"


def action_type_from_control(control_id: str | None) -> str:
    """Derive action_type from control_id; default pr_only (Step 9.8)."""
    if not control_id:
        return ACTION_TYPE_DEFAULT
    return CONTROL_TO_ACTION_TYPE.get(control_id.strip(), ACTION_TYPE_DEFAULT)
