# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `dfe034c9-e9e2-43ba-b42e-be411eab068d`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `python3 ./executable/actions/01-aws-account-696505809372-dfe034c9/rollback/aws_config_restore.py`
