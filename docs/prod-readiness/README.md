# PR Bundle Artifact Readiness

> Scope note: This folder mixes active PR-bundle readiness docs with historical February-March 2026 discovery and deployment snapshots.
>
> Current contract note (2026-03-19): onboarding is ReadRole-only, customer-run PR bundles are the only supported remediation path, and customer `WriteRole` / `direct_fix` are out of scope.
>
> Treat this README, [docs/README.md](/Users/marcomaher/AWS%20Security%20Autopilot/docs/README.md), and [project_status.md](/Users/marcomaher/AWS%20Security%20Autopilot/.cursor/notes/project_status.md) as the current contract. Treat the `01-*`, `06-*`, `07-*`, and `08-*` raw extraction or deployment snapshot files as historical evidence unless they explicitly say otherwise.

This document defines the production-readiness contract for PR bundle generation in [`backend/services/pr_bundle.py`](../../backend/services/pr_bundle.py) and worker execution in [`backend/workers/jobs/remediation_run.py`](../../backend/workers/jobs/remediation_run.py).

## Contract

1. Supported action types must generate executable IaC artifacts by default.
2. `README.tf` / `README.yaml` placeholder-only bundles are not allowed for `pr_only` execution.
3. Unsupported generation requests must fail with structured `PRBundleGenerationError` payloads.
4. Worker jobs must persist structured error metadata (`artifacts.pr_bundle_error`) and mark runs `failed` when generation is unsupported.
5. Exception-only strategies must be rejected at `POST /api/remediation-runs` (HTTP 400) before queue dispatch with guidance: `Use Exception workflow instead of PR bundle.`

Cross-reference:
- [Remediation adjacency hardening plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/remediation-adjacency-hardening-plan.md)
- [Remediation determinism hardening implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/remediation-determinism-hardening-implementation-plan.md)
- [Remediation determinism frontend UI coverage status (March 30, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/remediation-determinism-hardening-implementation-plan.md#frontend-ui-coverage-status)
- [Remediation determinism production signoff (`PASS`, umbrella closure index, March 30, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260330T021500Z-remediation-determinism-production-signoff/README.md)
- [Phase 1 action-resolution lag closure (`PASS`, Gate 1 closed on production, March 30, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260330T011601Z-phase1-action-resolution-closure/README.md)
- [Phase 2 action-resolution lag closure (`PASS`, Gate 2 closed on production, March 30, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260330T012757Z-phase2-action-resolution-lag-closure/README.md)
- [Phase 1 + Phase 2 closure attempt (historical predecessor, lag still open at that point, March 30, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260330T000053Z-remediation-determinism-phase1-phase2-closure/README.md)
- [Phase 3 remediation determinism production rerun (`PASS`, Gate 3 closed after March 30 WI-5 follow-up)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T194129Z-remediation-determinism-phase3-production/README.md)
- [Phase 3 remediation determinism production attempt (historical predecessor, March 29, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T003200Z-remediation-determinism-phase3-production/README.md)
- [WI-1 production closure follow-up (`BLOCKED`, missing finding materialization fixed, March 29, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260329T002042Z-wi1-production-closure/README.md)
- [WI-7 authoritative production-path investigation (`WAIVED / DEFERRED`, March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T205427Z-wi7-production-authoritative-path/README.md)
- [Phase 1 remediation determinism production gate evidence (authoritative candidate rerun, live `WI-13` / `WI-14` proof and Gate 0 repair, March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T201359Z-phase1-production-candidate-rerun/README.md)
- [Phase 1 remediation determinism production gate evidence (historical rerun, live `WI-3` / `WI-6` apply proof, March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T175854Z-phase1-production-signoff-rerun/README.md)
- [Phase 1 remediation determinism production gate evidence (authenticated live run, historical defects package, March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T163848Z-remediation-determinism-phase1-production-live/README.md)
- [Phase 1 remediation determinism production gate evidence (blocked on auth, historical March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T162829Z-remediation-determinism-phase1-production/README.md)
- [WI-4 retained live proof package (March 28, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260328T021002Z-wi4-s35-apply-time-merge-canary/README.md)
- [Phase 5 support-bucket family implementation plan](/Users/marcomaher/AWS%20Security%20Autopilot/docs/prod-readiness/phase-5-support-bucket-family-implementation-plan.md)
- [Phase 5 live rerun evidence (March 26, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T050614Z-phase5-support-bucket-cluster-canary-backup-auth-rerun/notes/final-summary.md)
- [Phase 5 CloudTrail postdeploy recheck (March 26, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T052354Z-phase5-cloudtrail-postdeploy-recheck/notes/final-summary.md)
- [Phase 5 pending-confirmation repair (March 26, 2026)](/Users/marcomaher/AWS%20Security%20Autopilot/docs/test-results/live-runs/20260326T132117Z-phase5-pending-confirmation-repair/notes/final-summary.md)
- [Implementation Plan — archived snapshot](../archive/2026-02-doc-cleanup/implementation-plan.md)
- [No-UI PR Bundle Agent Runbook](../runbooks/no-ui-pr-bundle-agent.md)
- [Important To Do](important-to-do.md)
- [Item 16 High-Confidence Live Status Rollout Policy](16-high-confidence-live-status-rollout.md)
- [Item 17 Medium/Low-Confidence Control Coverage Plan](17-medium-low-confidence-control-coverage-plan.md)
- [Discovery Contract](01-discovery.md)
- [Task 1 Candidate File Map](06-task1-file-map.md)
- [Task 1 Input Validation](07-task1-input-validation.md)
- [Task 2 Architecture 1 Scenario](07-task2-arch1-scenario.md)
- [Task 3 Architecture 2 Scenario](07-task3-arch2-scenario.md)
- [Task 3 Control Coverage Validation](07-task3-control-coverage-validation.md)
- [Architecture Resource Design Source](07-architecture-design.md)
- [Task 4 A-Series Adversarial Resources](07-task4-a-series-resources.md)
- [Task 5 B-Series Adversarial Resources](07-task5-b-series-resources.md)
- [Task 1 Resource Inventory Extraction and Validation](08-task1-resource-inventory.md)
- [Task 4 Architecture 1 Reset Commands](08-task4-reset-arch1.sh)
- [Task 6 Architecture 1 Group A Teardown Script](08-task6-teardown-arch1-groupA.sh)
- [Task 6 Architecture 1 Group B Teardown Script](08-task6-teardown-arch1-groupB.sh)
- [Task 6 Architecture 1 Full Teardown Script](08-task6-teardown-arch1-full.sh)
- [Task 7 Architecture 2 Group A Teardown Script](08-task7-teardown-arch2-groupA.sh)
- [Task 7 Architecture 2 Group B Teardown Script](08-task7-teardown-arch2-groupB.sh)
- [Task 7 Architecture 2 Full Teardown Script](08-task7-teardown-arch2-full.sh)
- [Compiled Deployment Scripts Bundle](08-deployment-scripts.md)
- [Compiled Teardown Scripts Bundle](08-teardown-scripts.md)
- [Compiled Coverage Matrix](08-coverage-matrix.md)
- [Compilation Summary](08-summary.md)
- [Deployment Report](08-deployment-report.md)
- [Root-Credentials-Required Runbook (`iam_root_access_key_absent`)](root-credentials-required-iam-root-access-key-absent.md)

## Supported Action Types (Terraform Artifact Baseline)

| action_type | expected executable Terraform artifact |
| --- | --- |
| `s3_block_public_access` | `s3_block_public_access.tf` |
| `enable_security_hub` | `enable_security_hub.tf` |
| `enable_guardduty` | `enable_guardduty.tf` |
| `s3_bucket_block_public_access` | `s3_bucket_block_public_access.tf` |
| `s3_bucket_encryption` | `s3_bucket_encryption.tf` |
| `s3_bucket_access_logging` | `s3_bucket_access_logging.tf` |
| `s3_bucket_lifecycle_configuration` | `s3_bucket_lifecycle_configuration.tf` |
| `s3_bucket_encryption_kms` | `s3_bucket_encryption_kms.tf` |
| `sg_restrict_public_ports` | `sg_restrict_public_ports.tf` |
| `cloudtrail_enabled` | `cloudtrail_enabled.tf` |
| `aws_config_enabled` | `aws_config_enabled.tf` |
| `ssm_block_public_sharing` | `ssm_block_public_sharing.tf` |
| `ebs_snapshot_block_public_access` | `ebs_snapshot_block_public_access.tf` |
| `ebs_default_encryption` | `ebs_default_encryption.tf` |
| `s3_bucket_require_ssl` | `s3_bucket_require_ssl.tf` |
| `iam_root_access_key_absent` | `iam_root_access_key_absent.tf` |

## Structured Error Codes

When generation cannot produce runnable IaC, `PRBundleGenerationError.as_dict()` returns:

```json
{
  "code": "<machine_code>",
  "detail": "<human detail>",
  "action_type": "<action_type_or_empty>",
  "format": "<terraform_or_cloudformation_or_empty>",
  "strategy_id": "<strategy_or_empty>",
  "variant": "<variant_or_empty>"
}
```

Current explicit error codes:
- `missing_action_context`
- `missing_action_type`
- `pr_only_action_type_unsupported`
- `unsupported_action_type`
- `missing_security_group_id`
- `unsupported_variant_format`
- `unsupported_format_for_action_type`
- `exception_strategy_requires_exception_workflow`

## Verification Tests

Primary coverage:
- [`tests/test_step7_components.py`](../../tests/test_step7_components.py)
- [`tests/test_remediation_run_worker.py`](../../tests/test_remediation_run_worker.py)

Representative commands:
- `PYTHONPATH=. ./venv/bin/pytest -q tests/test_step7_components.py`
- `PYTHONPATH=. ./venv/bin/pytest -q tests/test_remediation_run_worker.py`
