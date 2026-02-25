# Task 1 Candidate File Map

Search scope: repository files excluding `node_modules`, `.git`, `build/dist`, and generated/vendor trees (`.venv`, `venv`, `.next`, `.terraform`, `__pycache__`, `*.pyc`, `artifacts`, `backups`).

CANDIDATE FILE MAP
| File Path | Why flagged | Likely contains (controls / actions / ids / fix-logic / unknown) |
|-----------|------------|------------------------------------------------------------------|

## Section A: High confidence — very likely to contain definitions
| `backend/models/action.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_finding.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_group.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_group_action_state.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_group_membership.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_group_run.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/action_group_run_result.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/models/control_mapping.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `backend/models/enums.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | ids |
| `backend/models/exception.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/models/finding.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/finding_shadow_state.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/inventory_asset.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/remediation_run.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/models/remediation_run_execution.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/routers/action_groups.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/routers/actions.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/routers/control_mappings.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `backend/routers/findings.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/routers/remediation_runs.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/action_engine.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/services/action_groups.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/services/action_run_confirmation.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/services/control_plane_event_allowlist.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/services/control_plane_intake.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/services/control_scope.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `backend/services/direct_fix_bridge.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/pr_bundle.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | fix-logic |
| `backend/services/remediation_audit.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/remediation_metrics.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/remediation_risk.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/remediation_runtime_checks.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/remediation_strategy.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/services/root_credentials_workflow.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | fix-logic |
| `backend/workers/jobs/backfill_action_groups.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/workers/jobs/backfill_finding_keys.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/jobs/compute_actions.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `backend/workers/jobs/ingest_control_plane_events.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/jobs/ingest_findings.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/jobs/reconcile_inventory_global_orchestration.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/jobs/reconcile_inventory_shard.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/jobs/remediation_run.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/workers/jobs/remediation_run_execution.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/workers/services/control_plane_events.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/services/direct_fix.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `backend/workers/services/inventory_assets.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/services/inventory_reconcile.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `infrastructure/cloudformation/control-plane-forwarder-template.yaml` | extension is .json/.yaml/.yml; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `infrastructure/cloudformation/dr-backup-controls.yaml` | extension is .json/.yaml/.yml; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `infrastructure/cloudformation/read-role-template.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/reconcile-scheduler-template.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/write-role-template.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/finding-scenarios/finding_control_mapping.csv` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |

## Section B: Medium confidence — may contain definitions
| `alembic/versions/0001_initial_models.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `alembic/versions/0002_findings_table.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0003_auth_user_fields_invites.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `alembic/versions/0004_actions_table.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `alembic/versions/0005_action_findings.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `alembic/versions/0006_exceptions_table.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `alembic/versions/0007_remediation_runs_table.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `alembic/versions/0010_findings_source_column.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0015_control_mappings_table.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `alembic/versions/0017_aws_account_status_disabled.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `alembic/versions/0019_findings_unique_per_tenant.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0020_remediation_run_executions.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `alembic/versions/0021_control_plane_shadow_tables.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0022_inventory_assets_table.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0023_control_plane_reconcile_jobs.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0024_tenant_control_plane_token.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0025_control_plane_event_ingest_status.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0027_findings_scope_shadow_overlay.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0028_findings_missing_keys_partial_index.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0029_tenant_reconciliation_controls.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0030_action_groups_persistent.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `alembic/versions/0031_control_plane_token_hash_lifecycle.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `alembic/versions/0032_findings_resolved_at.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/config.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/aws_account.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/models/baseline_report.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/models/control_plane_event.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/control_plane_event_ingest_status.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/control_plane_reconcile_job.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/models/evidence_export.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | ids |
| `backend/models/user.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/services/baseline_report_spec.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/services/canonicalization.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `backend/services/health_checks.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/config.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `backend/workers/services/json_safe.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `docs/action-groups-persistent.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `docs/audit-remediation/phase2-architecture-closure-checklist.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `docs/audit-remediation/phase3-architecture-closure-checklist.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `docs/audit-remediation/phase3-security-closure-checklist.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `docs/audit-remediation/phase4-required-check-governance.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `docs/control-plane-event-monitoring.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `docs/deployment/secrets-config.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `docs/remediation-safety-model.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `frontend/src/app/accounts/AccountIngestActions.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `frontend/src/app/accounts/AccountRowActions.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `frontend/src/app/accounts/AccountServiceStatusCheck.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/actions/ActionCard.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `frontend/src/app/findings/FindingCard.test.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/findings/FindingCard.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/findings/FindingGroupCard.test.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/findings/FindingGroupCard.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/findings/GroupedFindingsView.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/app/findings/GroupingControlBar.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/components/ActionDetailDrawer.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `frontend/src/components/RemediationModal.test.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `frontend/src/components/RemediationModal.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `frontend/src/components/RemediationRunProgress.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `frontend/src/components/control-plane/ControlPlaneKpiGrid.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `frontend/src/components/control-plane/FindingComparisonTable.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/components/control-plane/ReconcileActionsPanel.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `frontend/src/components/control-plane/ShadowFindingComparisonTable.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/components/pr-bundles/OnlineExecutionControls.test.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/components/pr-bundles/OnlineExecutionControls.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `frontend/src/components/ui/MajorActionButton.tsx` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `infrastructure/cloudformation/edge-protection.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/saas-ecs-dev.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/saas-serverless-build.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/saas-serverless-httpapi.yaml` | extension is .json/.yaml/.yml | unknown |
| `infrastructure/cloudformation/sqs-queues.yaml` | extension is .json/.yaml/.yml | unknown |
| `scripts/check_api_readiness.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/check_migration_gate.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/config/no_ui_pr_bundle_agent.example.json` | extension is .json/.yaml/.yml | fix-logic |
| `scripts/control_plane_freshness_canary.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/deploy_finding_bundle.sh` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `scripts/destroy_finding_bundle.sh` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `scripts/init_finding_scenarios.sh` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/lib/no_ui_agent_stats.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `scripts/run_s3_controls_campaign.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/upload_control_plane_forwarder_template.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/verify_control_plane_forwarder.sh` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `scripts/verify_step7.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `tests/test_action_engine_merge.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_action_groups_api.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_action_groups_migration.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_action_run_confirmation.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_actions_batch_grouping.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_backfill_action_groups_job.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | actions |
| `tests/test_baseline_report_renderer.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `tests/test_control_mappings_api.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `tests/test_control_plane_allowlist_parity.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_control_plane_events.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_control_plane_public_intake.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_control_plane_readiness.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_control_plane_token_lifecycle.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_control_scope.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | ids |
| `tests/test_direct_fix.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `tests/test_evidence_export_spec.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | ids |
| `tests/test_internal_control_plane_events.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_internal_inventory_reconcile.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_inventory_assets.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_inventory_reconcile.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_multi_account_campaign.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `tests/test_no_ui_agent_stats.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `tests/test_reconcile_inventory_global_orchestration_worker.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |
| `tests/test_remediation_risk.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `tests/test_remediation_run_execution.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `tests/test_remediation_run_worker.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `tests/test_remediation_runs_api.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | fix-logic |
| `tests/test_s3_campaign_summary.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | controls |
| `tests/test_shadow_state.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |
| `tests/test_step7_components.py` | Python first 50 lines match enum/Enum/CONTROL/RULE/ACTION/FINDING/check_id/control_id/rule_id/action_type | unknown |

## Section C: Low confidence — flagged by pattern but uncertain
| `backend/routers/control_plane.py` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config | controls |

## Section D: Explicitly ruled out — found but confirmed irrelevant
| `.github/workflows/architecture-phase2.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/architecture-phase3.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/backend-ci.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/dependency-governance.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/frontend-accessibility.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/frontend-ci.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/migration-gate.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/security-phase3.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `.github/workflows/worker-ci.yml` | extension is .json/.yaml/.yml; ruled out: CI workflow config, not control/action/ID registry source | unknown |
| `docs/audit-remediation/evidence/.phase3-arc008-backup-job-final.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/.phase3-arc008-backup-job.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/.phase3-arc008-restore-job-final.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/.phase3-arc008-restore-job.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/.phase3-arc008-restore-metadata-raw.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-arc002-arc006-load-20260212T125856Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-architecture-20260212T115214Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-architecture-20260212T115809Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-architecture-20260212T124542Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-architecture-20260212T131159Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase2-architecture-closure-evidence-20260212T131159Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc008-backup-job-final-20260217T181033Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc008-restore-job-final-20260217T181033Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc008-restore-metadata-20260217T181033Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc008-stack-outputs-20260217T181033Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc009-readiness-failure-20260217T181415Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc009-readiness-recovery-20260217T181415Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-arc009-system-health-slo-20260217T181442Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-architecture-20260217T182441Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-sec010-httpapi-precheck-20260217T224942Z.txt` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-sec010-httpapi-precheck-20260217T225021Z.txt` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-sec010-waf-input-arn-check-20260217T183545Z.txt` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260212T220639Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260212T232910Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260212T233036Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260212T233139Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260212T234649Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-security-20260217T224836Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-ux004-a11y-baseline-20260217T191445Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase3-ux005-ttv-metrics-20260217T193137Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T011527Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T012807Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T014903Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T015027Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T015129Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-main-branch-protection-20260218T015344Z.json` | extension is .json/.yaml/.yml; ruled out: evidence artifact/output, not source definitions | unknown |
| `docs/audit-remediation/evidence/phase4-required-check-context-audit-20260218T011345Z.md` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: evidence artifact/output, not source definitions | unknown |
| `frontend/a11y-results/findings.axe.json` | extension is .json/.yaml/.yml; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: accessibility test output artifact | unknown |
| `frontend/a11y-results/findings.png` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: accessibility test output artifact | unknown |
| `frontend/a11y-results/onboarding.axe.json` | extension is .json/.yaml/.yml; ruled out: accessibility test output artifact | unknown |
| `frontend/a11y-results/settings.axe.json` | extension is .json/.yaml/.yml; ruled out: accessibility test output artifact | unknown |
| `frontend/a11y-results/summary.json` | extension is .json/.yaml/.yml; ruled out: accessibility test output artifact | unknown |
| `frontend/components.json` | extension is .json/.yaml/.yml; ruled out: frontend tooling/build config | unknown |
| `frontend/eslint.config.mjs` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `frontend/next.config.ts` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `frontend/package-lock.json` | extension is .json/.yaml/.yml; ruled out: dependency manifest/lockfile | unknown |
| `frontend/package.json` | extension is .json/.yaml/.yml; ruled out: dependency manifest/lockfile | unknown |
| `frontend/postcss.config.mjs` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `frontend/tsconfig.json` | extension is .json/.yaml/.yml; filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `frontend/tsconfig.tsbuildinfo` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `frontend/vitest.config.ts` | filename contains keyword: control/rule/action/finding/check/policy/remediation/fix/mapping/registry/catalog/inventory/config; ruled out: frontend tooling/build config | unknown |
| `local-agent/package.json` | extension is .json/.yaml/.yml; ruled out: dependency manifest/lockfile | unknown |
| `package-lock.json` | extension is .json/.yaml/.yml; ruled out: dependency manifest/lockfile | unknown |
| `package.json` | extension is .json/.yaml/.yml; ruled out: dependency manifest/lockfile | unknown |
