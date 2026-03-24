# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## AWS Config should be enabled and use the service-linked role for resource recording
- Action ID: `202e02c7-f2c1-4c24-b81a-11168acad054`
- Control ID: `Config.1`
- Target: `696505809372|us-east-1|AWS::::Account:696505809372|Config.1`
- Rollback command: `python3 ./executable/actions/01-aws-account-696505809372-202e02c7/rollback/aws_config_restore.py`
