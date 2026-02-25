from __future__ import annotations

import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from backend.services.control_scope import unsupported_control_decision
from backend.workers.services.inventory_reconcile import (
    INVENTORY_SERVICES_DEFAULT,
    _policy_has_ssl_deny,
    _s3_bucket_has_valid_lifecycle_rule,
    collect_inventory_snapshots,
)
from scripts.run_no_ui_pr_bundle_agent import _reconcile_services_for_control


_FINDINGS_PRE_RAW_PATH = Path("artifacts/no-ui-agent/20260220T022820Z/findings_pre_raw.json")


def _identity_from_findings(control_id: str, expected_resource_type: str) -> tuple[str, str, str, str]:
    payload = json.loads(_FINDINGS_PRE_RAW_PATH.read_text(encoding="utf-8"))
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("control_id") or "").upper() != control_id.upper():
            continue
        if str(row.get("resource_type") or "") != expected_resource_type:
            continue
        resource_id = str(row.get("resource_id") or "").strip()
        resource_type = str(row.get("resource_type") or "").strip()
        account_id = str(row.get("account_id") or "").strip()
        region = str(row.get("region") or "").strip()
        if resource_id and resource_type and account_id and region:
            return resource_id, resource_type, account_id, region
    raise AssertionError(
        f"No {expected_resource_type} identity found for {control_id} in {_FINDINGS_PRE_RAW_PATH}"
    )


def _account_id_from_account_resource_id(resource_id: str) -> str:
    prefix = "AWS::::Account:"
    return resource_id[len(prefix) :] if resource_id.startswith(prefix) else resource_id


class _FakeSession:
    def __init__(self, clients: dict[str, object]) -> None:
        self._clients = clients

    def client(self, service_name: str, region_name: str | None = None):
        return self._clients[service_name]


class _FakeEc2:
    def describe_security_groups(self, GroupIds):  # noqa: N803
        group_id = GroupIds[0]
        if group_id == "sg-missing":
            raise ClientError(
                {
                    "Error": {
                        "Code": "InvalidGroup.NotFound",
                        "Message": "group does not exist",
                    }
                },
                "DescribeSecurityGroups",
            )
        return {
            "SecurityGroups": [
                {
                    "GroupId": group_id,
                    "VpcId": "vpc-1",
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": 22,
                            "ToPort": 22,
                            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                            "Ipv6Ranges": [],
                        }
                    ],
                }
            ]
        }

    def get_ebs_encryption_by_default(self):
        return {"EbsEncryptionByDefault": True}

    def get_snapshot_block_public_access_state(self):
        return {"State": "block-all-sharing"}


class _FakeEc2TrackCalls:
    def __init__(self) -> None:
        self.group_ids: list[str] = []

    def describe_security_groups(self, GroupIds):  # noqa: N803
        group_id = str(GroupIds[0])
        self.group_ids.append(group_id)
        return {
            "SecurityGroups": [
                {
                    "GroupId": group_id,
                    "VpcId": "vpc-1",
                    "IpPermissions": [],
                }
            ]
        }


class _FakeEc2SnapshotAccessDenied(_FakeEc2):
    def get_snapshot_block_public_access_state(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetSnapshotBlockPublicAccessState",
        )


class _FakeEc2SnapshotUnsupportedOperation(_FakeEc2):
    def get_snapshot_block_public_access_state(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "UnsupportedOperationException",
                    "Message": "unsupported",
                }
            },
            "GetSnapshotBlockPublicAccessState",
        )


class _FakeEc2SnapshotThrottling(_FakeEc2):
    def get_snapshot_block_public_access_state(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "slow down",
                }
            },
            "GetSnapshotBlockPublicAccessState",
        )


class _FakeEc2SnapshotUnknownError(_FakeEc2):
    def get_snapshot_block_public_access_state(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "InternalError",
                    "Message": "internal",
                }
            },
            "GetSnapshotBlockPublicAccessState",
        )


class _FakeS3:
    def list_buckets(self):
        return {"Buckets": []}


class _FakeS3SingleBucket:
    def __init__(
        self,
        bucket: str,
        region: str,
        encryption_rules: list[dict[str, object]] | None = None,
        logging_enabled: dict[str, object] | None = None,
    ) -> None:
        self.bucket = bucket
        self.region = region
        self.encryption_rules = (
            encryption_rules
            if encryption_rules is not None
            else [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
        )
        self.logging_enabled = (
            logging_enabled
            if logging_enabled is not None
            else {
                "TargetBucket": "logs-target",
                "TargetPrefix": "access/",
            }
        )

    def list_buckets(self):
        return {"Buckets": [{"Name": self.bucket}]}

    def get_bucket_location(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"LocationConstraint": self.region}

    def get_public_access_block(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_policy_status(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"PolicyStatus": {"IsPublic": False}}

    def get_bucket_encryption(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": self.encryption_rules
            }
        }

    def get_bucket_logging(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {
            "LoggingEnabled": self.logging_enabled
        }

    def get_bucket_lifecycle_configuration(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {
            "Rules": [
                {
                    "Status": "Enabled",
                    "Expiration": {"Days": 30},
                }
            ]
        }

    def get_bucket_policy(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        bucket_arn = f"arn:aws:s3:::{self.bucket}"
        object_arn = f"{bucket_arn}/*"
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [bucket_arn, object_arn],
                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                }
            ],
        }
        return {"Policy": json.dumps(policy)}


class _FakeS3Control:
    def get_public_access_block(self, AccountId):  # noqa: N803
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }


class _FakeGuardDuty:
    def list_detectors(self):
        return {"DetectorIds": ["det-1"]}

    def get_detector(self, DetectorId):  # noqa: N803
        return {"Status": "ENABLED"}


class _FakeGuardDutyPaginated:
    def __init__(self) -> None:
        self.list_calls = 0
        self.processed_detector_ids: list[str] = []

    def list_detectors(self, NextToken=None):  # noqa: N803
        self.list_calls += 1
        if NextToken:
            return {"DetectorIds": ["det-2"]}
        return {"DetectorIds": ["det-1"], "NextToken": "token-2"}

    def get_detector(self, DetectorId):  # noqa: N803
        self.processed_detector_ids.append(str(DetectorId))
        return {"Status": "ENABLED"}


class _FakeGuardDutyDetectorAccessDenied:
    def __init__(self) -> None:
        self.processed_detector_ids: list[str] = []

    def list_detectors(self, NextToken=None):  # noqa: N803
        del NextToken
        return {"DetectorIds": ["det-1"]}

    def get_detector(self, DetectorId):  # noqa: N803
        self.processed_detector_ids.append(str(DetectorId))
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetDetector",
        )


class _FakeConfig:
    def describe_configuration_recorders(self):
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "roleARN": "arn:aws:iam::123456789012:role/service-role/config",
                    "recordingGroup": {"allSupported": True, "resourceTypes": []},
                }
            ]
        }

    def describe_configuration_recorder_status(self):
        return {"ConfigurationRecordersStatus": [{"name": "default", "recording": True}]}

    def describe_delivery_channels(self):
        return {"DeliveryChannels": [{"name": "default", "s3BucketName": "config-delivery-bucket"}]}


class _FakeConfigNotRecording(_FakeConfig):
    def describe_configuration_recorder_status(self):
        return {"ConfigurationRecordersStatus": [{"name": "default", "recording": False}]}


class _FakeConfigNoDeliveryChannel(_FakeConfig):
    def describe_delivery_channels(self):
        return {"DeliveryChannels": []}


class _FakeConfigAccessDenied(_FakeConfig):
    def describe_configuration_recorder_status(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "DescribeConfigurationRecorderStatus",
        )


class _FakeSsm:
    def get_service_setting(self, SettingId):  # noqa: N803
        return {"ServiceSetting": {"SettingValue": "false"}}


class _FakeSsmAccessDenied:
    def get_service_setting(self, SettingId):  # noqa: N803
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetServiceSetting",
        )


class _FakeSsmUnsupportedOperation:
    def get_service_setting(self, SettingId):  # noqa: N803
        raise ClientError(
            {
                "Error": {
                    "Code": "UnsupportedOperationException",
                    "Message": "unsupported",
                }
            },
            "GetServiceSetting",
        )


class _FakeSsmThrottling:
    def get_service_setting(self, SettingId):  # noqa: N803
        raise ClientError(
            {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "slow down",
                }
            },
            "GetServiceSetting",
        )


class _FakeRds:
    def __init__(self, publicly_accessible: bool, storage_encrypted: bool) -> None:
        self.publicly_accessible = publicly_accessible
        self.storage_encrypted = storage_encrypted

    def describe_db_instances(self, DBInstanceIdentifier):  # noqa: N803
        return {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": str(DBInstanceIdentifier),
                    "PubliclyAccessible": self.publicly_accessible,
                    "StorageEncrypted": self.storage_encrypted,
                    "Engine": "postgres",
                    "DBInstanceStatus": "available",
                }
            ]
        }


class _FakeEks:
    def __init__(self, endpoint_public_access: bool, public_access_cidrs: list[str] | None = None) -> None:
        self.endpoint_public_access = endpoint_public_access
        self.public_access_cidrs = list(public_access_cidrs or [])

    def describe_cluster(self, name):  # noqa: N803
        return {
            "cluster": {
                "name": str(name),
                "resourcesVpcConfig": {
                    "endpointPublicAccess": self.endpoint_public_access,
                    "endpointPrivateAccess": not self.endpoint_public_access,
                    "publicAccessCidrs": self.public_access_cidrs,
                },
            }
        }


class _FakeSecurityHub:
    def describe_hub(self):
        return {"HubArn": "arn:aws:securityhub:eu-north-1:123456789012:hub/default"}


class _FakeCloudTrailAccessDenied:
    def __init__(self) -> None:
        self.include_shadow_trails: bool | None = None

    def describe_trails(self, includeShadowTrails):  # noqa: N803
        self.include_shadow_trails = bool(includeShadowTrails)
        return {
            "trailList": [
                {
                    "Name": "org-trail",
                    "IsMultiRegionTrail": True,
                }
            ]
        }

    def get_trail_status(self, Name):  # noqa: N803
        del Name
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetTrailStatus",
        )


class _FakeCloudTrailIncludeShadow:
    def __init__(self) -> None:
        self.include_shadow_trails: bool | None = None

    def describe_trails(self, includeShadowTrails):  # noqa: N803
        self.include_shadow_trails = bool(includeShadowTrails)
        return {
            "trailList": [
                {
                    "Name": "org-trail",
                    "IsMultiRegionTrail": True,
                }
            ]
        }

    def get_trail_status(self, Name):  # noqa: N803
        del Name
        return {"IsLogging": True}


class _FakeS3Lifecycle:
    def __init__(self, rules: list[dict[str, object]]) -> None:
        self.rules = rules

    def get_bucket_lifecycle_configuration(self, Bucket):  # noqa: N803
        del Bucket
        return {"Rules": self.rules}


def test_collect_inventory_snapshots_unknown_service_returns_empty() -> None:
    session = _FakeSession(clients={})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="unknown",
    )
    assert snapshots == []


def test_collect_inventory_snapshots_ec2_skips_missing_ids_and_evaluates_found() -> None:
    session = _FakeSession(clients={"ec2": _FakeEc2()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="ec2",
        resource_ids=["sg-missing", "sg-123"],
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == "sg-123"
    assert snapshot.service == "ec2"
    assert len(snapshot.evaluations) == 1
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "EC2.53"
    assert evaluation.status == "OPEN"


def test_ec2_53_raw_sg_id_is_accepted() -> None:
    ec2 = _FakeEc2TrackCalls()
    session = _FakeSession(clients={"ec2": ec2})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="ec2",
        resource_ids=["sg-abc123"],
    )

    assert ec2.group_ids == ["sg-abc123"]
    assert len(snapshots) == 1
    assert snapshots[0].resource_id == "sg-abc123"
    assert snapshots[0].evaluations[0].control_id == "EC2.53"


def test_ec2_53_arn_form_sg_id_is_normalized() -> None:
    ec2 = _FakeEc2TrackCalls()
    session = _FakeSession(clients={"ec2": ec2})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="ec2",
        resource_ids=["arn:aws:ec2:eu-north-1:029037611564:security-group/sg-abc123"],
    )

    assert ec2.group_ids == ["sg-abc123"]
    assert len(snapshots) == 1
    assert snapshots[0].resource_id == "sg-abc123"
    assert snapshots[0].evaluations[0].control_id == "EC2.53"


def test_ec2_53_invalid_input_is_dropped_not_raised(caplog) -> None:
    ec2 = _FakeEc2TrackCalls()
    session = _FakeSession(clients={"ec2": ec2})
    with caplog.at_level("WARNING"):
        snapshots = collect_inventory_snapshots(
            session_boto=session,
            account_id="123456789012",
            region="eu-north-1",
            service="ec2",
            resource_ids=["invalid-security-group-id"],
        )

    assert snapshots == []
    assert ec2.group_ids == []
    assert any(
        "Skipping unsupported EC2.53 resource identifier during targeted reconcile"
        in record.message
        for record in caplog.records
    )


def test_ec2_7_ec2_182_route_to_ebs_and_emit_account_identity() -> None:
    ec27_resource_id, ec27_resource_type, account_id, region = _identity_from_findings("EC2.7", "AwsAccount")
    (
        ec2182_account_resource_id,
        ec2182_account_resource_type,
        ec2182_account_id,
        ec2182_account_region,
    ) = _identity_from_findings("EC2.182", "AwsAccount")
    (
        ec2182_arn_resource_id,
        ec2182_arn_resource_type,
        ec2182_arn_account_id,
        ec2182_arn_region,
    ) = _identity_from_findings("EC2.182", "AwsEc2SnapshotBlockPublicAccess")

    assert ec2182_account_id == account_id
    assert ec2182_account_region == region
    assert ec2182_arn_account_id == account_id
    assert ec2182_arn_region == region

    expected_arn = f"arn:aws:ec2:{region}:{account_id}:snapshotblockpublicaccess/{account_id}"
    assert ec2182_arn_resource_id == expected_arn
    assert ec2182_arn_resource_type == "AwsEc2SnapshotBlockPublicAccess"

    assert _reconcile_services_for_control("EC2.7") == ["ebs"]
    assert _reconcile_services_for_control("EC2.182") == ["ebs"]
    assert _reconcile_services_for_control("EC2.7") != ["ec2"]
    assert _reconcile_services_for_control("EC2.182") != ["ec2"]

    session = _FakeSession(clients={"ec2": _FakeEc2()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ebs",
    )
    assert len(snapshots) == 2

    snapshots_by_identity = {
        (snapshot.resource_type, snapshot.resource_id): snapshot
        for snapshot in snapshots
    }
    assert (ec27_resource_type, ec27_resource_id) in snapshots_by_identity
    assert (ec2182_arn_resource_type, ec2182_arn_resource_id) in snapshots_by_identity

    account_snapshot = snapshots_by_identity[(ec27_resource_type, ec27_resource_id)]
    arn_snapshot = snapshots_by_identity[(ec2182_arn_resource_type, ec2182_arn_resource_id)]

    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    ec2182_evals = [evaluation for evaluation in evaluations if evaluation.control_id == "EC2.182"]
    assert len(ec2182_evals) == 2
    assert {evaluation.resource_type for evaluation in ec2182_evals} == {
        ec2182_account_resource_type,
        ec2182_arn_resource_type,
    }
    assert {evaluation.resource_id for evaluation in ec2182_evals} == {
        ec2182_account_resource_id,
        ec2182_arn_resource_id,
    }
    assert len({evaluation.status for evaluation in ec2182_evals}) == 1

    account_evaluations = {evaluation.control_id: evaluation for evaluation in account_snapshot.evaluations}
    assert account_evaluations["EC2.7"].resource_id == ec27_resource_id
    assert account_evaluations["EC2.7"].resource_type == ec27_resource_type

    assert len(arn_snapshot.evaluations) == 1
    assert arn_snapshot.evaluations[0].control_id == "EC2.182"
    assert arn_snapshot.evaluations[0].resource_id == ec2182_arn_resource_id
    assert arn_snapshot.evaluations[0].resource_type == ec2182_arn_resource_type


def test_ec2_182_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"ec2": _FakeEc2SnapshotAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ebs",
    )

    ec2182_evals = [
        evaluation
        for snapshot in snapshots
        for evaluation in snapshot.evaluations
        if evaluation.control_id == "EC2.182"
    ]
    assert len(ec2182_evals) == 2
    assert {evaluation.status for evaluation in ec2182_evals} == {"SOFT_RESOLVED"}
    assert {evaluation.state_confidence for evaluation in ec2182_evals} == {40}
    assert {evaluation.status_reason for evaluation in ec2182_evals} == {
        "inventory_access_denied_ec2_snapshot_block_public_access"
    }


def test_ec2_182_unsupported_operation_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"ec2": _FakeEc2SnapshotUnsupportedOperation()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ebs",
    )

    ec2182_evals = [
        evaluation
        for snapshot in snapshots
        for evaluation in snapshot.evaluations
        if evaluation.control_id == "EC2.182"
    ]
    assert len(ec2182_evals) == 2
    assert {evaluation.status for evaluation in ec2182_evals} == {"SOFT_RESOLVED"}
    assert {evaluation.state_confidence for evaluation in ec2182_evals} == {40}
    assert {evaluation.status_reason for evaluation in ec2182_evals} == {
        "inventory_unsupported_operation_ec2_snapshot_block_public_access"
    }


def test_ec2_182_throttling_is_reraised() -> None:
    session = _FakeSession(clients={"ec2": _FakeEc2SnapshotThrottling()})
    with pytest.raises(ClientError):
        collect_inventory_snapshots(
            session_boto=session,
            account_id="123456789012",
            region="eu-north-1",
            service="ebs",
        )


def test_ec2_182_unknown_error_is_reraised() -> None:
    session = _FakeSession(clients={"ec2": _FakeEc2SnapshotUnknownError()})
    with pytest.raises(ClientError):
        collect_inventory_snapshots(
            session_boto=session,
            account_id="123456789012",
            region="eu-north-1",
            service="ebs",
        )


def test_collect_inventory_snapshots_config_1_emits_account_identity() -> None:
    finding_resource_id, finding_resource_type, account_id, region = _identity_from_findings("Config.1", "AwsAccount")
    assert finding_resource_type == "AwsAccount"
    assert _account_id_from_account_resource_id(finding_resource_id) == account_id

    session = _FakeSession(clients={"config": _FakeConfig()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="config",
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"
    assert snapshot.resource_id != f"{account_id}:{region}"

    assert len(snapshot.evaluations) == 1
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "Config.1"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"


def test_config_1_recorder_exists_but_not_recording_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"config": _FakeConfigNotRecording()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "Config.1"
    assert evaluation.status == "OPEN"


def test_config_1_no_delivery_channel_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"config": _FakeConfigNoDeliveryChannel()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "Config.1"
    assert evaluation.status == "OPEN"
    assert bool((evaluation.evidence_ref or {}).get("delivery_channel_present")) is False


def test_config_1_full_coverage_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"config": _FakeConfig()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "Config.1"
    assert evaluation.status == "RESOLVED"
    assert bool((evaluation.evidence_ref or {}).get("recorder_has_role_arn")) is True
    assert bool((evaluation.evidence_ref or {}).get("recorder_has_resource_coverage")) is True
    assert bool((evaluation.evidence_ref or {}).get("delivery_channel_configured")) is True


def test_config_1_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"config": _FakeConfigAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "Config.1"
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.state_confidence == 40
    assert evaluation.status_reason == "inventory_access_denied_config_describe_configuration_recorder_status"


def test_collect_inventory_snapshots_ssm_7_emits_account_identity() -> None:
    finding_resource_id, finding_resource_type, account_id, region = _identity_from_findings("SSM.7", "AwsAccount")
    assert finding_resource_type == "AwsAccount"
    assert _account_id_from_account_resource_id(finding_resource_id) == account_id

    session = _FakeSession(clients={"ssm": _FakeSsm()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ssm",
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"
    assert snapshot.resource_id != f"{account_id}:{region}"

    assert len(snapshot.evaluations) == 1
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "SSM.7"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"


def test_ssm_7_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"ssm": _FakeSsmAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ssm",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "SSM.7"
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.state_confidence == 40
    assert evaluation.status_reason == "inventory_access_denied_ssm_get_service_setting"


def test_ssm_7_unsupported_operation_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"ssm": _FakeSsmUnsupportedOperation()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ssm",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "SSM.7"
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.state_confidence == 40
    assert evaluation.status_reason == "inventory_unsupported_operation_ssm_default_host_management"


def test_ssm_7_throttling_is_reraised() -> None:
    session = _FakeSession(clients={"ssm": _FakeSsmThrottling()})
    with pytest.raises(ClientError):
        collect_inventory_snapshots(
            session_boto=session,
            account_id="123456789012",
            region="eu-north-1",
            service="ssm",
        )


def test_rds_public_access_is_open_and_explicitly_unsupported() -> None:
    session = _FakeSession(clients={"rds": _FakeRds(publicly_accessible=True, storage_encrypted=False)})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="rds",
        resource_ids=["db-public"],
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == "db-public"
    assert snapshot.resource_type == "AwsRdsDbInstance"

    evaluation = next(item for item in snapshot.evaluations if item.control_id == "RDS.PUBLIC_ACCESS")
    assert evaluation.status == "OPEN"

    decision = unsupported_control_decision("RDS.PUBLIC_ACCESS")
    assert decision is not None
    assert evaluation.evidence_ref.get("support_status") == decision["support_status"]
    assert evaluation.evidence_ref.get("remediation_classification") == decision["remediation_classification"]
    assert evaluation.evidence_ref.get("action_type") == decision["action_type"]
    assert evaluation.evidence_ref.get("support_reason") == decision["reason"]


def test_rds_encryption_is_resolved_and_explicitly_unsupported() -> None:
    session = _FakeSession(clients={"rds": _FakeRds(publicly_accessible=False, storage_encrypted=True)})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="rds",
        resource_ids=["db-encrypted"],
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    evaluation = next(item for item in snapshot.evaluations if item.control_id == "RDS.ENCRYPTION")
    assert evaluation.status == "RESOLVED"
    assert evaluation.severity_label == "MEDIUM"

    decision = unsupported_control_decision("RDS.ENCRYPTION")
    assert decision is not None
    assert evaluation.evidence_ref.get("support_status") == decision["support_status"]
    assert evaluation.evidence_ref.get("remediation_classification") == decision["remediation_classification"]
    assert evaluation.evidence_ref.get("action_type") == decision["action_type"]
    assert evaluation.evidence_ref.get("support_reason") == decision["reason"]


def test_eks_public_endpoint_world_exposed_is_open_and_explicitly_unsupported() -> None:
    session = _FakeSession(clients={"eks": _FakeEks(endpoint_public_access=True, public_access_cidrs=["0.0.0.0/0"])})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="eks",
        resource_ids=["cluster-world-open"],
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == "cluster-world-open"
    assert snapshot.resource_type == "AwsEksCluster"
    assert len(snapshot.evaluations) == 1

    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "EKS.PUBLIC_ENDPOINT"
    assert evaluation.status == "OPEN"

    decision = unsupported_control_decision("EKS.PUBLIC_ENDPOINT")
    assert decision is not None
    assert evaluation.evidence_ref.get("support_status") == decision["support_status"]
    assert evaluation.evidence_ref.get("remediation_classification") == decision["remediation_classification"]
    assert evaluation.evidence_ref.get("action_type") == decision["action_type"]
    assert evaluation.evidence_ref.get("support_reason") == decision["reason"]


def test_eks_public_endpoint_restricted_cidrs_is_resolved_and_still_unsupported() -> None:
    session = _FakeSession(clients={"eks": _FakeEks(endpoint_public_access=True, public_access_cidrs=["10.0.0.0/8"])})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="eks",
        resource_ids=["cluster-restricted"],
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "EKS.PUBLIC_ENDPOINT"
    assert evaluation.status == "RESOLVED"
    assert evaluation.evidence_ref.get("support_status") == "unsupported"
    assert evaluation.evidence_ref.get("action_type") == "pr_only"


def test_collect_inventory_snapshots_s3_includes_s31_account_evaluation() -> None:
    session = _FakeSession(clients={"s3": _FakeS3(), "s3control": _FakeS3Control()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="s3",
    )
    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "S3.1"
    assert evaluation.status == "RESOLVED"


def test_s3_2_emits_both_bucket_and_account_shaped_evaluations() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-2-bucket"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(bucket=bucket, region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )

    bucket_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_type == "AwsS3Bucket")
    s32_evaluations = [evaluation for evaluation in bucket_snapshot.evaluations if evaluation.control_id == "S3.2"]
    assert len(s32_evaluations) == 2
    assert {(evaluation.resource_type, evaluation.resource_id) for evaluation in s32_evaluations} == {
        ("AwsS3Bucket", f"arn:aws:s3:::{bucket}"),
        ("AwsAccount", account_id),
    }
    assert len({evaluation.status for evaluation in s32_evaluations}) == 1
    assert len({evaluation.status_reason for evaluation in s32_evaluations}) == 1
    assert len({evaluation.state_confidence for evaluation in s32_evaluations}) == 1


def test_s3_5_emits_bucket_shaped_only() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-5-bucket"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(bucket=bucket, region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )

    all_evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s35_evaluations = [evaluation for evaluation in all_evaluations if evaluation.control_id == "S3.5"]
    assert len(s35_evaluations) == 1
    assert s35_evaluations[0].resource_type == "AwsS3Bucket"
    assert s35_evaluations[0].resource_id == f"arn:aws:s3:::{bucket}"


def test_s3_9_logging_enabled_no_target_bucket_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-9-no-target-bucket"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                logging_enabled={"TargetPrefix": "logs/"},
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s39 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.9")
    assert s39.status == "OPEN"


def test_s3_9_logging_enabled_no_target_prefix_key_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-9-no-target-prefix"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                logging_enabled={"TargetBucket": "logs-target"},
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s39 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.9")
    assert s39.status == "OPEN"


def test_s3_9_logging_enabled_empty_prefix_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-9-empty-prefix"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                logging_enabled={"TargetBucket": "logs-target", "TargetPrefix": ""},
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s39 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.9")
    assert s39.status == "RESOLVED"


def test_s3_9_full_logging_config_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-9-full-config"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                logging_enabled={"TargetBucket": "logs-target", "TargetPrefix": "logs/"},
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s39 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.9")
    assert s39.status == "RESOLVED"


def test_s3_15_first_rule_non_kms_later_kms_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-15-later-kms"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}},
                ],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s315 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.15")
    assert s315.status == "RESOLVED"


def test_s3_15_first_rule_kms_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-15-first-kms"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}},
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
                ],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s315 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.15")
    assert s315.status == "RESOLVED"


def test_s3_15_no_kms_rule_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-15-no-kms"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}},
                ],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s315 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.15")
    assert s315.status == "OPEN"


def test_s3_15_case_insensitive_kms_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-15-case-kms"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[
                    {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AWS:KMS"}},
                ],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s315 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.15")
    assert s315.status == "RESOLVED"


def test_s3_4_null_algorithm_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-null"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": None}}],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s34 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.4")
    assert s34.status == "OPEN"
    assert s34.resource_type == "AwsS3Bucket"
    assert s34.resource_id == f"arn:aws:s3:::{bucket}"


def test_s3_4_unapproved_algorithm_is_not_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-unapproved"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "DES3"}}],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s34 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.4")
    assert s34.status == "OPEN"


def test_s3_4_aes256_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-aes256"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s34 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.4")
    assert s34.status == "RESOLVED"


def test_s3_4_aws_kms_is_compliant() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-kms"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s34 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.4")
    assert s34.status == "RESOLVED"


def test_s3_4_case_insensitive_algorithm_match() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-case"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucket(
                bucket=bucket,
                region=region,
                encryption_rules=[{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AWS:KMS"}}],
            ),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[bucket],
    )
    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    s34 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.4")
    assert s34.status == "RESOLVED"


def test_collect_inventory_snapshots_guardduty_enabled_resolved() -> None:
    session = _FakeSession(clients={"guardduty": _FakeGuardDuty()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="us-east-1",
        service="guardduty",
    )
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == "123456789012"
    assert snapshot.resource_type == "AwsAccount"
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "GuardDuty.1"
    assert evaluation.resource_id == "123456789012"
    assert evaluation.resource_type == "AwsAccount"
    assert evaluation.status == "RESOLVED"


def test_guardduty_paginates_detector_list() -> None:
    client = _FakeGuardDutyPaginated()
    session = _FakeSession(clients={"guardduty": client})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="us-east-1",
        service="guardduty",
    )

    assert len(snapshots) == 1
    assert client.list_calls == 2
    assert set(client.processed_detector_ids) == {"det-1", "det-2"}
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "RESOLVED"


def test_guardduty_per_detector_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    client = _FakeGuardDutyDetectorAccessDenied()
    session = _FakeSession(clients={"guardduty": client})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region="us-east-1",
        service="guardduty",
    )

    assert len(snapshots) == 1
    assert client.processed_detector_ids == ["det-1"]
    snapshot = snapshots[0]
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "GuardDuty.1"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_guardduty_get_detector"
    assert evaluation.state_confidence == 40


def test_collect_inventory_snapshots_securityhub_1_emits_account_identity() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    assert "securityhub" in INVENTORY_SERVICES_DEFAULT

    session = _FakeSession(clients={"securityhub": _FakeSecurityHub()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="securityhub",
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.service == "securityhub"
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"

    assert len(snapshot.evaluations) == 1
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "SecurityHub.1"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"
    assert evaluation.status == "RESOLVED"


def test_cloudtrail_per_trail_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    cloudtrail = _FakeCloudTrailAccessDenied()
    session = _FakeSession(clients={"cloudtrail": cloudtrail})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="cloudtrail",
    )

    assert cloudtrail.include_shadow_trails is True
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"
    evaluation = snapshot.evaluations[0]
    assert evaluation.control_id == "CloudTrail.1"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_cloudtrail_get_trail_status"
    assert evaluation.state_confidence == 40


def test_cloudtrail_includes_shadow_trails() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    cloudtrail = _FakeCloudTrailIncludeShadow()
    session = _FakeSession(clients={"cloudtrail": cloudtrail})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="cloudtrail",
    )

    assert cloudtrail.include_shadow_trails is True
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == account_id
    assert snapshot.resource_type == "AwsAccount"
    evaluation = snapshot.evaluations[0]
    assert evaluation.status == "RESOLVED"
    assert evaluation.resource_id == account_id
    assert evaluation.resource_type == "AwsAccount"


def test_ssl_deny_narrow_action_is_not_compliant() -> None:
    policy = {
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": [
                    "arn:aws:s3:::example-bucket",
                    "arn:aws:s3:::example-bucket/*",
                ],
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false",
                    }
                },
            }
        ]
    }
    assert _policy_has_ssl_deny(policy, "example-bucket") is False


def test_ssl_deny_missing_object_resource_is_not_compliant() -> None:
    policy = {
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": "arn:aws:s3:::example-bucket",
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false",
                    }
                },
            }
        ]
    }
    assert _policy_has_ssl_deny(policy, "example-bucket") is False


def test_ssl_deny_full_coverage_is_compliant() -> None:
    policy = {
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": "s3:*",
                "Resource": [
                    "arn:aws:s3:::example-bucket",
                    "arn:aws:s3:::example-bucket/*",
                ],
                "Condition": {
                    "Bool": {
                        "aws:SecureTransport": "false",
                    }
                },
            }
        ]
    }
    assert _policy_has_ssl_deny(policy, "example-bucket") is True


def test_ssl_deny_case_insensitive_condition_key() -> None:
    policy = {
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": "*",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": [
                    "arn:aws:s3:::example-bucket",
                    "arn:aws:s3:::example-bucket/*",
                ],
                "Condition": {
                    "bool": {
                        "AWS:SecureTransport": "FALSE",
                    }
                },
            }
        ]
    }
    assert _policy_has_ssl_deny(policy, "example-bucket") is True


def test_s3_lifecycle_no_rules_is_not_compliant() -> None:
    s3 = _FakeS3Lifecycle([])
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is False


def test_s3_lifecycle_disabled_rule_is_not_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Disabled",
                "Expiration": {"Days": 30},
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is False


def test_s3_lifecycle_enabled_rule_no_action_is_not_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Enabled",
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is False


def test_s3_lifecycle_enabled_rule_with_expiration_is_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Enabled",
                "Expiration": {"Days": 30},
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is True


def test_s3_lifecycle_enabled_rule_with_transitions_is_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Enabled",
                "Transitions": [{"Days": 45, "StorageClass": "GLACIER"}],
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is True
