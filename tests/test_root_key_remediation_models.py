from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from backend.models.root_key_dependency_fingerprint import RootKeyDependencyFingerprint
from backend.models.root_key_external_task import RootKeyExternalTask
from backend.models.root_key_remediation_artifact import RootKeyRemediationArtifact
from backend.models.root_key_remediation_event import RootKeyRemediationEvent
from backend.models.root_key_remediation_run import RootKeyRemediationRun


def _constraint_names(model: type) -> set[str]:
    return {constraint.name for constraint in model.__table__.constraints if constraint.name}



def _column_names(model: type) -> set[str]:
    return {column.name for column in model.__table__.columns}



def test_root_key_run_model_has_idempotency_and_lock_constraints() -> None:
    names = _constraint_names(RootKeyRemediationRun)
    assert "uq_root_key_runs_tenant_idempotency" in names
    assert "ck_root_key_runs_retry_non_negative" in names
    assert "ck_root_key_runs_lock_version_positive" in names



def test_all_root_key_models_include_required_common_columns() -> None:
    models = [
        RootKeyRemediationRun,
        RootKeyRemediationEvent,
        RootKeyDependencyFingerprint,
        RootKeyRemediationArtifact,
        RootKeyExternalTask,
    ]
    required_common = {
        "tenant_id",
        "account_id",
        "region",
        "control_id",
        "action_id",
        "finding_id",
        "strategy_id",
        "mode",
        "correlation_id",
        "started_at",
        "updated_at",
        "completed_at",
        "retry_count",
        "rollback_reason",
        "exception_expiry",
        "actor_metadata",
    }

    for model in models:
        assert required_common <= _column_names(model)
        assert "status" in _column_names(model)
        assert "state" in _column_names(model)



def test_root_key_child_models_enforce_tenant_run_scoped_uniques() -> None:
    child_models = {
        RootKeyRemediationEvent: "uq_root_key_events_tenant_run_idempotency",
        RootKeyRemediationArtifact: "uq_root_key_artifacts_tenant_run_idempotency",
        RootKeyExternalTask: "uq_root_key_external_tasks_tenant_run_idempotency",
        RootKeyDependencyFingerprint: "uq_root_key_dependency_fingerprint",
    }

    for model, constraint_name in child_models.items():
        assert constraint_name in _constraint_names(model)



def test_retry_count_check_constraints_exist_for_all_models() -> None:
    models = [
        RootKeyRemediationRun,
        RootKeyRemediationEvent,
        RootKeyDependencyFingerprint,
        RootKeyRemediationArtifact,
        RootKeyExternalTask,
    ]

    for model in models:
        checks = [c for c in model.__table__.constraints if isinstance(c, CheckConstraint)]
        assert any("retry_count" in str(c.sqltext) for c in checks)



def test_unique_constraints_explicitly_include_tenant_scope() -> None:
    models = [
        RootKeyRemediationRun,
        RootKeyRemediationEvent,
        RootKeyDependencyFingerprint,
        RootKeyRemediationArtifact,
        RootKeyExternalTask,
    ]

    for model in models:
        uniques = [c for c in model.__table__.constraints if isinstance(c, UniqueConstraint)]
        if not uniques:
            continue
        assert any("tenant_id" in [column.name for column in uc.columns] for uc in uniques)
