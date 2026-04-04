from __future__ import annotations

import json
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from backend.services.control_scope import unsupported_control_decision
from backend.services.remediation_support_bucket import (
    SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS,
    support_bucket_tag_map,
)
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


class _FakeS3SingleBucketTaggedSupportLogSink(_FakeS3SingleBucket):
    def get_bucket_tagging(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        tag_map = support_bucket_tag_map(support_bucket_role=SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS)
        return {
            "TagSet": [{"Key": key, "Value": value} for key, value in tag_map.items()]
        }


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


class _FakeS3ControlAccessDenied:
    def get_public_access_block(self, AccountId):  # noqa: N803
        del AccountId
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetPublicAccessBlock",
        )


class _FakeS3SingleBucketPolicyPublic(_FakeS3SingleBucket):
    def get_bucket_policy_status(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"PolicyStatus": {"IsPublic": True}}


class _FakeS3SingleBucketMissingBucketPab(_FakeS3SingleBucket):
    def get_public_access_block(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        raise ClientError(
            {
                "Error": {
                    "Code": "NoSuchPublicAccessBlockConfiguration",
                    "Message": "missing",
                }
            },
            "GetPublicAccessBlock",
        )


class _FakeS3SingleBucketNoEncryptionConfig(_FakeS3SingleBucket):
    def get_bucket_encryption(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        raise ClientError(
            {
                "Error": {
                    "Code": "ServerSideEncryptionConfigurationNotFoundError",
                    "Message": "missing encryption",
                }
            },
            "GetBucketEncryption",
        )


class _FakeS3SingleBucketEncryptionAccessDenied(_FakeS3SingleBucket):
    def get_bucket_encryption(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetBucketEncryption",
        )


class _FakeS3SingleBucketPolicyMissing(_FakeS3SingleBucket):
    def get_bucket_policy(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        raise ClientError(
            {
                "Error": {
                    "Code": "NoSuchBucketPolicy",
                    "Message": "missing policy",
                }
            },
            "GetBucketPolicy",
        )


class _FakeS3SingleBucketPolicyMalformed(_FakeS3SingleBucket):
    def get_bucket_policy(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"Policy": "{"}


class _FakeS3SingleBucketSkipUnknownTarget(_FakeS3SingleBucket):
    def get_bucket_location(self, Bucket):  # noqa: N803
        if Bucket != self.bucket:
            raise ClientError(
                {
                    "Error": {
                        "Code": "NoSuchBucket",
                        "Message": "missing bucket",
                    }
                },
                "GetBucketLocation",
            )
        return {"LocationConstraint": self.region}


class _FakeS3MultiBucketMixedPublicPosture:
    def __init__(self, region: str) -> None:
        self.region = region
        self.buckets = ["mixed-open-bucket", "mixed-resolved-bucket"]

    def list_buckets(self):
        return {"Buckets": [{"Name": name} for name in self.buckets]}

    def get_bucket_location(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"LocationConstraint": self.region}

    def get_public_access_block(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
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
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"PolicyStatus": {"IsPublic": Bucket == "mixed-open-bucket"}}

    def get_bucket_encryption(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"}}]
            }
        }

    def get_bucket_logging(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"LoggingEnabled": {"TargetBucket": "logs", "TargetPrefix": "access/"}}

    def get_bucket_lifecycle_configuration(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        return {"Rules": [{"Status": "Enabled", "Expiration": {"Days": 30}}]}

    def get_bucket_policy(self, Bucket):  # noqa: N803
        if Bucket not in self.buckets:
            raise AssertionError(f"unexpected bucket {Bucket}")
        bucket_arn = f"arn:aws:s3:::{Bucket}"
        object_arn = f"{bucket_arn}/*"
        return {
            "Policy": json.dumps(
                {
                    "Statement": [
                        {
                            "Effect": "Deny",
                            "Principal": "*",
                            "Action": "s3:*",
                            "Resource": [bucket_arn, object_arn],
                            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                        }
                    ]
                }
            )
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


class _FakeGuardDutyListAccessDenied:
    def list_detectors(self, NextToken=None):  # noqa: N803
        del NextToken
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "ListDetectors",
        )


class _FakeGuardDutyInvalidOnly:
    def __init__(self) -> None:
        self.processed_detector_ids: list[str] = []

    def list_detectors(self, NextToken=None):  # noqa: N803
        del NextToken
        return {"DetectorIds": ["det-invalid-1", "det-invalid-2"]}

    def get_detector(self, DetectorId):  # noqa: N803
        self.processed_detector_ids.append(str(DetectorId))
        raise ClientError(
            {
                "Error": {
                    "Code": "InvalidInputException",
                    "Message": "invalid detector id",
                }
            },
            "GetDetector",
        )


class _FakeGuardDutyMixedDetectorStates:
    def __init__(self) -> None:
        self.processed_detector_ids: list[str] = []

    def list_detectors(self, NextToken=None):  # noqa: N803
        del NextToken
        return {"DetectorIds": ["det-enabled", "det-denied"]}

    def get_detector(self, DetectorId):  # noqa: N803
        detector_id = str(DetectorId)
        self.processed_detector_ids.append(detector_id)
        if detector_id == "det-enabled":
            return {"Status": "ENABLED"}
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "GetDetector",
        )


class _FakeGuardDutyDetectorThrottling:
    def list_detectors(self, NextToken=None):  # noqa: N803
        del NextToken
        return {"DetectorIds": ["det-1"]}

    def get_detector(self, DetectorId):  # noqa: N803
        del DetectorId
        raise ClientError(
            {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "slow down",
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


class _FakeConfigMissingRoleArn(_FakeConfig):
    def describe_configuration_recorders(self):
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "roleARN": "",
                    "recordingGroup": {"allSupported": True, "resourceTypes": []},
                }
            ]
        }


class _FakeConfigMissingResourceCoverage(_FakeConfig):
    def describe_configuration_recorders(self):
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "roleARN": "arn:aws:iam::123456789012:role/service-role/config",
                    "recordingGroup": {"allSupported": False, "resourceTypes": []},
                }
            ]
        }


class _FakeConfigSelectiveResourceScope(_FakeConfig):
    def describe_configuration_recorders(self):
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "roleARN": "arn:aws:iam::123456789012:role/service-role/config",
                    "recordingGroup": {
                        "allSupported": False,
                        "resourceTypes": ["AWS::S3::Bucket"],
                    },
                }
            ]
        }


class _FakeConfigMultiRecorderNameMismatch(_FakeConfig):
    def describe_configuration_recorders(self):
        return {
            "ConfigurationRecorders": [
                {
                    "name": "default-a",
                    "roleARN": "arn:aws:iam::123456789012:role/service-role/config-a",
                    "recordingGroup": {"allSupported": True, "resourceTypes": []},
                },
                {
                    "name": "default-b",
                    "roleARN": "arn:aws:iam::123456789012:role/service-role/config-b",
                    "recordingGroup": {"allSupported": True, "resourceTypes": []},
                },
            ]
        }

    def describe_configuration_recorder_status(self):
        return {"ConfigurationRecordersStatus": [{"name": "unexpected", "recording": True}]}


class _FakeConfigDeliveryChannelAccessDenied(_FakeConfig):
    def describe_delivery_channels(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "DescribeDeliveryChannels",
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


class _FakeSsmSettingValue:
    def __init__(self, setting_value: str | None) -> None:
        self.setting_value = setting_value

    def get_service_setting(self, SettingId):  # noqa: N803
        del SettingId
        return {"ServiceSetting": {"SettingValue": self.setting_value}}


class _FakeSsmMalformedResponse:
    def get_service_setting(self, SettingId):  # noqa: N803
        del SettingId
        return {"ServiceSetting": []}


class _FakeSsmUnknownError:
    def get_service_setting(self, SettingId):  # noqa: N803
        del SettingId
        raise ClientError(
            {
                "Error": {
                    "Code": "InternalError",
                    "Message": "internal",
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


class _FakeSecurityHubNotEnabled:
    def describe_hub(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "ResourceNotFoundException",
                    "Message": "not enabled",
                }
            },
            "DescribeHub",
        )


class _FakeSecurityHubEmptyHubArn:
    def describe_hub(self):
        return {"HubArn": "   "}


class _FakeSecurityHubAccessDenied:
    def describe_hub(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "DescribeHub",
        )


class _FakeSecurityHubThrottling:
    def describe_hub(self):
        raise ClientError(
            {
                "Error": {
                    "Code": "ThrottlingException",
                    "Message": "slow down",
                }
            },
            "DescribeHub",
        )


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


class _FakeCloudTrailDescribeAccessDenied:
    def describe_trails(self, includeShadowTrails):  # noqa: N803
        del includeShadowTrails
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "denied",
                }
            },
            "DescribeTrails",
        )


class _FakeCloudTrailTrailNotFoundOnly:
    def describe_trails(self, includeShadowTrails):  # noqa: N803
        del includeShadowTrails
        return {
            "trailList": [
                {
                    "Name": "missing-trail",
                    "IsMultiRegionTrail": True,
                }
            ]
        }

    def get_trail_status(self, Name):  # noqa: N803
        del Name
        raise ClientError(
            {
                "Error": {
                    "Code": "TrailNotFoundException",
                    "Message": "missing trail",
                }
            },
            "GetTrailStatus",
        )


class _FakeCloudTrailZeroTrails:
    def describe_trails(self, includeShadowTrails):  # noqa: N803
        del includeShadowTrails
        return {"trailList": []}


class _FakeCloudTrailMixedIndeterminate:
    def describe_trails(self, includeShadowTrails):  # noqa: N803
        del includeShadowTrails
        return {
            "trailList": [
                {"Name": "denied-trail", "IsMultiRegionTrail": True},
                {"Name": "missing-trail", "IsMultiRegionTrail": True},
            ]
        }

    def get_trail_status(self, Name):  # noqa: N803
        if Name == "denied-trail":
            raise ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "denied",
                    }
                },
                "GetTrailStatus",
            )
        raise ClientError(
            {
                "Error": {
                    "Code": "TrailNotFoundException",
                    "Message": "missing",
                }
            },
            "GetTrailStatus",
        )


class _FakeCloudTrailStatusThrottling:
    def describe_trails(self, includeShadowTrails):  # noqa: N803
        del includeShadowTrails
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
                    "Code": "ThrottlingException",
                    "Message": "slow down",
                }
            },
            "GetTrailStatus",
        )


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

    assert len(snapshots) == 2
    snapshots_by_id = {snapshot.resource_id: snapshot for snapshot in snapshots}

    deleted_snapshot = snapshots_by_id["sg-missing"]
    assert deleted_snapshot.service == "ec2"
    assert deleted_snapshot.evaluations[0].control_id == "EC2.53"
    assert deleted_snapshot.evaluations[0].status == "RESOLVED"
    assert deleted_snapshot.evaluations[0].status_reason == "inventory_resource_deleted"

    found_snapshot = snapshots_by_id["sg-123"]
    assert found_snapshot.service == "ec2"
    assert len(found_snapshot.evaluations) == 1
    evaluation = found_snapshot.evaluations[0]
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
    assert bool((evaluation.evidence_ref or {}).get("recorder_captures_required_scope")) is True
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


def test_config_1_missing_role_arn_is_open_with_quality_flags() -> None:
    session = _FakeSession(clients={"config": _FakeConfigMissingRoleArn()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 95
    assert evaluation.evidence_ref["recorder_has_role_arn"] is False
    assert evaluation.evidence_ref["recorder_has_resource_coverage"] is True
    assert evaluation.evidence_ref["delivery_channel_configured"] is True
    assert evaluation.evidence_ref["status_access_denied"] is False


def test_config_1_missing_resource_coverage_is_open_with_quality_flags() -> None:
    session = _FakeSession(clients={"config": _FakeConfigMissingResourceCoverage()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 95
    assert evaluation.evidence_ref["recorder_has_role_arn"] is True
    assert evaluation.evidence_ref["recorder_has_resource_coverage"] is False
    assert evaluation.evidence_ref["recorder_captures_required_scope"] is False
    assert evaluation.evidence_ref["delivery_channel_configured"] is True
    assert evaluation.evidence_ref["status_access_denied"] is False


def test_config_1_selective_resource_scope_is_open_even_with_explicit_resource_types() -> None:
    session = _FakeSession(clients={"config": _FakeConfigSelectiveResourceScope()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 95
    assert evaluation.evidence_ref["recorder_has_resource_coverage"] is True
    assert evaluation.evidence_ref["recorder_captures_required_scope"] is False
    assert evaluation.evidence_ref["delivery_channel_configured"] is True
    evaluated = evaluation.evidence_ref["recorders_evaluated"]
    assert isinstance(evaluated, list)
    assert evaluated[0]["has_resource_coverage"] is True
    assert evaluated[0]["captures_required_scope"] is False


def test_config_1_multi_recorder_name_mismatch_is_open_with_ambiguous_recording_state() -> None:
    session = _FakeSession(clients={"config": _FakeConfigMultiRecorderNameMismatch()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_partial_data_config_recorder_status_mismatch"
    assert evaluation.state_confidence == 50
    assert evaluation.evidence_ref["recorder_count"] == 2
    assert evaluation.evidence_ref["recorder_status_count"] == 1
    assert evaluation.evidence_ref["recording"] is True
    assert evaluation.evidence_ref["recorder_quality_passed"] is False
    assert evaluation.evidence_ref["status_branch"] == "partial_data_recorder_status_mismatch"
    assert evaluation.evidence_ref["recorder_status_name_mismatch_count"] == 2
    evaluated = evaluation.evidence_ref["recorders_evaluated"]
    assert isinstance(evaluated, list)
    assert len(evaluated) == 2
    assert all(bool((item or {}).get("recording")) is False for item in evaluated)


def test_config_1_delivery_channel_access_denied_is_reraised() -> None:
    session = _FakeSession(clients={"config": _FakeConfigDeliveryChannelAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="config",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_config_describe_delivery_channels"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["delivery_access_denied"] is True
    assert evaluation.evidence_ref["delivery_error_code"] == "AccessDeniedException"
    assert evaluation.evidence_ref["read_access_denied"] is True
    assert evaluation.evidence_ref["status_branch"] == "access_denied_describe_delivery_channels"


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


@pytest.mark.parametrize("setting_value", ["enabled", "true", "1", "on"])
def test_ssm_7_enabled_tokens_emit_open(setting_value: str) -> None:
    session = _FakeSession(clients={"ssm": _FakeSsmSettingValue(setting_value)})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="ssm",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 90
    assert {
        "source",
        "setting_id",
        "setting_value",
        "setting_value_present",
        "api_supported",
        "access_denied",
        "unsupported_operation",
        "partial_data",
        "api_error",
        "error_code",
        "status_branch",
    }.issubset(set((evaluation.evidence_ref or {}).keys()))
    assert evaluation.evidence_ref["setting_value"] == setting_value
    assert evaluation.evidence_ref["setting_value_present"] is True
    assert evaluation.evidence_ref["api_supported"] is True
    assert evaluation.evidence_ref["access_denied"] is False
    assert evaluation.evidence_ref["unsupported_operation"] is False
    assert evaluation.evidence_ref["partial_data"] is False
    assert evaluation.evidence_ref["api_error"] is False
    assert evaluation.evidence_ref["error_code"] is None
    assert evaluation.evidence_ref["status_branch"] == "normal"


def test_ssm_7_resolved_token_and_malformed_shape_stay_resolved() -> None:
    resolved_session = _FakeSession(clients={"ssm": _FakeSsmSettingValue("false")})
    resolved_snapshots = collect_inventory_snapshots(
        session_boto=resolved_session,
        account_id="123456789012",
        region="eu-north-1",
        service="ssm",
    )
    resolved_eval = resolved_snapshots[0].evaluations[0]
    assert resolved_eval.status == "RESOLVED"
    assert resolved_eval.status_reason == "inventory_confirmed_compliant"
    assert resolved_eval.state_confidence == 90
    assert resolved_eval.evidence_ref["setting_value"] == "false"

    malformed_session = _FakeSession(clients={"ssm": _FakeSsmMalformedResponse()})
    malformed_snapshots = collect_inventory_snapshots(
        session_boto=malformed_session,
        account_id="123456789012",
        region="eu-north-1",
        service="ssm",
    )
    malformed_eval = malformed_snapshots[0].evaluations[0]
    assert malformed_eval.status == "SOFT_RESOLVED"
    assert malformed_eval.status_reason == "inventory_partial_data_ssm_get_service_setting"
    assert malformed_eval.state_confidence == 50
    assert malformed_eval.evidence_ref["setting_value"] is None
    assert malformed_eval.evidence_ref["api_supported"] is True
    assert malformed_eval.evidence_ref["access_denied"] is False
    assert malformed_eval.evidence_ref["unsupported_operation"] is False
    assert malformed_eval.evidence_ref["partial_data"] is True
    assert malformed_eval.evidence_ref["api_error"] is False
    assert malformed_eval.evidence_ref["error_code"] is None
    assert malformed_eval.evidence_ref["status_branch"] == "partial_data"


def test_ssm_7_unknown_error_is_reraised() -> None:
    session = _FakeSession(clients={"ssm": _FakeSsmUnknownError()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="ssm",
    )
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_api_error_ssm_get_service_setting"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["api_supported"] is False
    assert evaluation.evidence_ref["api_error"] is True
    assert evaluation.evidence_ref["error_code"] == "InternalError"
    assert evaluation.evidence_ref["status_branch"] == "api_error"


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


def test_s3_2_public_policy_emits_open_with_dual_shape_confidence_and_evidence() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-2-public-policy"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketPolicyPublic(bucket=bucket, region=region),
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
    s32 = [evaluation for evaluation in evaluations if evaluation.control_id == "S3.2"]
    assert len(s32) == 2
    assert {evaluation.status for evaluation in s32} == {"OPEN"}
    assert {evaluation.status_reason for evaluation in s32} == {"inventory_confirmed_non_compliant"}
    assert {evaluation.state_confidence for evaluation in s32} == {95}
    assert {evaluation.resource_type for evaluation in s32} == {"AwsS3Bucket", "AwsAccount"}
    for evaluation in s32:
        assert {
            "source",
            "probe_branch",
            "access_denied_error_codes",
            "api_error_codes",
            "policy_is_public",
            "public_access_block",
        }.issubset(set(evaluation.evidence_ref.keys()))
        assert evaluation.evidence_ref["source"] == "inventory"
        assert evaluation.evidence_ref["probe_branch"] == "normal"
        assert evaluation.evidence_ref["access_denied_error_codes"] == []
        assert evaluation.evidence_ref["api_error_codes"] == []
        assert evaluation.evidence_ref["policy_is_public"] is True
        assert set((evaluation.evidence_ref["public_access_block"] or {}).keys()) == {
            "BlockPublicAcls",
            "IgnorePublicAcls",
            "BlockPublicPolicy",
            "RestrictPublicBuckets",
        }


def test_s3_2_missing_bucket_public_access_block_emits_open() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-2-missing-pab"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketMissingBucketPab(bucket=bucket, region=region),
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
    s32 = [evaluation for evaluation in evaluations if evaluation.control_id == "S3.2"]
    assert len(s32) == 2
    assert {evaluation.status for evaluation in s32} == {"OPEN"}
    assert {evaluation.status_reason for evaluation in s32} == {"inventory_confirmed_non_compliant"}
    assert {evaluation.state_confidence for evaluation in s32} == {95}


def test_s3_targeted_account_resource_id_keeps_account_eval_and_skips_bucket_eval() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "known-bucket"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketSkipUnknownTarget(bucket=bucket, region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[f"AWS::::Account:{account_id}"],
    )

    assert len(snapshots) == 1
    assert snapshots[0].resource_type == "AwsAccount"
    assert len(snapshots[0].evaluations) == 1
    s31 = snapshots[0].evaluations[0]
    assert s31.control_id == "S3.1"
    assert s31.status == "RESOLVED"
    assert s31.status_reason == "inventory_confirmed_compliant"
    assert s31.state_confidence == 95
    assert set((s31.evidence_ref or {}).keys()) == {"source", "public_access_block", "probe_ok"}


def test_s3_targeted_missing_bucket_emits_deleted_resource_snapshot() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "known-bucket"
    missing_bucket = "missing-bucket"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketSkipUnknownTarget(bucket=bucket, region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
        resource_ids=[missing_bucket],
    )

    assert len(snapshots) == 2
    deleted_snapshot = next(snapshot for snapshot in snapshots if snapshot.resource_type == "AwsS3Bucket")
    assert deleted_snapshot.resource_id == f"arn:aws:s3:::{missing_bucket}"
    assert deleted_snapshot.key_fields["deleted"] is True
    assert deleted_snapshot.state_for_hash["deleted"] is True
    assert deleted_snapshot.metadata_json["bucket_name"] == "DELETED"
    deleted_evaluations = {evaluation.control_id: evaluation for evaluation in deleted_snapshot.evaluations}
    assert set(deleted_evaluations) == {"S3.2", "S3.4", "S3.5", "S3.9", "S3.11", "S3.15"}
    for evaluation in deleted_evaluations.values():
        assert evaluation.status == "RESOLVED"
        assert evaluation.status_reason == "inventory_resource_deleted"
        assert evaluation.state_confidence == 95
        assert evaluation.evidence_ref["resource_deleted"] is True


def test_s3_global_sweep_mixed_bucket_states_keeps_per_bucket_statuses_isolated() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(
        clients={
            "s3": _FakeS3MultiBucketMixedPublicPosture(region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
    )

    bucket_snapshots = [snapshot for snapshot in snapshots if snapshot.resource_type == "AwsS3Bucket"]
    assert len(bucket_snapshots) == 2
    per_bucket_status: dict[str, str] = {}
    for snapshot in bucket_snapshots:
        bucket_id = str(snapshot.resource_id)
        s32_bucket = [
            evaluation
            for evaluation in snapshot.evaluations
            if evaluation.control_id == "S3.2" and evaluation.resource_type == "AwsS3Bucket"
        ]
        assert len(s32_bucket) == 1
        per_bucket_status[bucket_id] = s32_bucket[0].status
        assert s32_bucket[0].status_reason in {"inventory_confirmed_compliant", "inventory_confirmed_non_compliant"}
        assert s32_bucket[0].state_confidence == 95
    assert per_bucket_status == {
        "arn:aws:s3:::mixed-open-bucket": "OPEN",
        "arn:aws:s3:::mixed-resolved-bucket": "RESOLVED",
    }


def test_s3_global_sweep_does_not_emit_duplicate_account_shaped_s3_2_evaluations() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(
        clients={
            "s3": _FakeS3MultiBucketMixedPublicPosture(region=region),
            "s3control": _FakeS3Control(),
        }
    )
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="s3",
    )

    evaluations = [evaluation for snapshot in snapshots for evaluation in snapshot.evaluations]
    account_s32 = [
        evaluation
        for evaluation in evaluations
        if evaluation.control_id == "S3.2" and evaluation.resource_type == "AwsAccount"
    ]
    assert account_s32 == []


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


def test_s3_5_missing_bucket_policy_is_open_with_deterministic_evidence() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-5-policy-missing"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketPolicyMissing(bucket=bucket, region=region),
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
    s35 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.5")
    assert s35.status == "OPEN"
    assert s35.status_reason == "inventory_confirmed_non_compliant"
    assert s35.state_confidence == 95
    assert {"source", "probe_branch", "error_code", "policy_parse_error", "ssl_deny_policy"}.issubset(
        set((s35.evidence_ref or {}).keys())
    )
    assert s35.evidence_ref["source"] == "inventory"
    assert s35.evidence_ref["probe_branch"] == "normal"
    assert s35.evidence_ref["error_code"] is None
    assert s35.evidence_ref["policy_parse_error"] is False
    assert s35.evidence_ref["ssl_deny_policy"] is False


def test_s3_5_malformed_policy_json_is_open_with_deterministic_evidence() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-5-policy-malformed"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketPolicyMalformed(bucket=bucket, region=region),
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
    s35 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.5")
    assert s35.status == "SOFT_RESOLVED"
    assert s35.status_reason == "inventory_partial_data_s3_bucket_policy_parse_failed"
    assert s35.state_confidence == 50
    assert {"source", "probe_branch", "error_code", "policy_parse_error", "ssl_deny_policy"}.issubset(
        set((s35.evidence_ref or {}).keys())
    )
    assert s35.evidence_ref["probe_branch"] == "partial_data"
    assert s35.evidence_ref["error_code"] is None
    assert s35.evidence_ref["policy_parse_error"] is True
    assert s35.evidence_ref["ssl_deny_policy"] is False


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


def test_s3_9_tagged_product_managed_support_log_sink_is_resolved_without_recursive_logging() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-9-product-managed-log-sink"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketTaggedSupportLogSink(
                bucket=bucket,
                region=region,
                logging_enabled={},
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
    assert s39.status_reason == "inventory_product_managed_support_log_sink"
    assert s39.evidence_ref["product_managed_support_log_sink"] is True
    assert s39.evidence_ref["support_bucket_role"] == SUPPORT_BUCKET_ROLE_S3_ACCESS_LOGS


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


def test_s3_4_missing_encryption_configuration_is_open_with_stable_reason() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-missing-config"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketNoEncryptionConfig(bucket=bucket, region=region),
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
    assert s34.status_reason == "inventory_confirmed_non_compliant"
    assert s34.state_confidence == 95
    assert {"source", "probe_branch", "error_code", "default_encryption_algorithm"}.issubset(
        set((s34.evidence_ref or {}).keys())
    )
    assert s34.evidence_ref["probe_branch"] == "normal"
    assert s34.evidence_ref["error_code"] is None
    assert s34.evidence_ref["default_encryption_algorithm"] is None


def test_s3_4_access_denied_is_reraised() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    bucket = "example-s3-4-access-denied"
    session = _FakeSession(
        clients={
            "s3": _FakeS3SingleBucketEncryptionAccessDenied(bucket=bucket, region=region),
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
    s315 = next(evaluation for evaluation in evaluations if evaluation.control_id == "S3.15")
    assert s34.status == "SOFT_RESOLVED"
    assert s34.status_reason == "inventory_access_denied_s3_get_bucket_encryption"
    assert s34.state_confidence == 40
    assert s34.evidence_ref["probe_branch"] == "access_denied"
    assert s34.evidence_ref["error_code"] == "AccessDeniedException"
    assert s315.status == "SOFT_RESOLVED"
    assert s315.status_reason == "inventory_access_denied_s3_get_bucket_encryption"
    assert s315.state_confidence == 40


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


def test_guardduty_list_detectors_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    client = _FakeGuardDutyListAccessDenied()
    session = _FakeSession(clients={"guardduty": client})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region="us-east-1",
        service="guardduty",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_guardduty_list_detectors"
    assert evaluation.state_confidence == 40
    assert {
        "source",
        "detector_ids",
        "detector_statuses",
        "access_ok",
        "list_access_denied",
        "list_error_code",
        "detector_access_denied",
        "detector_access_denied_count",
        "detector_invalid_input_count",
        "detector_api_error_count",
        "detector_api_error_codes",
        "detector_status_read_success_count",
        "status_branch",
    }.issubset(set((evaluation.evidence_ref or {}).keys()))
    assert evaluation.evidence_ref["access_ok"] is False
    assert evaluation.evidence_ref["list_access_denied"] is True
    assert evaluation.evidence_ref["list_error_code"] == "AccessDeniedException"
    assert evaluation.evidence_ref["detector_ids"] == []
    assert evaluation.evidence_ref["detector_access_denied_count"] == 0
    assert evaluation.evidence_ref["detector_invalid_input_count"] == 0
    assert evaluation.evidence_ref["detector_api_error_count"] == 0
    assert evaluation.evidence_ref["detector_status_read_success_count"] == 0
    assert evaluation.evidence_ref["status_branch"] == "access_denied_list_detectors"


def test_guardduty_invalid_input_only_is_open_with_invalid_counter() -> None:
    account_id = "123456789012"
    client = _FakeGuardDutyInvalidOnly()
    session = _FakeSession(clients={"guardduty": client})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region="us-east-1",
        service="guardduty",
    )

    assert len(snapshots) == 1
    assert client.processed_detector_ids == ["det-invalid-1", "det-invalid-2"]
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_partial_data_guardduty_invalid_detector_ids"
    assert evaluation.state_confidence == 50
    assert evaluation.evidence_ref["detector_access_denied_count"] == 0
    assert evaluation.evidence_ref["detector_invalid_input_count"] == 2
    assert evaluation.evidence_ref["detector_statuses"] == []
    assert evaluation.evidence_ref["detector_status_read_success_count"] == 0
    assert evaluation.evidence_ref["status_branch"] == "partial_data_invalid_detector_ids"


def test_guardduty_mixed_detector_states_soft_resolved_with_evidence_counters() -> None:
    account_id = "123456789012"
    client = _FakeGuardDutyMixedDetectorStates()
    session = _FakeSession(clients={"guardduty": client})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region="us-east-1",
        service="guardduty",
    )

    assert len(snapshots) == 1
    assert client.processed_detector_ids == ["det-enabled", "det-denied"]
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_guardduty_get_detector"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["detector_access_denied_count"] == 1
    assert evaluation.evidence_ref["detector_invalid_input_count"] == 0
    assert evaluation.evidence_ref["detector_statuses"] == ["ENABLED"]


def test_guardduty_detector_throttling_is_reraised() -> None:
    session = _FakeSession(clients={"guardduty": _FakeGuardDutyDetectorThrottling()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="us-east-1",
        service="guardduty",
    )
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_api_error_guardduty_get_detector"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["detector_api_error_count"] == 1
    assert evaluation.evidence_ref["detector_api_error_codes"] == ["ThrottlingException"]
    assert evaluation.evidence_ref["status_branch"] == "api_error_get_detector"


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
    assert evaluation.status_reason == "inventory_confirmed_compliant"
    assert evaluation.state_confidence == 95
    assert {
        "source",
        "enabled",
        "hub_arn",
        "access_ok",
        "partial_data",
        "api_error",
        "not_enabled_error",
        "error_code",
        "status_branch",
    }.issubset(set((evaluation.evidence_ref or {}).keys()))
    assert evaluation.evidence_ref["enabled"] is True
    assert evaluation.evidence_ref["access_ok"] is True
    assert evaluation.evidence_ref["partial_data"] is False
    assert evaluation.evidence_ref["api_error"] is False
    assert evaluation.evidence_ref["not_enabled_error"] is False
    assert evaluation.evidence_ref["status_branch"] == "normal_compliant"


def test_securityhub_not_enabled_is_open_with_high_confidence() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"securityhub": _FakeSecurityHubNotEnabled()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="securityhub",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 95
    assert evaluation.evidence_ref["enabled"] is False
    assert evaluation.evidence_ref["access_ok"] is True
    assert evaluation.evidence_ref["hub_arn"] is None
    assert evaluation.evidence_ref["error_code"] == "ResourceNotFoundException"


def test_securityhub_empty_hub_arn_is_open_ambiguous_not_enabled() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"securityhub": _FakeSecurityHubEmptyHubArn()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="securityhub",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_partial_data_securityhub_describe_hub"
    assert evaluation.state_confidence == 50
    assert evaluation.evidence_ref["enabled"] is False
    assert evaluation.evidence_ref["access_ok"] is True
    assert evaluation.evidence_ref["partial_data"] is True
    assert evaluation.evidence_ref["hub_arn"] is None
    assert evaluation.evidence_ref["error_code"] is None
    assert evaluation.evidence_ref["status_branch"] == "partial_data"


def test_securityhub_access_denied_emits_soft_resolved() -> None:
    account_id = "123456789012"
    region = "eu-north-1"
    session = _FakeSession(clients={"securityhub": _FakeSecurityHubAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="securityhub",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_securityhub_describe_hub"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["enabled"] is False
    assert evaluation.evidence_ref["access_ok"] is False
    assert evaluation.evidence_ref["error_code"] == "AccessDeniedException"


def test_securityhub_throttling_is_reraised() -> None:
    session = _FakeSession(clients={"securityhub": _FakeSecurityHubThrottling()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="securityhub",
    )
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_api_error_securityhub_describe_hub"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["api_error"] is True
    assert evaluation.evidence_ref["error_code"] == "ThrottlingException"
    assert evaluation.evidence_ref["status_branch"] == "api_error"


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
    assert evaluation.status_reason == "inventory_confirmed_compliant"
    assert evaluation.state_confidence == 95
    assert {
        "source",
        "trail_count",
        "multi_region_trail_count",
        "logging_multi_region_trails",
        "describe_access_denied",
        "describe_error_code",
        "trail_status_access_denied",
        "trail_status_access_denied_count",
        "trail_status_not_found_count",
        "trail_status_unknown_error_count",
        "trail_status_read_success_count",
        "status_branch",
    }.issubset(set((evaluation.evidence_ref or {}).keys()))
    assert evaluation.evidence_ref["trail_count"] == 1
    assert evaluation.evidence_ref["multi_region_trail_count"] == 1
    assert evaluation.evidence_ref["logging_multi_region_trails"] == 1
    assert evaluation.evidence_ref["describe_access_denied"] is False
    assert evaluation.evidence_ref["describe_error_code"] is None
    assert evaluation.evidence_ref["trail_status_access_denied"] is False
    assert evaluation.evidence_ref["trail_status_access_denied_count"] == 0
    assert evaluation.evidence_ref["trail_status_not_found_count"] == 0
    assert evaluation.evidence_ref["trail_status_unknown_error_count"] == 0
    assert evaluation.evidence_ref["trail_status_read_success_count"] == 1
    assert evaluation.evidence_ref["status_branch"] == "normal"


def test_cloudtrail_describe_trails_access_denied_is_reraised() -> None:
    session = _FakeSession(clients={"cloudtrail": _FakeCloudTrailDescribeAccessDenied()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="cloudtrail",
    )
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_cloudtrail_describe_trails"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["describe_access_denied"] is True
    assert evaluation.evidence_ref["describe_error_code"] == "AccessDeniedException"
    assert evaluation.evidence_ref["status_branch"] == "access_denied_describe_trails"


def test_cloudtrail_trail_not_found_only_is_open_with_high_confidence() -> None:
    session = _FakeSession(clients={"cloudtrail": _FakeCloudTrailTrailNotFoundOnly()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="cloudtrail",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_partial_data_cloudtrail_trail_status_indeterminate"
    assert evaluation.state_confidence == 50
    assert evaluation.evidence_ref["trail_count"] == 1
    assert evaluation.evidence_ref["multi_region_trail_count"] == 1
    assert evaluation.evidence_ref["logging_multi_region_trails"] == 0
    assert evaluation.evidence_ref["trail_status_access_denied"] is False
    assert evaluation.evidence_ref["trail_status_access_denied_count"] == 0
    assert evaluation.evidence_ref["trail_status_not_found_count"] == 1
    assert evaluation.evidence_ref["trail_status_read_success_count"] == 0
    assert evaluation.evidence_ref["status_branch"] == "partial_data_indeterminate_trail_status"


def test_cloudtrail_zero_trails_is_open_with_high_confidence() -> None:
    session = _FakeSession(clients={"cloudtrail": _FakeCloudTrailZeroTrails()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="cloudtrail",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "OPEN"
    assert evaluation.status_reason == "inventory_confirmed_non_compliant"
    assert evaluation.state_confidence == 95
    assert evaluation.evidence_ref["trail_count"] == 0
    assert evaluation.evidence_ref["logging_multi_region_trails"] == 0
    assert evaluation.evidence_ref["trail_status_access_denied"] is False
    assert evaluation.evidence_ref["trail_status_access_denied_count"] == 0


def test_cloudtrail_mixed_indeterminate_statuses_soft_resolve_with_low_confidence() -> None:
    session = _FakeSession(clients={"cloudtrail": _FakeCloudTrailMixedIndeterminate()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="cloudtrail",
    )

    assert len(snapshots) == 1
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_access_denied_cloudtrail_get_trail_status"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["trail_count"] == 2
    assert evaluation.evidence_ref["logging_multi_region_trails"] == 0
    assert evaluation.evidence_ref["trail_status_access_denied"] is True
    assert evaluation.evidence_ref["trail_status_access_denied_count"] == 1


def test_cloudtrail_status_throttling_is_reraised() -> None:
    session = _FakeSession(clients={"cloudtrail": _FakeCloudTrailStatusThrottling()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id="123456789012",
        region="eu-north-1",
        service="cloudtrail",
    )
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.status == "SOFT_RESOLVED"
    assert evaluation.status_reason == "inventory_api_error_cloudtrail_get_trail_status"
    assert evaluation.state_confidence == 40
    assert evaluation.evidence_ref["trail_status_unknown_error_count"] == 1
    assert evaluation.evidence_ref["status_branch"] == "api_error_get_trail_status"


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


def test_s3_lifecycle_enabled_rule_with_noncurrent_expiration_is_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Enabled",
                "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is True


def test_s3_lifecycle_enabled_rule_with_abort_incomplete_upload_is_compliant() -> None:
    s3 = _FakeS3Lifecycle(
        [
            {
                "Status": "Enabled",
                "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7},
            }
        ]
    )
    assert _s3_bucket_has_valid_lifecycle_rule(s3, "example-bucket") is True
