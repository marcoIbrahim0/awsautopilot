# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## SSM documents should have the block public sharing setting enabled
- Action ID: `e6b1eac2-041c-4fb3-9a47-2525a3afa908`
- Control ID: `SSM.7`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|SSM.7`
- Rollback command: `aws ssm update-service-setting --setting-id /ssm/documents/console/public-sharing-permission --setting-value Enable`
