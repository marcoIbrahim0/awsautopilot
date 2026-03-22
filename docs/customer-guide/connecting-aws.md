# Connecting Your AWS Account

Use IAM roles with `sts:AssumeRole` and `sts:ExternalId`.

## Roles

- `SecurityAutopilotReadRole` (required)
- `SecurityAutopilotWriteRole` (out of scope for the current product contract; do not deploy for active onboarding)

## Steps

1. Get your tenant External ID from onboarding or organization settings.
2. Deploy the `ReadRole` CloudFormation template in your AWS account.
3. In the app, save the AWS account ID, `ReadRole` ARN, and monitored regions.
4. Run onboarding final checks to confirm Inspector, Security Hub, AWS Config, and control-plane readiness.

## Current Remediation Scope

- Findings ingestion and action generation use `ReadRole`.
- Customer-run PR bundles are the supported remediation path.
- `direct_fix` and customer `WriteRole` execution are currently out of scope.

## Disconnecting

- Removing an AWS account from the app does not delete IAM resources in your AWS account.
- To remove the onboarding role, delete the `SecurityAutopilotReadRole` CloudFormation stack from your AWS account through your normal change-control process.
- If you still have a historical `SecurityAutopilotWriteRole` stack, remove that stack separately in your own AWS account. It is not part of the current supported workflow.

## Security Notes

- Trust policy must include the matching `sts:ExternalId`.
- If the launch link or operator instructions include `SaaSExecutionRoleArns`, keep trust scoped to that exact SaaS execution role ARN set rather than the full SaaS account root. The broader account-root trust is a temporary rollout fallback only.
- Keep least privilege on `ReadRole`.
- Use your own CI/CD or change-control path to review and apply generated PR bundles.

## Related

- [WriteRole status](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md)
- [Troubleshooting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/troubleshooting.md)
