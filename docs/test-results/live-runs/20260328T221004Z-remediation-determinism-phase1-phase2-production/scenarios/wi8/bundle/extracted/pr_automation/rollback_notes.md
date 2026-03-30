# Rollback notes

Prefer reverting through version control and the same reviewed deployment workflow.

## Security groups should not allow ingress from 0.0.0.0/0 or ::/0 to port 22
- Action ID: `dfa0a526-87b8-4670-92d7-401a611f58f5`
- Control ID: `EC2.53`
- Target: `696505809372|eu-north-1|arn:aws:ec2:eu-north-1:696505809372:security-group/sg-0ef32ca8805a55a8b|EC2.53`
- Rollback command: `python3 ./rollback/sg_restore.py`
