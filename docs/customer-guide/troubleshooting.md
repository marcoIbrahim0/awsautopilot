# Troubleshooting

## Common Issues

### Login/auth issues
- Verify credentials and tenant context.
- Re-authenticate if session expired.

### AWS connection issues
- Validate role ARN format and account ID.
- Confirm trust policy principal + ExternalId.
- Confirm CloudFormation stack finished successfully.

### Findings/actions not updating
- Trigger ingest from Accounts page.
- Wait for worker processing.
- Recompute actions if needed.

### Notification settings issues
- Verify digest/slack settings for tenant admins.
- Confirm webhook validity for Slack.

## Escalation Data to Capture

- Tenant/account identifiers
- Endpoint + HTTP status + UTC timestamp
- Relevant UI screenshot
- Reproduction steps

## Related

- [Customer guide index](/Users/marcomaher/AWS%20Security%20Autopilot/docs/customer-guide/README.md)
- [Live E2E tracker](/Users/marcomaher/AWS%20Security%20Autopilot/docs/live-e2e-testing/00-BASE-ISSUE-TRACKER.md)
