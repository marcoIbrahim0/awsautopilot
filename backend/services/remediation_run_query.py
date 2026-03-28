from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.sql.elements import ColumnElement

from backend.models.action_group_membership import ActionGroupMembership
from backend.models.action_group_run import ActionGroupRun
from backend.models.remediation_run import RemediationRun


def grouped_related_remediation_run_ids_subquery(
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
):
    group_ids = select(ActionGroupMembership.group_id).where(
        ActionGroupMembership.tenant_id == tenant_id,
        ActionGroupMembership.action_id == action_id,
    )
    return select(ActionGroupRun.remediation_run_id).where(
        ActionGroupRun.tenant_id == tenant_id,
        ActionGroupRun.remediation_run_id.is_not(None),
        ActionGroupRun.group_id.in_(group_ids),
    )


def action_related_remediation_runs_clause(
    *,
    tenant_id: uuid.UUID,
    action_id: uuid.UUID,
    include_group_related: bool,
) -> ColumnElement[bool]:
    direct_clause: ColumnElement[bool] = RemediationRun.action_id == action_id
    if not include_group_related:
        return direct_clause
    return or_(
        direct_clause,
        RemediationRun.id.in_(
            grouped_related_remediation_run_ids_subquery(
                tenant_id=tenant_id,
                action_id=action_id,
            )
        ),
    )
