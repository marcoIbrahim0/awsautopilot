"""
Tests for Step 9.8: In-scope controls, control_id mapping and PR bundle coverage.

Asserts the in-scope control list (control_scope) has all mapped action types, action_engine
uses the same mapping, and every in-scope action_type has a PR bundle generator.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.services.control_scope import (
    ACTION_TYPE_DEFAULT,
    CONTROL_ALIAS_TO_ACTION_TYPE,
    CONTROL_TO_ACTION_TYPE,
    IN_SCOPE_CONTROL_IDS,
    IN_SCOPE_CONTROLS,
    UNSUPPORTED_CONTROL_DECISIONS,
    action_type_from_control,
    canonical_control_id_for_action_type,
    unsupported_control_decision,
)
from backend.services.action_engine import _action_type_from_control
from backend.services.pr_bundle import SUPPORTED_ACTION_TYPES

_RUNTIME_CONTROL_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*\.\d+$")
_ARCHITECTURE_OBJECTIVE_ID_PATTERN = re.compile(r"^ARC-\d+$")


def _inventory_reconcile_control_ids() -> set[str]:
    source_path = Path(__file__).resolve().parents[1] / "backend/workers/services/inventory_reconcile.py"
    source = source_path.read_text(encoding="utf-8")
    return set(re.findall(r'control_id="([^"]+)"', source))


def test_in_scope_controls_has_sixteen_rows() -> None:
    """Phase 1: In-scope control list has 16 rows after adding top-volume controls."""
    assert len(IN_SCOPE_CONTROLS) == 16
    assert len(CONTROL_TO_ACTION_TYPE) == 16
    assert len(IN_SCOPE_CONTROL_IDS) == 16
    assert len(CONTROL_ALIAS_TO_ACTION_TYPE) >= 7


def test_control_to_action_type_matches_table() -> None:
    """CONTROL_TO_ACTION_TYPE matches the canonical in-scope mapping table."""
    expected = {
        "S3.1": "s3_block_public_access",
        "SecurityHub.1": "enable_security_hub",
        "GuardDuty.1": "enable_guardduty",
        "S3.2": "s3_bucket_block_public_access",
        "S3.4": "s3_bucket_encryption",
        "EC2.53": "sg_restrict_public_ports",
        "CloudTrail.1": "cloudtrail_enabled",
        "Config.1": "aws_config_enabled",
        "SSM.7": "ssm_block_public_sharing",
        "EC2.182": "ebs_snapshot_block_public_access",
        "EC2.7": "ebs_default_encryption",
        "S3.5": "s3_bucket_require_ssl",
        "IAM.4": "iam_root_access_key_absent",
        "S3.9": "s3_bucket_access_logging",
        "S3.11": "s3_bucket_lifecycle_configuration",
        "S3.15": "s3_bucket_encryption_kms",
    }
    assert CONTROL_TO_ACTION_TYPE == expected
    assert set(CONTROL_TO_ACTION_TYPE.keys()) == IN_SCOPE_CONTROL_IDS
    assert CONTROL_ALIAS_TO_ACTION_TYPE["S3.3"] == "s3_bucket_block_public_access"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["S3.8"] == "s3_bucket_block_public_access"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["S3.17"] == "s3_bucket_encryption_kms"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["S3.13"] == "s3_bucket_lifecycle_configuration"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["EC2.13"] == "sg_restrict_public_ports"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["EC2.19"] == "sg_restrict_public_ports"
    assert CONTROL_ALIAS_TO_ACTION_TYPE["EC2.18"] == "sg_restrict_public_ports"


def test_action_type_from_control_all_mapped_controls() -> None:
    """Every in-scope control_id maps to the correct action_type."""
    for c in IN_SCOPE_CONTROLS:
        assert action_type_from_control(c["control_id"]) == c["action_type"]
        assert action_type_from_control("  " + c["control_id"] + "  ") == c["action_type"]
    assert action_type_from_control("S3.3") == "s3_bucket_block_public_access"
    assert action_type_from_control("S3.8") == "s3_bucket_block_public_access"
    assert action_type_from_control("S3.17") == "s3_bucket_encryption_kms"
    assert action_type_from_control("S3.13") == "s3_bucket_lifecycle_configuration"
    assert action_type_from_control("EC2.13") == "sg_restrict_public_ports"
    assert action_type_from_control("EC2.19") == "sg_restrict_public_ports"
    assert action_type_from_control("EC2.18") == "sg_restrict_public_ports"
    # Case-insensitive normalization for legacy/control-source variance.
    assert action_type_from_control("ec2.19") == "sg_restrict_public_ports"
    assert action_type_from_control("config.1") == "aws_config_enabled"
    # Trailing token extraction for prefixed control strings.
    assert action_type_from_control("aws/security-controls/SSM.7") == "ssm_block_public_sharing"


def test_action_type_from_control_unmapped_returns_pr_only() -> None:
    """Step 9.8: Unmapped (out-of-scope) control_id returns pr_only."""
    assert action_type_from_control(None) == ACTION_TYPE_DEFAULT
    assert action_type_from_control("") == ACTION_TYPE_DEFAULT
    assert action_type_from_control("Unknown.Control.99") == ACTION_TYPE_DEFAULT
    assert action_type_from_control("CIS.1.1") == ACTION_TYPE_DEFAULT


def test_explicitly_unsupported_controls_have_pr_only_action_type() -> None:
    """Known inventory-only controls are explicitly unsupported and map to pr_only."""
    for control_id in ("RDS.PUBLIC_ACCESS", "RDS.ENCRYPTION", "EKS.PUBLIC_ENDPOINT"):
        decision = unsupported_control_decision(control_id)
        assert decision is not None
        assert UNSUPPORTED_CONTROL_DECISIONS[control_id] == decision
        assert decision["action_type"] == ACTION_TYPE_DEFAULT
        assert decision["remediation_classification"] == "UNSUPPORTED"
        assert decision["support_status"] == "unsupported"
        assert "inventory-only visibility exists" in decision["reason"].lower()
        assert action_type_from_control(control_id) == ACTION_TYPE_DEFAULT


def test_action_engine_uses_control_scope_mapping() -> None:
    """Step 9.8: action_engine._action_type_from_control uses control_scope mapping."""
    for control_id, action_type in CONTROL_TO_ACTION_TYPE.items():
        assert _action_type_from_control(control_id) == action_type
    for control_id, action_type in CONTROL_ALIAS_TO_ACTION_TYPE.items():
        assert _action_type_from_control(control_id) == action_type
    assert _action_type_from_control(None) == ACTION_TYPE_DEFAULT
    assert _action_type_from_control("Unmapped.1") == ACTION_TYPE_DEFAULT


def test_canonical_control_id_for_action_type_uses_primary_control() -> None:
    """Equivalent controls map back to one canonical control_id for deterministic action dedupe."""
    assert canonical_control_id_for_action_type(
        "s3_bucket_block_public_access",
        "S3.8",
    ) == "S3.2"
    assert canonical_control_id_for_action_type(
        "s3_bucket_block_public_access",
        "S3.3",
    ) == "S3.2"
    assert canonical_control_id_for_action_type(
        "sg_restrict_public_ports",
        "EC2.13",
    ) == "EC2.53"
    assert canonical_control_id_for_action_type(
        "sg_restrict_public_ports",
        "EC2.19",
    ) == "EC2.53"
    assert canonical_control_id_for_action_type(
        "sg_restrict_public_ports",
        "EC2.18",
    ) == "EC2.53"
    assert canonical_control_id_for_action_type(
        "s3_bucket_lifecycle_configuration",
        "S3.13",
    ) == "S3.11"
    assert canonical_control_id_for_action_type(
        "s3_bucket_encryption_kms",
        "S3.17",
    ) == "S3.15"
    assert canonical_control_id_for_action_type("pr_only", "S3.8") == "S3.8"


def test_pr_bundle_coverage_all_in_scope_types() -> None:
    """Every in-scope action_type has a PR bundle generator."""
    in_scope_action_types = {c["action_type"] for c in IN_SCOPE_CONTROLS}
    assert in_scope_action_types <= SUPPORTED_ACTION_TYPES, (
        f"In-scope action types missing from pr_bundle.SUPPORTED_ACTION_TYPES: "
        f"{in_scope_action_types - SUPPORTED_ACTION_TYPES}"
    )
    assert len(SUPPORTED_ACTION_TYPES) == 16
    assert in_scope_action_types == SUPPORTED_ACTION_TYPES
    for c in IN_SCOPE_CONTROLS:
        assert c["action_type"] in SUPPORTED_ACTION_TYPES


def test_in_scope_direct_fix_four_only() -> None:
    """Phase 1: Exactly 4 in-scope controls have direct_fix."""
    direct_fix_controls = [c for c in IN_SCOPE_CONTROLS if c["direct_fix"]]
    assert len(direct_fix_controls) == 4
    direct_fix_ids = {c["control_id"] for c in direct_fix_controls}
    assert direct_fix_ids == {"S3.1", "SecurityHub.1", "GuardDuty.1", "EC2.7"}


def test_in_scope_all_have_pr_bundle() -> None:
    """All in-scope controls have pr_bundle True (real IaC or strategy guidance)."""
    for c in IN_SCOPE_CONTROLS:
        assert c["pr_bundle"] is True


def test_runtime_registry_excludes_architecture_objective_ids() -> None:
    """Architecture objective IDs (ARC-*) must never be registered as runtime controls."""
    runtime_registry = set(CONTROL_TO_ACTION_TYPE) | set(CONTROL_ALIAS_TO_ACTION_TYPE)
    unexpected = {
        control_id for control_id in runtime_registry if _ARCHITECTURE_OBJECTIVE_ID_PATTERN.fullmatch(control_id)
    }
    assert not unexpected, f"Architecture objective IDs leaked into runtime control registry: {sorted(unexpected)}"


def test_inventory_runtime_controls_are_defined_in_control_registry() -> None:
    """Runtime-shaped control IDs emitted by inventory must be mapped in control_scope."""
    runtime_registry = set(CONTROL_TO_ACTION_TYPE) | set(CONTROL_ALIAS_TO_ACTION_TYPE)
    inventory_runtime_controls = {
        control_id
        for control_id in _inventory_reconcile_control_ids()
        if _RUNTIME_CONTROL_ID_PATTERN.fullmatch(control_id)
    }
    missing = inventory_runtime_controls - runtime_registry
    assert not missing, f"Inventory emits runtime controls without definitions: {sorted(missing)}"


def test_dr_template_uses_architecture_objective_tag_for_arc008() -> None:
    """ARC-008 should stay infra metadata, not a runtime control-tag key."""
    template_path = Path(__file__).resolve().parents[1] / "infrastructure/cloudformation/dr-backup-controls.yaml"
    template_text = template_path.read_text(encoding="utf-8")
    assert "ArchitectureObjectiveId: ARC-008" in template_text
    assert "Control: ARC-008" not in template_text
