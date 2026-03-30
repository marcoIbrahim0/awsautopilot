# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should only allow unrestricted incoming traffic for authorized ports
- Action ID: `58a22607-666e-4016-8fe3-4ce62a235a6e`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-06f6252fa8a95b61d|EC2.53`
- Rollback command: `python3 ./rollback/sg_restore.py`
