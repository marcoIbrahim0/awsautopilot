# SecurityHub.1 (not possible with declarative IaC)

`SecurityHub.1` requires Security Hub to be disabled or not enabled in a region.

With declarative Terraform/CloudFormation, this is not reliably enforceable as a stable "vulnerable desired state" across arbitrary accounts:

- CloudFormation has an enable resource (`AWS::SecurityHub::Hub`) but no native disable resource.
- Terraform can model enabled state, but "disabled" is represented by resource absence/destruction, which cannot safely and deterministically disable pre-existing unmanaged Security Hub state in every account/region.

Use manual setup for this scenario:

1. Open Security Hub in the target region.
2. Disable Security Hub (or use a region where it was never enabled).
3. Wait for control evaluation and ingest findings.
