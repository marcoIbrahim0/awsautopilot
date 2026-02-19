"""
Unit tests for worker/services/direct_fix.py (Step 8.2).

Tests cover:
- Unsupported action_type
- S3 Block Public Access: already compliant, apply+post-check, pre-check exception, apply failure
- Security Hub: region required, already enabled
- GuardDuty: region required, already enabled
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from backend.workers.services.direct_fix import (
    DirectFixResult,
    SUPPORTED_ACTION_TYPES,
    run_direct_fix,
    run_remediation_preview,
)


def _mock_session(clients: dict[str, MagicMock]) -> MagicMock:
    """Build a mock boto3 Session whose client() returns the given service mocks."""
    session = MagicMock()

    def client(name: str, **kwargs):
        if name in clients:
            return clients[name]
        return MagicMock()

    session.client.side_effect = client
    return session


# ---------------------------------------------------------------------------
# Unsupported action_type
# ---------------------------------------------------------------------------
def test_unsupported_action_type() -> None:
    """Unsupported action_type returns failure."""
    session = _mock_session({})
    result = run_direct_fix(session, "unknown_fix", "123456789012", "us-east-1")
    assert result.success is False
    assert "Unsupported" in result.outcome or "unknown" in result.outcome.lower()


def test_supported_action_types_constant() -> None:
    """SUPPORTED_ACTION_TYPES contains the four low-risk direct-fix action types."""
    assert "s3_block_public_access" in SUPPORTED_ACTION_TYPES
    assert "enable_security_hub" in SUPPORTED_ACTION_TYPES
    assert "enable_guardduty" in SUPPORTED_ACTION_TYPES
    assert "ebs_default_encryption" in SUPPORTED_ACTION_TYPES
    assert len(SUPPORTED_ACTION_TYPES) == 4


# ---------------------------------------------------------------------------
# S3 Block Public Access
# ---------------------------------------------------------------------------
def test_s3_block_public_access_already_compliant() -> None:
    """Pre-check finds all four settings True -> success, no apply."""
    s3c = MagicMock()
    s3c.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }
    session = _mock_session({"s3control": s3c})

    result = run_direct_fix(session, "s3_block_public_access", "123456789012", None)

    assert result.success is True
    assert "Already compliant" in result.outcome
    s3c.get_public_access_block.assert_called_once_with(AccountId="123456789012")
    s3c.put_public_access_block.assert_not_called()


def test_s3_block_public_access_apply_and_post_check() -> None:
    """Pre-check finds not compliant -> apply -> post-check passes."""
    s3c = MagicMock()
    s3c.get_public_access_block.side_effect = [
        ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration", "Message": "Not configured"}},
            "get_public_access_block",
        ),
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        },
    ]  # First call raises, second returns post-check config
    session = _mock_session({"s3control": s3c})

    result = run_direct_fix(session, "s3_block_public_access", "123456789012", None)

    assert result.success is True
    assert "S3 Block Public Access enabled" in result.outcome
    s3c.put_public_access_block.assert_called_once()
    call_kw = s3c.put_public_access_block.call_args[1]
    assert call_kw["AccountId"] == "123456789012"
    config = call_kw["PublicAccessBlockConfiguration"]
    assert config["BlockPublicAcls"] is True
    assert config["RestrictPublicBuckets"] is True


def test_s3_block_public_access_apply_fails() -> None:
    """Apply fails with ClientError -> failure."""
    s3c = MagicMock()
    s3c.get_public_access_block.side_effect = ClientError(
        {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration", "Message": "Not configured"}},
        "get_public_access_block",
    )
    s3c.put_public_access_block.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Org policy blocks"}},
        "put_public_access_block",
    )
    session = _mock_session({"s3control": s3c})

    result = run_direct_fix(session, "s3_block_public_access", "123456789012", None)

    assert result.success is False
    assert "Apply failed" in result.outcome or "AccessDenied" in result.outcome


def test_s3_block_public_access_post_check_fails() -> None:
    """Apply succeeds but post-check finds settings not all True -> run failed (Step 8.2)."""
    s3c = MagicMock()
    s3c.get_public_access_block.side_effect = [
        ClientError(
            {"Error": {"Code": "NoSuchPublicAccessBlockConfiguration", "Message": "Not configured"}},
            "get_public_access_block",
        ),
        # Post-check returns partial config (e.g. one setting False)
        {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": False,
            }
        },
    ]
    session = _mock_session({"s3control": s3c})

    result = run_direct_fix(session, "s3_block_public_access", "123456789012", None)

    assert result.success is False
    assert "Post-check failed" in result.outcome
    s3c.put_public_access_block.assert_called_once()


# ---------------------------------------------------------------------------
# Security Hub
# ---------------------------------------------------------------------------
def test_security_hub_region_required() -> None:
    """enable_security_hub with no region returns failure."""
    session = _mock_session({})
    result = run_direct_fix(session, "enable_security_hub", "123456789012", None)
    assert result.success is False
    assert "Region" in result.outcome or "region" in result.outcome.lower()


def test_security_hub_already_enabled() -> None:
    """Pre-check finds standards enabled -> success, no apply."""
    sh = MagicMock()
    sh.get_enabled_standards.return_value = {
        "StandardsSubscriptions": [{"StandardsSubscriptionArn": "arn:..."}]
    }
    session = _mock_session({"securityhub": sh})

    result = run_direct_fix(session, "enable_security_hub", "123456789012", "us-east-1")

    assert result.success is True
    assert "Already compliant" in result.outcome
    sh.enable_security_hub.assert_not_called()


def test_security_hub_enable_success() -> None:
    """Not enabled -> enable -> post-check passes."""
    sh = MagicMock()
    sh.get_enabled_standards.side_effect = [
        ClientError(
            {"Error": {"Code": "InvalidAccessException", "Message": "Not enabled"}},
            "get_enabled_standards",
        ),
        {"StandardsSubscriptions": [{"StandardsSubscriptionArn": "arn:..."}]},
    ]
    session = _mock_session({"securityhub": sh})

    result = run_direct_fix(session, "enable_security_hub", "123456789012", "us-east-1")

    assert result.success is True
    assert "Security Hub enabled" in result.outcome
    sh.enable_security_hub.assert_called_once_with(EnableDefaultStandards=True)


# ---------------------------------------------------------------------------
# GuardDuty
# ---------------------------------------------------------------------------
def test_guardduty_region_required() -> None:
    """enable_guardduty with no region returns failure."""
    session = _mock_session({})
    result = run_direct_fix(session, "enable_guardduty", "123456789012", None)
    assert result.success is False
    assert "Region" in result.outcome or "region" in result.outcome.lower()


def test_guardduty_already_enabled() -> None:
    """Pre-check finds enabled detector -> success, no apply."""
    gd = MagicMock()
    gd.list_detectors.return_value = {"DetectorIds": ["det-123"]}
    gd.get_detector.return_value = {"Status": "ENABLED"}
    session = _mock_session({"guardduty": gd})

    result = run_direct_fix(session, "enable_guardduty", "123456789012", "us-east-1")

    assert result.success is True
    assert "Already compliant" in result.outcome
    gd.create_detector.assert_not_called()


def test_guardduty_enable_success() -> None:
    """No detector -> create -> post-check passes."""
    gd = MagicMock()
    gd.list_detectors.return_value = {"DetectorIds": []}
    gd.create_detector.return_value = {"DetectorId": "det-new"}
    gd.get_detector.return_value = {"Status": "ENABLED"}
    session = _mock_session({"guardduty": gd})

    result = run_direct_fix(session, "enable_guardduty", "123456789012", "us-east-1")

    assert result.success is True
    assert "GuardDuty enabled" in result.outcome
    gd.create_detector.assert_called_once_with(Enable=True)


def test_guardduty_detector_exists_but_disabled() -> None:
    """Detector exists but disabled -> update_detector(Enable=True) -> success (idempotent)."""
    gd = MagicMock()
    gd.list_detectors.return_value = {"DetectorIds": ["det-123"]}
    gd.get_detector.return_value = {"Status": "DISABLED"}
    gd.create_detector.side_effect = ClientError(
        {"Error": {"Code": "BadRequestException", "Message": "Account already has a GuardDuty detector"}},
        "create_detector",
    )
    session = _mock_session({"guardduty": gd})

    result = run_direct_fix(session, "enable_guardduty", "123456789012", "us-east-1")

    assert result.success is True
    assert "GuardDuty enabled" in result.outcome
    gd.update_detector.assert_called_once_with(DetectorId="det-123", Enable=True)


# ---------------------------------------------------------------------------
# EBS default encryption
# ---------------------------------------------------------------------------
def test_ebs_default_encryption_region_required() -> None:
    """ebs_default_encryption with no region returns failure."""
    session = _mock_session({})
    result = run_direct_fix(session, "ebs_default_encryption", "123456789012", None)
    assert result.success is False
    assert "Region required" in result.outcome


def test_ebs_default_encryption_already_enabled_aws_managed() -> None:
    """When default encryption is already enabled, direct-fix is idempotent."""
    ec2 = MagicMock()
    ec2.get_ebs_encryption_by_default.return_value = {"EbsEncryptionByDefault": True}
    session = _mock_session({"ec2": ec2})

    result = run_direct_fix(session, "ebs_default_encryption", "123456789012", "eu-north-1")

    assert result.success is True
    assert "Already compliant" in result.outcome
    ec2.enable_ebs_encryption_by_default.assert_not_called()


def test_ebs_default_encryption_enable_with_customer_kms_success() -> None:
    """Customer KMS strategy enables encryption and sets default KMS key."""
    ec2 = MagicMock()
    ec2.get_ebs_encryption_by_default.side_effect = [
        {"EbsEncryptionByDefault": False},
        {"EbsEncryptionByDefault": True},
    ]
    ec2.get_ebs_default_kms_key_id.return_value = {"KmsKeyId": "arn:aws:kms:eu-north-1:123:key/abc"}
    session = _mock_session({"ec2": ec2})

    result = run_direct_fix(
        session,
        "ebs_default_encryption",
        "123456789012",
        "eu-north-1",
        strategy_id="ebs_enable_default_encryption_customer_kms",
        strategy_inputs={"kms_key_arn": "arn:aws:kms:eu-north-1:123:key/abc"},
    )

    assert result.success is True
    assert "EBS default encryption enabled" in result.outcome
    ec2.enable_ebs_encryption_by_default.assert_called_once()
    ec2.modify_ebs_default_kms_key_id.assert_called_once_with(
        KmsKeyId="arn:aws:kms:eu-north-1:123:key/abc"
    )


def test_ebs_default_encryption_customer_kms_missing_input() -> None:
    """Customer KMS strategy requires kms_key_arn input."""
    ec2 = MagicMock()
    ec2.get_ebs_encryption_by_default.return_value = {"EbsEncryptionByDefault": False}
    session = _mock_session({"ec2": ec2})

    result = run_direct_fix(
        session,
        "ebs_default_encryption",
        "123456789012",
        "eu-north-1",
        strategy_id="ebs_enable_default_encryption_customer_kms",
        strategy_inputs={},
    )

    assert result.success is False
    assert "kms_key_arn is required" in result.outcome


# ---------------------------------------------------------------------------
# DirectFixResult
# ---------------------------------------------------------------------------
def test_direct_fix_result_log_text() -> None:
    """log_text joins logs with newlines."""
    r = DirectFixResult(success=True, outcome="OK", logs=["a", "b", "c"])
    assert r.log_text() == "a\nb\nc"


# ---------------------------------------------------------------------------
# run_remediation_preview (Step 8.4)
# ---------------------------------------------------------------------------
def test_remediation_preview_s3_already_compliant() -> None:
    """Preview returns compliant=True when S3 Block Public Access already enabled."""
    s3c = MagicMock()
    s3c.get_public_access_block.return_value = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }
    session = _mock_session({"s3control": s3c})

    result = run_remediation_preview(session, "s3_block_public_access", "123456789012", None)

    assert result.compliant is True
    assert result.will_apply is False
    assert "already" in result.message.lower()


def test_remediation_preview_unsupported_type() -> None:
    """Preview for unsupported action_type returns will_apply=False."""
    session = _mock_session({})
    result = run_remediation_preview(session, "unknown", "123456789012", "us-east-1")
    assert result.compliant is False
    assert result.will_apply is False
