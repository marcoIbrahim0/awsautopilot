from __future__ import annotations

from botocore.exceptions import ClientError

from worker.services.inventory_reconcile import collect_inventory_snapshots


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
    evaluation = snapshots[0].evaluations[0]
    assert evaluation.control_id == "GuardDuty.1"
    assert evaluation.status == "RESOLVED"
