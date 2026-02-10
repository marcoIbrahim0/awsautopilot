from __future__ import annotations

from worker.services.control_plane_events import (
    build_fingerprint,
    evaluate_s3_bucket_public_posture,
    evaluate_security_group_public_admin_ports,
    extract_s3_bucket_names,
    extract_security_group_ids,
    is_supported_management_event,
)


def test_is_supported_management_event_accepts_allowlisted_management_event() -> None:
    event = {
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {"eventName": "AuthorizeSecurityGroupIngress", "eventCategory": "Management"},
    }
    ok, reason = is_supported_management_event(event)
    assert ok is True
    assert reason is None


def test_is_supported_management_event_rejects_data_event() -> None:
    event = {
        "detail-type": "AWS API Call via CloudTrail",
        "detail": {"eventName": "PutObject", "eventCategory": "Data"},
    }
    ok, reason = is_supported_management_event(event)
    assert ok is False
    assert reason == "unsupported_event_name:PutObject"


def test_build_fingerprint_is_deterministic() -> None:
    fp1 = build_fingerprint("123456789012", "us-east-1", "sg-123", "EC2.53")
    fp2 = build_fingerprint("123456789012", "us-east-1", "sg-123", "EC2.53")
    assert fp1 == fp2
    assert fp1 == "123456789012|us-east-1|sg-123|EC2.53"


def test_extract_security_group_ids_from_request_and_resource_arns() -> None:
    event = {
        "resources": [{"ARN": "arn:aws:ec2:us-east-1:123456789012:security-group/sg-abc"}],
        "detail": {
            "requestParameters": {
                "groupId": "sg-def",
                "ipPermissions": {"items": [{"groups": [{"groupId": "sg-ghi"}]}]},
            }
        },
    }
    sg_ids = extract_security_group_ids(event)
    assert sorted(sg_ids) == ["sg-abc", "sg-def", "sg-ghi"]


def test_extract_s3_bucket_names_from_request_and_resource_arns() -> None:
    event = {
        "resources": [{"ARN": "arn:aws:s3:::bucket-from-arn"}],
        "detail": {"requestParameters": {"bucketName": "bucket-from-request"}},
    }
    names = extract_s3_bucket_names(event)
    assert sorted(names) == ["bucket-from-arn", "bucket-from-request"]


def test_evaluate_security_group_public_admin_ports_detects_open_rule() -> None:
    group = {
        "IpPermissions": [
            {
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                "Ipv6Ranges": [],
            }
        ]
    }
    non_compliant, violations = evaluate_security_group_public_admin_ports(group)
    assert non_compliant is True
    assert len(violations) == 1
    assert violations[0]["cidr"] == "0.0.0.0/0"


def test_evaluate_security_group_public_admin_ports_detects_compliant_rules() -> None:
    group = {
        "IpPermissions": [
            {
                "IpProtocol": "tcp",
                "FromPort": 443,
                "ToPort": 443,
                "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                "Ipv6Ranges": [],
            }
        ]
    }
    non_compliant, violations = evaluate_security_group_public_admin_ports(group)
    assert non_compliant is False
    assert violations == []


def test_evaluate_s3_bucket_public_posture_flags_public_or_missing_pab() -> None:
    non_compliant, evidence = evaluate_s3_bucket_public_posture(
        public_access_block={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": False,
            "RestrictPublicBuckets": True,
        },
        policy_is_public=False,
    )
    assert non_compliant is True
    assert evidence["public_access_block"]["BlockPublicPolicy"] is False


def test_evaluate_s3_bucket_public_posture_marks_compliant() -> None:
    non_compliant, evidence = evaluate_s3_bucket_public_posture(
        public_access_block={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
        policy_is_public=False,
    )
    assert non_compliant is False
    assert evidence["policy_is_public"] is False
