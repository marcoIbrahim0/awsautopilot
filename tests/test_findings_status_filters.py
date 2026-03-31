import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.routers import findings


def _make_finding(status: str = "NEW") -> SimpleNamespace:
    current = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        id=uuid.uuid4(),
        finding_id="finding-1",
        tenant_id=uuid.uuid4(),
        account_id="696505809372",
        region="us-east-1",
        source="security_hub",
        severity_label="HIGH",
        severity_normalized=70,
        status=status,
        shadow_status_raw=None,
        shadow_status_normalized=None,
        shadow_fingerprint=None,
        shadow_source=None,
        shadow_status_reason=None,
        shadow_last_observed_event_time=None,
        shadow_last_evaluated_at=None,
        title="Synthetic finding",
        description=None,
        resource_id="arn:aws:ec2:us-east-1:696505809372:instance/i-1234567890abcdef0",
        resource_type="AwsEc2Instance",
        control_id="EC2.1",
        standard_name=None,
        first_observed_at=None,
        last_observed_at=None,
        resolved_at=None,
        sh_updated_at=current,
        created_at=current,
        updated_at=current,
        in_scope=True,
    )


def _compile_sql(statement: object) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


@pytest.mark.asyncio
async def test_finding_to_response_marks_active_exception_as_suppressed():
    finding = _make_finding(status="NEW")

    response = findings.finding_to_response(
        finding,
        exception_state={
            "exception_id": str(uuid.uuid4()),
            "exception_expires_at": "2026-03-30T00:00:00+00:00",
        },
        remediation_hints={},
    )

    assert response.status == "SUPPRESSED"
    assert response.effective_status == "SUPPRESSED"
    assert response.exception_id is not None


@pytest.mark.asyncio
async def test_list_findings_suppressed_filter_checks_active_exceptions():
    tenant_id = uuid.uuid4()
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    executed_statements: list[object] = []

    async def execute_side_effect(statement: object, *args, **kwargs):
        del args, kwargs
        executed_statements.append(statement)
        return count_result if len(executed_statements) == 1 else rows_result

    db = AsyncMock()
    db.execute.side_effect = execute_side_effect

    with patch("backend.routers.findings.resolve_tenant_id", return_value=tenant_id), patch(
        "backend.routers.findings.get_tenant_by_uuid",
        AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
    ), patch(
        "backend.routers.findings.get_remediation_hints_for_findings",
        AsyncMock(return_value={}),
    ), patch(
        "backend.routers.findings.get_exception_states_for_entities",
        AsyncMock(return_value={}),
    ):
        response = await findings.list_findings(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id=None,
            resource_type=None,
            resource_id=None,
            severity=None,
            status_filter="SUPPRESSED",
            source=None,
            first_observed_since=None,
            last_observed_since=None,
            updated_since=None,
            limit=20,
            offset=0,
        )

    compiled = " ".join(_compile_sql(statement) for statement in executed_statements[:2])

    assert response.total == 0
    assert "from exceptions" in compiled
    assert "suppressed" in compiled
    assert "expires_at" in compiled


@pytest.mark.asyncio
async def test_list_findings_grouped_suppressed_filter_checks_active_exceptions():
    tenant_id = uuid.uuid4()
    count_result = MagicMock()
    count_result.scalar.return_value = 0

    rows_result = MagicMock()
    rows_result.all.return_value = []

    executed_statements: list[object] = []

    async def execute_side_effect(statement: object, *args, **kwargs):
        del args, kwargs
        executed_statements.append(statement)
        return count_result if len(executed_statements) == 1 else rows_result

    db = AsyncMock()
    db.execute.side_effect = execute_side_effect

    with patch("backend.routers.findings.resolve_tenant_id", return_value=tenant_id), patch(
        "backend.routers.findings.get_tenant_by_uuid",
        AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
    ), patch(
        "backend.routers.findings._fetch_action_hints_for_group_rows",
        AsyncMock(return_value={}),
    ):
        response = await findings.list_findings_grouped(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id=None,
            resource_id=None,
            severity=None,
            source=None,
            status_filter="SUPPRESSED",
            limit=20,
            offset=0,
        )

    compiled = " ".join(_compile_sql(statement) for statement in executed_statements[:2])

    assert response.total == 0
    assert "from exceptions" in compiled
    assert "suppressed" in compiled
    assert "expires_at" in compiled


@pytest.mark.asyncio
async def test_list_findings_uses_stable_id_tiebreaker_for_offset_pagination():
    tenant_id = uuid.uuid4()
    current = datetime(2026, 3, 30, 3, 28, 40, tzinfo=timezone.utc)
    dataset: list[SimpleNamespace] = []
    for index in range(8):
        finding = _make_finding(status="NEW")
        finding.id = uuid.UUID(f"00000000-0000-0000-0000-{index + 1:012x}")
        finding.finding_id = f"finding-{index + 1}"
        finding.sh_updated_at = current
        finding.created_at = current
        finding.updated_at = current
        dataset.append(finding)

    count_result = MagicMock()
    count_result.scalar.return_value = len(dataset)
    executed_statements: list[object] = []

    async def execute_side_effect(statement: object, *args, **kwargs):
        del args, kwargs
        executed_statements.append(statement)
        if len(executed_statements) % 2 == 1:
            return count_result

        compiled = _compile_sql(statement)
        assert "findings.id asc" in compiled

        limit = int(statement._limit_clause.value)
        offset = int(statement._offset_clause.value)
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = sorted(dataset, key=lambda item: str(item.id))[offset:offset + limit]
        return rows_result

    db = AsyncMock()
    db.execute.side_effect = execute_side_effect

    with patch("backend.routers.findings.resolve_tenant_id", return_value=tenant_id), patch(
        "backend.routers.findings.get_tenant_by_uuid",
        AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
    ), patch(
        "backend.routers.findings.get_remediation_hints_for_findings",
        AsyncMock(return_value={}),
    ), patch(
        "backend.routers.findings.get_exception_states_for_entities",
        AsyncMock(return_value={}),
    ):
        first_page = await findings.list_findings(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id=None,
            resource_type=None,
            resource_id=None,
            severity=None,
            status_filter="NEW,NOTIFIED",
            source=None,
            first_observed_since=None,
            last_observed_since=None,
            updated_since=None,
            limit=5,
            offset=0,
        )
        second_page = await findings.list_findings(
            db=db,
            current_user=None,
            tenant_id=str(tenant_id),
            account_id=None,
            region=None,
            control_id=None,
            resource_type=None,
            resource_id=None,
            severity=None,
            status_filter="NEW,NOTIFIED",
            source=None,
            first_observed_since=None,
            last_observed_since=None,
            updated_since=None,
            limit=5,
            offset=5,
        )

    first_ids = [item.id for item in first_page.items]
    second_ids = [item.id for item in second_page.items]

    assert first_page.total == len(dataset)
    assert second_page.total == len(dataset)
    assert len(set(first_ids).intersection(second_ids)) == 0
    assert first_ids == [str(item.id) for item in sorted(dataset, key=lambda item: str(item.id))[:5]]
    assert second_ids == [str(item.id) for item in sorted(dataset, key=lambda item: str(item.id))[5:10]]
