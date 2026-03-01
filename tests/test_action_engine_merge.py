"""Unit tests for action merge behavior in backend.services.action_engine."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from backend.services.action_engine import (
    _action_type_from_control,
    _build_target_id,
    _grouping_key,
    _is_effectively_open_finding,
    _is_open_finding_status,
)
from backend.services.control_scope import canonical_control_id_for_action_type


def test_grouping_key_merges_equivalent_s3_public_controls() -> None:
    """S3.2 and S3.8 should merge into one action group for the same bucket."""
    tenant_id = uuid.uuid4()
    base = dict(
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        resource_id="arn:aws:s3:::demomarcoss",
    )
    f_s32 = SimpleNamespace(**base, control_id="S3.2")
    f_s38 = SimpleNamespace(**base, control_id="S3.8")

    assert _grouping_key(f_s32) == _grouping_key(f_s38)


def test_grouping_key_merges_equivalent_ec2_sg_controls() -> None:
    """EC2.53/EC2.13/EC2.19 (and back-compat EC2.18) should merge into one action group per security group."""
    tenant_id = uuid.uuid4()
    base = dict(
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        resource_id="arn:aws:ec2:eu-north-1:029037611564:security-group/sg-0123456789abcdef0",
    )
    f_ec253 = SimpleNamespace(**base, control_id="EC2.53")
    f_ec213 = SimpleNamespace(**base, control_id="EC2.13")
    f_ec219 = SimpleNamespace(**base, control_id="EC2.19")
    f_ec218 = SimpleNamespace(**base, control_id="EC2.18")

    assert _grouping_key(f_ec253) == _grouping_key(f_ec213)
    assert _grouping_key(f_ec253) == _grouping_key(f_ec219)
    assert _grouping_key(f_ec253) == _grouping_key(f_ec218)


def test_grouping_key_keeps_distinct_s3_action_types_separate() -> None:
    """S3.2 (block public access) must not merge with S3.4 (encryption)."""
    tenant_id = uuid.uuid4()
    base = dict(
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        resource_id="arn:aws:s3:::demomarcoss",
    )
    f_s32 = SimpleNamespace(**base, control_id="S3.2")
    f_s34 = SimpleNamespace(**base, control_id="S3.4")

    assert _grouping_key(f_s32) != _grouping_key(f_s34)


def test_grouping_key_keeps_unmapped_pr_only_controls_separate() -> None:
    """Unmapped controls remain separate to avoid unsafe over-merging."""
    tenant_id = uuid.uuid4()
    base = dict(
        tenant_id=tenant_id,
        account_id="029037611564",
        region="eu-north-1",
        resource_id="AWS::::Account:029037611564",
    )
    f_iam4 = SimpleNamespace(**base, control_id="IAM.4")
    f_config1 = SimpleNamespace(**base, control_id="Config.1")

    assert _grouping_key(f_iam4) != _grouping_key(f_config1)


def test_target_id_uses_canonical_control_for_equivalent_controls() -> None:
    """Equivalent controls should produce the same dedupe target_id."""
    action_type_s32 = _action_type_from_control("S3.2")
    action_type_s38 = _action_type_from_control("S3.8")
    canonical_s32 = canonical_control_id_for_action_type(action_type_s32, "S3.2")
    canonical_s38 = canonical_control_id_for_action_type(action_type_s38, "S3.8")

    target_s32 = _build_target_id(
        "029037611564",
        "eu-north-1",
        "arn:aws:s3:::demomarcoss",
        canonical_s32,
    )
    target_s38 = _build_target_id(
        "029037611564",
        "eu-north-1",
        "arn:aws:s3:::demomarcoss",
        canonical_s38,
    )
    assert target_s32 == target_s38


def test_target_id_uses_canonical_control_for_equivalent_ec2_controls() -> None:
    """Equivalent EC2 SG controls should produce the same dedupe target_id."""
    action_type_ec253 = _action_type_from_control("EC2.53")
    action_type_ec213 = _action_type_from_control("EC2.13")
    action_type_ec219 = _action_type_from_control("EC2.19")
    canonical_ec253 = canonical_control_id_for_action_type(action_type_ec253, "EC2.53")
    canonical_ec213 = canonical_control_id_for_action_type(action_type_ec213, "EC2.13")
    canonical_ec219 = canonical_control_id_for_action_type(action_type_ec219, "EC2.19")

    resource_id = "arn:aws:ec2:eu-north-1:029037611564:security-group/sg-0123456789abcdef0"
    target_ec253 = _build_target_id("029037611564", "eu-north-1", resource_id, canonical_ec253)
    target_ec213 = _build_target_id("029037611564", "eu-north-1", resource_id, canonical_ec213)
    target_ec219 = _build_target_id("029037611564", "eu-north-1", resource_id, canonical_ec219)
    assert target_ec253 == target_ec213
    assert target_ec253 == target_ec219


def test_open_status_helper_treats_only_resolved_as_closed() -> None:
    """Legacy/non-standard statuses should still be treated as open during recompute."""
    assert _is_open_finding_status("NEW") is True
    assert _is_open_finding_status("NOTIFIED") is True
    assert _is_open_finding_status("ACTIVE") is True
    assert _is_open_finding_status("OPEN") is True
    assert _is_open_finding_status("SUPPRESSED") is True
    assert _is_open_finding_status("RESOLVED") is False


def test_effective_open_helper_prefers_shadow_resolved_status() -> None:
    """Shadow RESOLVED should close findings even when canonical status is NEW."""
    finding = SimpleNamespace(status="NEW", shadow_status_normalized="RESOLVED")
    assert _is_effectively_open_finding(finding) is False


def test_effective_open_helper_prefers_shadow_open_status() -> None:
    """Shadow OPEN should reopen findings even when canonical status is RESOLVED."""
    finding = SimpleNamespace(status="RESOLVED", shadow_status_normalized="OPEN")
    assert _is_effectively_open_finding(finding) is True


def test_orphan_open_actions_are_resolved_when_no_unresolved_links() -> None:
    """Open actions should resolve when linked unresolved findings count is zero."""
    import uuid as _uuid
    from types import SimpleNamespace
    from backend.services.action_engine import _mark_resolved_actions_with_no_open_findings
    from backend.models.enums import ActionStatus

    tenant_id = _uuid.uuid4()
    action = SimpleNamespace(
        tenant_id=tenant_id,
        status=ActionStatus.open.value,
        action_finding_links=[],
    )

    class _Session:
        def query(self, model):  # noqa: D401 - simple stub
            class _Q:
                def __init__(self, actions):
                    self._actions = actions
                def filter(self, *args, **kwargs):
                    return self
                def all(self):
                    return self._actions
            return _Q([action])

    session = _Session()
    updated = _mark_resolved_actions_with_no_open_findings(session, tenant_id, None, None)
    assert action.status == ActionStatus.resolved.value
    assert updated == 1


def test_open_actions_resolve_when_only_shadow_resolved_links_exist() -> None:
    """Open actions resolve when linked findings are canonically NEW but shadow-resolved."""
    import uuid as _uuid
    from types import SimpleNamespace
    from backend.services.action_engine import _mark_resolved_actions_with_no_open_findings
    from backend.models.enums import ActionStatus

    tenant_id = _uuid.uuid4()
    shadow_resolved_finding = SimpleNamespace(status="NEW", shadow_status_normalized="RESOLVED")
    action = SimpleNamespace(
        tenant_id=tenant_id,
        status=ActionStatus.open.value,
        action_finding_links=[SimpleNamespace(finding=shadow_resolved_finding)],
    )

    class _Session:
        def query(self, model):  # noqa: D401 - simple stub
            class _Q:
                def __init__(self, actions):
                    self._actions = actions
                def filter(self, *args, **kwargs):
                    return self
                def all(self):
                    return self._actions
            return _Q([action])

    session = _Session()
    updated = _mark_resolved_actions_with_no_open_findings(session, tenant_id, None, None)
    assert action.status == ActionStatus.resolved.value
    assert updated == 1


def test_resolved_orphan_actions_stay_resolved_when_no_unresolved_links() -> None:
    """Resolved orphan actions should stay resolved when no unresolved links exist."""
    import uuid as _uuid
    from types import SimpleNamespace
    from backend.services.action_engine import _reopen_resolved_orphan_actions
    from backend.models.enums import ActionStatus

    tenant_id = _uuid.uuid4()
    action = SimpleNamespace(
        tenant_id=tenant_id,
        status=ActionStatus.resolved.value,
        account_id="029037611564",
        region=None,
        action_finding_links=[],
    )

    class _ActionQuery:
        def __init__(self, actions):
            self._actions = actions

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._actions

    class _Session:
        def query(self, model):
            return _ActionQuery([action])

    session = _Session()
    reopened = _reopen_resolved_orphan_actions(session, tenant_id, None, None)
    assert action.status == ActionStatus.resolved.value
    assert reopened == 0


def test_resolved_actions_with_open_linked_findings_are_reopened() -> None:
    """Resolved actions are reopened when linked findings are still open."""
    import uuid as _uuid
    from types import SimpleNamespace
    from backend.services.action_engine import _reopen_resolved_orphan_actions
    from backend.models.enums import ActionStatus

    tenant_id = _uuid.uuid4()
    open_finding = SimpleNamespace(status="NEW")
    action = SimpleNamespace(
        tenant_id=tenant_id,
        status=ActionStatus.resolved.value,
        account_id="029037611564",
        region=None,
        action_finding_links=[SimpleNamespace(finding=open_finding)],
    )

    class _ActionQuery:
        def __init__(self, actions):
            self._actions = actions

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return self._actions

    class _Session:
        def query(self, model):
            return _ActionQuery([action])

    session = _Session()
    reopened = _reopen_resolved_orphan_actions(session, tenant_id, None, None)
    assert action.status == ActionStatus.open.value
    assert reopened == 1
