import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.routers import findings


@pytest.mark.asyncio
async def test_fetch_action_hints_for_group_rows_keeps_same_control_groups_isolated():
    tenant_id = uuid.uuid4()
    finding_id_rule = uuid.uuid4()
    finding_id_account = uuid.uuid4()
    action_id_rule = uuid.uuid4()
    action_id_account = uuid.uuid4()

    row_rule = SimpleNamespace(
        control_id="Config.1",
        resource_type="AwsConfigRule",
        account_id="696505809372",
        region="us-east-1",
        finding_ids=[finding_id_rule],
    )
    row_account = SimpleNamespace(
        control_id="Config.1",
        resource_type="AwsAccount",
        account_id="696505809372",
        region="eu-north-1",
        finding_ids=[finding_id_account],
    )

    action_rows_result = MagicMock()
    action_rows_result.all.return_value = [
        (
            finding_id_account,
            action_id_account,
            "aws_config_enabled",
            "open",
            "696505809372",
            "eu-north-1",
            None,
            None,
            None,
            None,
            None,
            "AWS::::Account:696505809372",
            "AWS::::Account:696505809372",
        ),
        (
            finding_id_rule,
            action_id_rule,
            "aws_config_enabled",
            "resolved",
            "696505809372",
            "us-east-1",
            None,
            None,
            None,
            None,
            None,
            "arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev",
            "arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev",
        ),
    ]

    db = AsyncMock()
    db.execute.return_value = action_rows_result

    hints = await findings._fetch_action_hints_for_group_rows(db, tenant_id, [row_rule, row_account])

    assert hints[("Config.1", "AwsConfigRule", "696505809372", "us-east-1")] == {
        "remediation_action_id": str(action_id_rule),
        "remediation_action_type": "aws_config_enabled",
        "remediation_action_status": "resolved",
        "remediation_action_account_id": "696505809372",
        "remediation_action_region": "us-east-1",
        "remediation_action_group_id": None,
        "remediation_action_group_status_bucket": None,
        "remediation_action_group_latest_run_status": None,
        "pending_confirmation": False,
        "pending_confirmation_started_at": None,
        "pending_confirmation_deadline_at": None,
        "pending_confirmation_message": None,
        "pending_confirmation_severity": None,
    }
    assert hints[("Config.1", "AwsAccount", "696505809372", "eu-north-1")] == {
        "remediation_action_id": str(action_id_account),
        "remediation_action_type": "aws_config_enabled",
        "remediation_action_status": "open",
        "remediation_action_account_id": "696505809372",
        "remediation_action_region": "eu-north-1",
        "remediation_action_group_id": None,
        "remediation_action_group_status_bucket": None,
        "remediation_action_group_latest_run_status": None,
        "pending_confirmation": False,
        "pending_confirmation_started_at": None,
        "pending_confirmation_deadline_at": None,
        "pending_confirmation_message": None,
        "pending_confirmation_severity": None,
    }


@pytest.mark.asyncio
async def test_list_findings_grouped_returns_group_specific_remediation_action_hint():
    tenant_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    action_id = uuid.uuid4()

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    grouped_row = SimpleNamespace(
        control_id="Config.1",
        resource_type="AwsConfigRule",
        account_id="696505809372",
        region="us-east-1",
        rule_title="Synthetic Config finding with trusted threat intel",
        finding_count=1,
        finding_ids=[finding_id],
        account_ids=["696505809372"],
        regions=["us-east-1"],
        cnt_critical=0,
        cnt_high=0,
        cnt_medium=0,
        cnt_low=1,
        cnt_informational=0,
    )
    rows_result = MagicMock()
    rows_result.all.return_value = [grouped_row]

    action_rows_result = MagicMock()
    pending_started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    action_rows_result.all.return_value = [
        (
            finding_id,
            action_id,
            "aws_config_enabled",
            "resolved",
            "696505809372",
            "us-east-1",
            uuid.uuid4(),
            "run_successful_pending_confirmation",
            None,
            "finished",
            pending_started_at,
            "arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev",
            "arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev",
        ),
    ]

    db = AsyncMock()
    db.execute.side_effect = [count_result, rows_result, action_rows_result]

    with patch("backend.routers.findings.resolve_tenant_id", return_value=tenant_id), patch(
        "backend.routers.findings.get_tenant_by_uuid",
        AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
    ):
        response = await findings.list_findings_grouped(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id=None,
            resource_id="arn:aws:config:us-east-1:696505809372:config-rule/ocypheris-p2-config-fresh-kev",
            severity=None,
            source=None,
            status_filter=None,
            limit=20,
            offset=0,
        )

    assert response.total == 1
    assert response.items[0].group_key == "Config.1|AwsConfigRule|696505809372|us-east-1"
    assert response.items[0].control_id == "Config.1"
    assert response.items[0].remediation_action_id == str(action_id)
    assert response.items[0].remediation_action_type == "aws_config_enabled"
    assert response.items[0].remediation_action_status == "resolved"
    assert response.items[0].remediation_action_group_status_bucket == "run_successful_pending_confirmation"
    assert response.items[0].remediation_action_group_latest_run_status == "finished"
    assert response.items[0].pending_confirmation is True
    assert response.items[0].pending_confirmation_message is not None
    assert response.items[0].pending_confirmation_severity == "info"


@pytest.mark.asyncio
async def test_list_findings_grouped_splits_multi_region_control_rows_and_keeps_pending_scoped():
    tenant_id = uuid.uuid4()
    finding_id_eu = uuid.uuid4()
    finding_id_us = uuid.uuid4()
    action_id_eu = uuid.uuid4()
    action_id_us = uuid.uuid4()

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    grouped_rows_result = MagicMock()
    grouped_rows_result.all.return_value = [
        SimpleNamespace(
            control_id="EC2.182",
            resource_type="AwsEc2SnapshotBlockPublicAccess",
            account_id="696505809372",
            region="eu-north-1",
            rule_title="Amazon EBS Snapshots should not be publicly accessible",
            finding_count=1,
            finding_ids=[finding_id_eu],
            account_ids=["696505809372"],
            regions=["eu-north-1"],
            cnt_critical=0,
            cnt_high=1,
            cnt_medium=0,
            cnt_low=0,
            cnt_informational=0,
        ),
        SimpleNamespace(
            control_id="EC2.182",
            resource_type="AwsEc2SnapshotBlockPublicAccess",
            account_id="696505809372",
            region="us-east-1",
            rule_title="Amazon EBS Snapshots should not be publicly accessible",
            finding_count=1,
            finding_ids=[finding_id_us],
            account_ids=["696505809372"],
            regions=["us-east-1"],
            cnt_critical=0,
            cnt_high=1,
            cnt_medium=0,
            cnt_low=0,
            cnt_informational=0,
        ),
    ]

    action_rows_result = MagicMock()
    action_rows_result.all.return_value = [
        (
            finding_id_us,
            action_id_us,
            "ebs_snapshot_block_public_access",
            "resolved",
            "696505809372",
            "us-east-1",
            uuid.uuid4(),
            "run_successful_pending_confirmation",
            None,
            "finished",
            datetime.fromisoformat("2026-03-24T08:30:00+00:00"),
            "arn:aws:ec2:us-east-1:696505809372:snapshotblockpublicaccess/696505809372",
            "arn:aws:ec2:us-east-1:696505809372:snapshotblockpublicaccess/696505809372",
        ),
        (
            finding_id_eu,
            action_id_eu,
            "ebs_snapshot_block_public_access",
            "open",
            "696505809372",
            "eu-north-1",
            uuid.uuid4(),
            "run_not_successful",
            None,
            "failed",
            datetime.fromisoformat("2026-03-24T08:15:00+00:00"),
            "arn:aws:ec2:eu-north-1:696505809372:snapshotblockpublicaccess/696505809372",
            "arn:aws:ec2:eu-north-1:696505809372:snapshotblockpublicaccess/696505809372",
        ),
    ]

    db = AsyncMock()
    db.execute.side_effect = [count_result, grouped_rows_result, action_rows_result]

    with patch("backend.routers.findings.resolve_tenant_id", return_value=tenant_id), patch(
        "backend.routers.findings.get_tenant_by_uuid",
        AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
    ):
        response = await findings.list_findings_grouped(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id="EC2.182",
            resource_id=None,
            severity=None,
            source=None,
            status_filter=None,
            limit=20,
            offset=0,
        )

    assert response.total == 2
    assert [item.group_key for item in response.items] == [
        "EC2.182|AwsEc2SnapshotBlockPublicAccess|696505809372|eu-north-1",
        "EC2.182|AwsEc2SnapshotBlockPublicAccess|696505809372|us-east-1",
    ]
    assert response.items[0].pending_confirmation is False
    assert response.items[1].pending_confirmation is True
    assert response.items[1].pending_confirmation_severity == "info"
