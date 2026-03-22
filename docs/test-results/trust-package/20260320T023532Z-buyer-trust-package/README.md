# Buyer Trust Package Evidence

This package was generated from the current repo-shipped ReadRole template plus sanitized live/retained evidence.

- Repo ReadRole template version: `v1.5.9`
- Customer account in retained authoritative source: `696505809372`
- Customer ReadRole ARN in retained authoritative source: `arn:aws:iam::696505809372:role/SecurityAutopilotReadRole`
- Fresh sanitized CloudTrail AssumeRole matches captured: `2`
- Customer-side authoritative source run: `/Users/marcomaher/AWS Security Autopilot/docs/test-results/live-runs/20260320T003851Z-issue2-live-closure-rerun`

## Contents

- `rendered/` — current repo-rendered policy documents derived from the checked-in CloudFormation template
- `validation/` — fresh IAM Access Analyzer validation output for the current ReadRole and the deprecated WriteRole appendix
- `evidence/` — sanitized customer-side retained evidence and fresh SaaS-side CloudTrail AssumeRole extracts
- `summary.json` — machine-readable index of the generated package
