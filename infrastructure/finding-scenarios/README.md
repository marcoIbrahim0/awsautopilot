# Vulnerable Finding Bundle (IaC)

This folder contains a deployable Terraform bundle that intentionally creates insecure, production-like AWS architectures for CSPM finding generation.

Use only in disposable test accounts.

## Bundle structure

- Root stack:
  - `infrastructure/finding-scenarios/stacks/cspm_insecure_bundle/main.tf`
- Modules:
  - `infrastructure/finding-scenarios/modules/foundational_controls_gaps/main.tf`
  - `infrastructure/finding-scenarios/modules/insecure_workload_stack/main.tf`
- Coverage and mapping:
  - `infrastructure/finding-scenarios/scenario_coverage.csv`
  - `infrastructure/finding-scenarios/finding_control_mapping.csv`

## Architecture relationships

### `foundational_controls_gaps` module

- CloudTrail writes to a dedicated audit S3 bucket.
- AWS Config singleton-safe flow ensures recorder + delivery channel (create if absent), using IAM role and audit S3 bucket.
- Config recorder is stopped to keep the control non-compliant.
- Security Hub and GuardDuty are disabled in-region via CLI actions (`terraform_data` + `local-exec`).

### `insecure_workload_stack` module

- IAM role + instance profile is attached to EC2.
- EC2 runs inside a VPC/subnet/route/IGW network path.
- Security group with public admin ingress is attached to the EC2 instance.
- Unencrypted EBS root + attached data volume + snapshot are created for the workload.
- Snapshot block public access is disabled via EC2 API and the workload snapshot is made publicly shareable.
- Multiple S3 buckets are configured with intentional misconfigurations and accessed by workload IAM policy.

## Single deploy sequence

From project root:

```bash
./scripts/deploy_finding_bundle.sh -auto-approve
```

Optional environment overrides:

```bash
AWS_REGION=eu-north-1 FINDING_BUNDLE_PREFIX=security-autopilot FINDING_BUNDLE_INSTANCE_TYPE=t3.micro ./scripts/deploy_finding_bundle.sh -auto-approve
```

## Single teardown sequence

From project root:

```bash
./scripts/destroy_finding_bundle.sh -auto-approve
```

## Provider initialization helper

```bash
./scripts/init_finding_scenarios.sh
```

## Not feasible via IaC alone

- `IAM.4`: root access key creation requires interactive root-user credentials.
- Inspector CVE findings: deterministic results depend on scanner timing and changing live vulnerability data.
