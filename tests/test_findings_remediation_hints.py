import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routers import findings


def _finding(**overrides: object) -> SimpleNamespace:
    current = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
    payload = {
        "id": uuid.uuid4(),
        "finding_id": "finding-1",
        "tenant_id": uuid.uuid4(),
        "account_id": "696505809372",
        "region": "eu-north-1",
        "source": "security_hub",
        "severity_label": "HIGH",
        "severity_normalized": 75,
        "status": "NEW",
        "shadow_status_raw": None,
        "shadow_status_normalized": None,
        "shadow_fingerprint": None,
        "shadow_source": None,
        "shadow_status_reason": None,
        "shadow_last_observed_event_time": None,
        "shadow_last_evaluated_at": None,
        "title": "Synthetic finding",
        "description": None,
        "resource_id": "AWS::::Account:696505809372",
        "resource_type": "AwsAccount",
        "control_id": "EC2.19",
        "standard_name": None,
        "first_observed_at": None,
        "last_observed_at": None,
        "resolved_at": None,
        "sh_updated_at": current,
        "created_at": current,
        "updated_at": current,
        "raw_json": None,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_finding_to_response_populates_service_aliases_from_control_mapping() -> None:
    response = findings.finding_to_response(_finding(), remediation_hints={})

    assert response.service == "Amazon EC2"
    assert response.aws_service == "Amazon EC2"


@pytest.mark.asyncio
async def test_get_remediation_hints_marks_account_scoped_rows_as_managed_on_resource_scope() -> None:
    tenant_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    direct_rows = MagicMock()
    direct_rows.all.return_value = []
    finding_rows = MagicMock()
    finding_rows.all.return_value = [
        (
            finding_id,
            "EC2.19",
            "696505809372",
            "eu-north-1",
            "AWS::::Account:696505809372",
            "AwsAccount",
            "NEW",
            None,
        ),
    ]
    action_rows = MagicMock()
    action_rows.all.return_value = [
        (
            "696505809372",
            "eu-north-1",
            "sg_restrict_public_ports",
            "arn:aws:ec2:eu-north-1:696505809372:security-group/sg-02279e5f534057980",
            "AwsEc2SecurityGroup",
        ),
    ]

    db = AsyncMock()
    db.execute.side_effect = [direct_rows, finding_rows, action_rows]

    hints = await findings.get_remediation_hints_for_findings(db, tenant_id, [finding_id])

    assert hints[finding_id]["remediation_visibility_reason"] == "managed_on_resource_scope"
    assert hints[finding_id]["remediation_scope_owner"] == "resource"


@pytest.mark.asyncio
async def test_get_remediation_hints_marks_resolved_rows_as_historical_resolved() -> None:
    tenant_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    direct_rows = MagicMock()
    direct_rows.all.return_value = []
    finding_rows = MagicMock()
    finding_rows.all.return_value = [
        (
            finding_id,
            "S3.9",
            "696505809372",
            "eu-north-1",
            "arn:aws:s3:::example-bucket",
            "AwsS3Bucket",
            "RESOLVED",
            None,
        ),
    ]

    db = AsyncMock()
    db.execute.side_effect = [direct_rows, finding_rows]

    hints = await findings.get_remediation_hints_for_findings(db, tenant_id, [finding_id])

    assert hints[finding_id]["remediation_visibility_reason"] == "historical_resolved"
    assert hints[finding_id]["remediation_scope_message"] is not None
