from __future__ import annotations

import json
from pathlib import Path

from botocore.exceptions import ClientError

from backend.workers.services.inventory_reconcile import collect_inventory_snapshots
from scripts.run_no_ui_pr_bundle_agent import _reconcile_services_for_control


_FINDINGS_PRE_RAW_PATH = Path("artifacts/no-ui-agent/20260220T022820Z/findings_pre_raw.json")


def _account_identity_from_findings(control_id: str) -> tuple[str, str, str, str]:
    payload = json.loads(_FINDINGS_PRE_RAW_PATH.read_text(encoding="utf-8"))
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("control_id") or "").upper() != control_id.upper():
            continue
        if str(row.get("resource_type") or "") != "AwsAccount":
            continue
        resource_id = str(row.get("resource_id") or "").strip()
        resource_type = str(row.get("resource_type") or "").strip()
        account_id = str(row.get("account_id") or "").strip()
        region = str(row.get("region") or "").strip()
        if resource_id and resource_type and account_id and region:
            return resource_id, resource_type, account_id, region
    raise AssertionError(f"No AwsAccount identity found for {control_id} in {_FINDINGS_PRE_RAW_PATH}")


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


class _FakeS3:
    def list_buckets(self):
        return {"Buckets": []}


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


def test_ec2_7_ec2_182_route_to_ebs_and_emit_account_identity() -> None:
    ec27_resource_id, ec27_resource_type, account_id, region = _account_identity_from_findings("EC2.7")
    ec2182_resource_id, ec2182_resource_type, ec2182_account_id, ec2182_region = _account_identity_from_findings(
        "EC2.182"
    )

    assert _reconcile_services_for_control("EC2.7") == ["ebs"]
    assert _reconcile_services_for_control("EC2.182") == ["ebs"]
    assert _reconcile_services_for_control("EC2.7") != ["ec2"]
    assert _reconcile_services_for_control("EC2.182") != ["ec2"]

    assert ec2182_account_id == account_id
    assert ec2182_region == region

    session = _FakeSession(clients={"ec2": _FakeEc2()})
    snapshots = collect_inventory_snapshots(
        session_boto=session,
        account_id=account_id,
        region=region,
        service="ebs",
    )
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.resource_id == ec27_resource_id
    assert snapshot.resource_type == ec27_resource_type

    evaluations = {evaluation.control_id: evaluation for evaluation in snapshot.evaluations}
    assert evaluations["EC2.7"].resource_id == ec27_resource_id
    assert evaluations["EC2.7"].resource_type == ec27_resource_type
    assert evaluations["EC2.182"].resource_id == ec2182_resource_id
    assert evaluations["EC2.182"].resource_type == ec2182_resource_type


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
