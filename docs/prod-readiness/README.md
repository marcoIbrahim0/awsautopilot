# PR Bundle Artifact Readiness

This document defines the production-readiness contract for PR bundle generation in [`backend/services/pr_bundle.py`](../../backend/services/pr_bundle.py) and worker execution in [`backend/workers/jobs/remediation_run.py`](../../backend/workers/jobs/remediation_run.py).

## Contract

1. Supported action types must generate executable IaC artifacts by default.
2. `README.tf` / `README.yaml` placeholder-only bundles are not allowed for `pr_only` execution.
3. Unsupported generation requests must fail with structured `PRBundleGenerationError` payloads.
4. Worker jobs must persist structured error metadata (`artifacts.pr_bundle_error`) and mark runs `failed` when generation is unsupported.
5. Exception-only strategies must be rejected at `POST /api/remediation-runs` (HTTP 400) before queue dispatch with guidance: `Use Exception workflow instead of PR bundle.`

Cross-reference:
- [Implementation Plan — Step 9](../implementation-plan.md)
- [No-UI PR Bundle Agent Runbook](../runbooks/no-ui-pr-bundle-agent.md)
- [Important To Do](important-to-do.md)
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
