# Connecting Your AWS Account

Use IAM roles with STS AssumeRole + ExternalId.

## Roles

- `SecurityAutopilotReadRole` (required)
- `SecurityAutopilotWriteRole` (optional, for direct-fix operations)

## Steps

1. Get your tenant External ID from onboarding/settings.
2. Deploy ReadRole CloudFormation template in your AWS account.
3. Optionally deploy WriteRole template.
4. In app, submit account ID, role ARN(s), and selected regions.
5. Validate connection.

## Security notes

- Trust policy must include the SaaS account principal and matching `sts:ExternalId`.
- Keep least privilege on both roles.
- WriteRole should be enabled only when you want direct-fix capability.

## Related

- [Connect WriteRole guide](/Users/marcomaher/AWS%20Security%20Autopilot/docs/connect-write-role.md)
- [Troubleshooting](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/troubleshooting.md)
