"""
Tests for Step 9.8: In-scope controls, control_id mapping and PR bundle coverage.

Asserts the in-scope control list (control_scope) has all 7 types, action_engine
uses the same mapping, and every in-scope action_type has a PR bundle generator.
"""
from __future__ import annotations

import pytest

from backend.services.control_scope import (
    ACTION_TYPE_DEFAULT,
    CONTROL_TO_ACTION_TYPE,
    IN_SCOPE_CONTROL_IDS,
    IN_SCOPE_CONTROLS,
    action_type_from_control,
)
from backend.services.action_engine import _action_type_from_control
from backend.services.pr_bundle import SUPPORTED_ACTION_TYPES


def test_in_scope_controls_has_seven_rows() -> None:
    """Step 9.8: In-scope control list has exactly 7 rows (7 action types)."""
    assert len(IN_SCOPE_CONTROLS) == 7
    assert len(CONTROL_TO_ACTION_TYPE) == 7
    assert len(IN_SCOPE_CONTROL_IDS) == 7


def test_control_to_action_type_matches_table() -> None:
    """Step 9.8: CONTROL_TO_ACTION_TYPE matches the implementation plan table."""
    expected = {
        "S3.1": "s3_block_public_access",
        "SecurityHub.1": "enable_security_hub",
        "GuardDuty.1": "enable_guardduty",
        "S3.2": "s3_bucket_block_public_access",
        "S3.4": "s3_bucket_encryption",
        "EC2.18": "sg_restrict_public_ports",
        "CloudTrail.1": "cloudtrail_enabled",
    }
    assert CONTROL_TO_ACTION_TYPE == expected
    assert set(CONTROL_TO_ACTION_TYPE.keys()) == IN_SCOPE_CONTROL_IDS


def test_action_type_from_control_all_seven() -> None:
    """Step 9.8: Every in-scope control_id maps to the correct action_type."""
    for c in IN_SCOPE_CONTROLS:
        assert action_type_from_control(c["control_id"]) == c["action_type"]
        assert action_type_from_control("  " + c["control_id"] + "  ") == c["action_type"]


def test_action_type_from_control_unmapped_returns_pr_only() -> None:
    """Step 9.8: Unmapped (out-of-scope) control_id returns pr_only."""
    assert action_type_from_control(None) == ACTION_TYPE_DEFAULT
    assert action_type_from_control("") == ACTION_TYPE_DEFAULT
    assert action_type_from_control("Unknown.Control.99") == ACTION_TYPE_DEFAULT
    assert action_type_from_control("CIS.1.1") == ACTION_TYPE_DEFAULT


def test_action_engine_uses_control_scope_mapping() -> None:
    """Step 9.8: action_engine._action_type_from_control uses control_scope mapping."""
    for control_id, action_type in CONTROL_TO_ACTION_TYPE.items():
        assert _action_type_from_control(control_id) == action_type
    assert _action_type_from_control(None) == ACTION_TYPE_DEFAULT
    assert _action_type_from_control("Unmapped.1") == ACTION_TYPE_DEFAULT


def test_pr_bundle_coverage_all_in_scope_types() -> None:
    """Step 9.8: Every in-scope action_type has a PR bundle generator (9.2–9.5, 9.9–9.12)."""
    in_scope_action_types = {c["action_type"] for c in IN_SCOPE_CONTROLS}
    assert in_scope_action_types <= SUPPORTED_ACTION_TYPES, (
        f"In-scope action types missing from pr_bundle.SUPPORTED_ACTION_TYPES: "
        f"{in_scope_action_types - SUPPORTED_ACTION_TYPES}"
    )
    assert len(SUPPORTED_ACTION_TYPES) == 7
    assert in_scope_action_types == SUPPORTED_ACTION_TYPES
    for c in IN_SCOPE_CONTROLS:
        assert c["action_type"] in SUPPORTED_ACTION_TYPES


def test_in_scope_direct_fix_three_only() -> None:
    """Step 9.8: Exactly 3 in-scope controls have direct_fix (S3.1, SecurityHub.1, GuardDuty.1)."""
    direct_fix_controls = [c for c in IN_SCOPE_CONTROLS if c["direct_fix"]]
    assert len(direct_fix_controls) == 3
    direct_fix_ids = {c["control_id"] for c in direct_fix_controls}
    assert direct_fix_ids == {"S3.1", "SecurityHub.1", "GuardDuty.1"}


def test_in_scope_all_have_pr_bundle() -> None:
    """Step 9.8: All 7 in-scope controls have pr_bundle True (real IaC)."""
    for c in IN_SCOPE_CONTROLS:
        assert c["pr_bundle"] is True
