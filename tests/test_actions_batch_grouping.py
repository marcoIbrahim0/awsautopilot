"""Unit tests for actions execution-group batching in backend.routers.actions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.routers.actions import _group_actions_into_batches


def _action(
    *,
    action_type: str,
    account_id: str = "029037611564",
    region: str | None = "eu-north-1",
    status: str = "open",
    priority: int = 80,
    control_id: str | None = None,
    findings: int = 1,
    updated_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        action_type=action_type,
        account_id=account_id,
        region=region,
        status=status,
        priority=priority,
        control_id=control_id,
        action_finding_links=[object() for _ in range(findings)],
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def test_group_actions_into_batches_merges_by_action_type_account_region_status() -> None:
    """Two matching actions should appear as one batch group with aggregated counts."""
    actions = [
        _action(
            action_type="s3_bucket_block_public_access",
            control_id="S3.2",
            findings=2,
            priority=100,
            updated_at=datetime(2026, 2, 8, 12, 0, tzinfo=timezone.utc),
        ),
        _action(
            action_type="s3_bucket_block_public_access",
            control_id="S3.8",
            findings=1,
            priority=90,
            updated_at=datetime(2026, 2, 8, 12, 5, tzinfo=timezone.utc),
        ),
    ]

    grouped = _group_actions_into_batches(actions)
    assert len(grouped) == 1
    item = grouped[0]
    assert item.is_batch is True
    assert item.batch_action_count == 2
    assert item.batch_finding_count == 3
    assert item.finding_count == 3
    assert item.action_type == "s3_bucket_block_public_access"
    assert item.target_id.startswith("batch|s3_bucket_block_public_access|029037611564|eu-north-1|open")


def test_group_actions_into_batches_keeps_different_action_types_separate() -> None:
    """Different remediation action types should not merge into one batch group."""
    actions = [
        _action(action_type="s3_bucket_block_public_access", control_id="S3.2"),
        _action(action_type="s3_bucket_encryption", control_id="S3.4"),
    ]

    grouped = _group_actions_into_batches(actions)
    assert len(grouped) == 2
    assert {item.action_type for item in grouped} == {
        "s3_bucket_block_public_access",
        "s3_bucket_encryption",
    }


def test_group_actions_into_batches_skips_orphan_groups_with_zero_findings() -> None:
    """Execution groups should never show up with zero linked findings."""
    actions = [
        _action(action_type="sg_restrict_public_ports", findings=0, control_id="EC2.53"),
        _action(action_type="sg_restrict_public_ports", findings=0, control_id="EC2.53"),
        _action(action_type="s3_bucket_block_public_access", findings=1, control_id="S3.2"),
    ]

    grouped = _group_actions_into_batches(actions)
    assert len(grouped) == 1
    assert grouped[0].action_type == "s3_bucket_block_public_access"
    assert grouped[0].batch_finding_count == 1
