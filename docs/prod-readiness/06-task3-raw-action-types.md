RAW ACTION TYPE EXTRACTION
| Type Value | Human Name | Execution Method | Source File | Source Line |
|-----------|------------|-----------------|-------------|-------------|
| pr_only | unknown | unknown | backend/services/action_engine.py | 69 |
| pr_only | unknown | unknown | backend/routers/actions.py | 180 |
| direct_fix | unknown | unknown | backend/routers/actions.py | 180 |
| pr_only | unknown | unknown | backend/routers/actions.py | 196 |
| direct_fix | unknown | unknown | backend/routers/actions.py | 196 |
| s3_block_public_access | S3 account public access hardening | unknown | backend/routers/actions.py | 233 |
| enable_security_hub | Enable Security Hub | unknown | backend/routers/actions.py | 234 |
| enable_guardduty | Enable GuardDuty | unknown | backend/routers/actions.py | 235 |
| s3_bucket_block_public_access | Enforce S3 bucket public access hardening | unknown | backend/routers/actions.py | 236 |
| s3_bucket_encryption | Enforce S3 bucket encryption | unknown | backend/routers/actions.py | 237 |
| s3_bucket_access_logging | Enable S3 bucket access logging | unknown | backend/routers/actions.py | 238 |
| s3_bucket_lifecycle_configuration | Configure S3 bucket lifecycle | unknown | backend/routers/actions.py | 239 |
| s3_bucket_encryption_kms | Enforce S3 bucket SSE-KMS encryption | unknown | backend/routers/actions.py | 240 |
| sg_restrict_public_ports | Restrict security-group public ports | unknown | backend/routers/actions.py | 241 |
| cloudtrail_enabled | Enable CloudTrail | unknown | backend/routers/actions.py | 242 |
| aws_config_enabled | Enable AWS Config recording | unknown | backend/routers/actions.py | 243 |
| ssm_block_public_sharing | Block public SSM document sharing | unknown | backend/routers/actions.py | 244 |
| ebs_snapshot_block_public_access | Restrict EBS snapshot public sharing | unknown | backend/routers/actions.py | 245 |
| ebs_default_encryption | Enable EBS default encryption | unknown | backend/routers/actions.py | 246 |
| s3_bucket_require_ssl | Enforce SSL-only S3 access | unknown | backend/routers/actions.py | 247 |
| iam_root_access_key_absent | Remove IAM root access keys | unknown | backend/routers/actions.py | 248 |
| direct_fix | direct_fix (preview mode) | unknown | backend/routers/actions.py | 804 |
| pr_bundle | PR bundle mode | iac-pr-required | backend/routers/actions.py | 847 |
| pr_only | unknown | unknown | backend/routers/action_groups.py | 399 |
| pr_only | pr_only (unmapped control) | manual | frontend/src/app/actions/ActionCard.tsx | 100 |
| s3_block_public_access | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 70 |
| enable_security_hub | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 71 |
| enable_guardduty | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 72 |
| ebs_default_encryption | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 73 |
| pr_only | This action is pr_only (unmapped control). Terraform/CloudFormation generation isn't supported yet. Remediate manually in AWS, then click Recompute actions. | iac-pr-required | frontend/src/components/RemediationModal.tsx | 59 |
| pr_only | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 465 |
| direct_fix | unknown | unknown | frontend/src/components/ActionDetailModal.tsx | 719 |
| pr_only | Unmapped controls remain separate to avoid unsafe over-merging. | unknown | tests/test_action_engine_merge.py | 66 |

FILES READ (WITH LINE COUNTS)
- backend/models/action.py — 68 lines — no relevant definitions.
- backend/models/action_finding.py — 47 lines — no relevant definitions.
- backend/models/action_group.py — 63 lines — no relevant definitions.
- backend/models/action_group_action_state.py — 84 lines — no relevant definitions.
- backend/models/action_group_membership.py — 53 lines — no relevant definitions.
- backend/models/action_group_run.py — 82 lines — no relevant definitions.
- backend/models/action_group_run_result.py — 69 lines — no relevant definitions.
- backend/routers/action_groups.py — 447 lines — relevant definitions found.
- backend/routers/actions.py — 1116 lines — relevant definitions found.
- backend/services/action_engine.py — 361 lines — relevant definitions found.
- backend/services/action_groups.py — 386 lines — no relevant definitions.
- backend/services/action_run_confirmation.py — 307 lines — no relevant definitions.
- backend/workers/jobs/backfill_action_groups.py — 365 lines — no relevant definitions.
- backend/workers/jobs/compute_actions.py — 53 lines — no relevant definitions.
- alembic/versions/0004_actions_table.py — 68 lines — no relevant definitions.
- alembic/versions/0005_action_findings.py — 61 lines — no relevant definitions.
- alembic/versions/0030_action_groups_persistent.py — 423 lines — no relevant definitions.
- docs/action-groups-persistent.md — 64 lines — no relevant definitions.
- frontend/src/app/accounts/AccountIngestActions.tsx — 343 lines — no relevant definitions.
- frontend/src/app/accounts/AccountRowActions.tsx — 41 lines — no relevant definitions.
- frontend/src/app/actions/ActionCard.tsx — 179 lines — relevant definitions found.
- frontend/src/components/ActionDetailModal.tsx — 1641 lines — relevant definitions found.
- frontend/src/components/RemediationModal.tsx — 1722 lines — relevant definitions found.
- frontend/src/components/control-plane/ReconcileActionsPanel.tsx — 207 lines — no relevant definitions.
- frontend/src/components/ui/MajorActionButton.tsx — 85 lines — no relevant definitions.
- tests/test_action_engine_merge.py — 205 lines — relevant definitions found.
- tests/test_action_groups_api.py — 89 lines — no relevant definitions.
- tests/test_action_groups_migration.py — 14 lines — no relevant definitions.
- tests/test_action_run_confirmation.py — 89 lines — no relevant definitions.
- tests/test_actions_batch_grouping.py — 91 lines — no relevant definitions.
- tests/test_backfill_action_groups_job.py — 27 lines — no relevant definitions.
