"""
Shared control-plane management-event allowlist.

This module is the single source of truth for:
- intake filtering
- worker filtering
- forwarder-template parity tests
"""

from __future__ import annotations

from typing import Final

SUPPORTED_CONTROL_PLANE_DETAIL_TYPE: Final[str] = "AWS API Call via CloudTrail"

SECURITY_GROUP_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "AuthorizeSecurityGroupIngress",
        "RevokeSecurityGroupIngress",
        "ModifySecurityGroupRules",
        "UpdateSecurityGroupRuleDescriptionsIngress",
    }
)

S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "PutBucketPolicy",
        "DeleteBucketPolicy",
        "PutBucketAcl",
        # Bucket-level S3 public access block API names observed in CloudTrail.
        "PutBucketPublicAccessBlock",
        "DeleteBucketPublicAccessBlock",
        # Keep legacy aliases for backward compatibility across mixed forwarder versions.
        "PutPublicAccessBlock",
        "DeletePublicAccessBlock",
    }
)

S3_MANAGEMENT_EVENT_NAMES: frozenset[str] = frozenset(
    set(S3_BUCKET_POSTURE_EVALUATION_EVENT_NAMES)
    | {
        "PutAccountPublicAccessBlock",
        "DeleteAccountPublicAccessBlock",
        "PutBucketEncryption",
        "DeleteBucketEncryption",
    }
)

SECURITY_HUB_EVENT_NAMES: frozenset[str] = frozenset({"EnableSecurityHub"})

GUARDDUTY_EVENT_NAMES: frozenset[str] = frozenset({"CreateDetector", "UpdateDetector"})

CLOUDTRAIL_EVENT_NAMES: frozenset[str] = frozenset(
    {"CreateTrail", "UpdateTrail", "StartLogging", "StopLogging"}
)

CONFIG_EVENT_NAMES: frozenset[str] = frozenset(
    {"PutConfigurationRecorder", "PutDeliveryChannel", "StartConfigurationRecorder"}
)

SUPPORTED_CONTROL_PLANE_EVENT_NAMES: frozenset[str] = frozenset(
    set(SECURITY_GROUP_EVENT_NAMES)
    | set(S3_MANAGEMENT_EVENT_NAMES)
    | set(SECURITY_HUB_EVENT_NAMES)
    | set(GUARDDUTY_EVENT_NAMES)
    | set(CLOUDTRAIL_EVENT_NAMES)
    | set(CONFIG_EVENT_NAMES)
)
