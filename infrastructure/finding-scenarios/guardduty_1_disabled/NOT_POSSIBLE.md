# GuardDuty.1 (not possible with declarative IaC)

`GuardDuty.1` requires GuardDuty to be disabled in a region.

With declarative Terraform/CloudFormation, this is not reliably enforceable as a stable "vulnerable desired state" across arbitrary accounts:

- CloudFormation supports detector resources but does not provide a universal declarative pattern to disable an already existing unmanaged detector in every account/region.
- Terraform can manage a detector only when it owns/imports that singleton detector; in accounts where detector state already exists outside state, apply is not deterministic for a reusable "one-shot vulnerable template."

Use manual setup for this scenario:

1. Open GuardDuty in the target region.
2. Disable GuardDuty (or use a region where it is not enabled).
3. Wait for control evaluation and ingest findings.
