# Connect WriteRole — Out Of Scope

> ⚠️ Status: Out of scope for the current product contract.

Customer `WriteRole` and `direct_fix` execution are currently disabled. New onboarding and active remediation workflows should use `ReadRole` plus customer-run PR bundles only.

## Current Contract

- `ReadRole` is required for AWS account connection and findings ingestion.
- `WriteRole` is not required and is not used by the currently supported remediation flow.
- `GET /api/actions/{action_id}/remediation-preview` supports `mode=pr_only` only.
- `POST /api/remediation-runs` supports `mode=pr_only` only.
- Customer-run PR bundles remain the supported remediation path.

If a caller still sends `role_write_arn`, the current API retains the field only for backward compatibility and clears it instead of activating a write-capable flow.

## Operator Guidance

- Do not deploy `SecurityAutopilotWriteRole` for new customer onboarding.
- Do not ask customers to connect `role_write_arn`.
- Do not rely on `direct_fix` or WriteRole-backed previews in demos, tests, or runbooks.
- Use reviewed PR bundles and customer-owned credentials/pipelines for remediation execution.

## Template Status

The historical template remains at [write-role-template.yaml](/Users/marcomaher/AWS%20Security%20Autopilot/infrastructure/cloudformation/write-role-template.yaml), but it is retained for backward-compatible reference only and is not part of the active onboarding path.

## Related

- [Connect your AWS account](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/connecting-aws.md)
- [Remediation safety model](/Users/marcomaher/AWS%20Security%20Autopilot/docs/remediation-safety-model.md)
- [Manual test use cases](/Users/marcomaher/AWS%20Security%20Autopilot/docs/runbooks/manual-test-use-cases.md)
