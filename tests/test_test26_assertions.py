"""Deterministic regression tests for Wave 7 Test 26 assertion helpers."""
from __future__ import annotations

from backend.services.test26_assertions import (
    build_precondition_risk_state,
    evaluate_visibility_track,
    summarize_policy_preservation,
)


def test_precondition_risk_state_confirms_expected_adversarial_setup() -> None:
    policy_doc = {
        "Statement": [
            {"Sid": "AllowCrossAccountRead", "Action": "s3:GetObject"},
            {"Sid": "AllowDataPipelinePutObject", "Action": "s3:PutObject"},
            {"Sid": "AllowVpcScopedReadPath", "Condition": {"StringEquals": {"aws:SourceVpc": "vpc-123"}}},
        ]
    }
    pab_doc = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": False,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        }
    }

    summary = build_precondition_risk_state(policy_doc, pab_doc)
    assert summary["adversarial_state_confirmed"] is True


def test_precondition_risk_state_fails_when_pab_not_fully_open() -> None:
    policy_doc = {
        "Statement": [{"Sid": "AllowDataPipelinePutObject", "Action": "s3:PutObject"}]
    }
    pab_doc = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": False,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": False,
        }
    }

    summary = build_precondition_risk_state(policy_doc, pab_doc)
    assert summary["adversarial_state_confirmed"] is False


def test_policy_preservation_keeps_non_risk_statements_when_only_cloudfront_rotates() -> None:
    policy_pre = {
        "Statement": [
            {"Sid": "AllowCrossAccountRead", "Action": "s3:GetObject"},
            {
                "Sid": "AllowCloudFrontReadOnly",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Condition": {"StringEquals": {"AWS:SourceArn": "old"}},
            },
        ]
    }
    policy_post = {
        "Statement": [
            {"Sid": "AllowCrossAccountRead", "Action": "s3:GetObject"},
            {
                "Sid": "AllowCloudFrontReadOnly",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Condition": {"StringEquals": {"AWS:SourceArn": "new"}},
            },
        ]
    }
    pab_post = {
        "PublicAccessBlockConfiguration": {
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        }
    }

    summary = summarize_policy_preservation(policy_pre, policy_post, pab_post)
    assert summary["removed_non_risk_statement_count"] == 0
    assert summary["added_non_risk_statement_count"] == 0
    assert summary["non_risk_invariance_pass"] is True
    assert summary["pab_hardened_post_apply"] is True


def test_visibility_track_fails_when_target_never_reappears_in_open() -> None:
    summary = evaluate_visibility_track(
        target_visible_in_open=False,
        elapsed_seconds=180,
        sla_seconds=180,
    )
    assert summary["pass"] is False
    assert summary["reason"] == "target_not_visible_in_open_list"
