# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## SSM documents should have the block public sharing setting enabled
- Action ID: `e8be6f05-0e5e-4bdc-818e-f551cd62ccb5`
- Control ID: `SSM.7`
- Target: `696505809372|eu-north-1|AWS::::Account:696505809372|SSM.7`
- Rollback command: `aws ssm update-service-setting --setting-id /ssm/documents/console/public-sharing-permission --setting-value Enable`
