# Customer Onboarding Guide

Welcome to AWS Security Autopilot! This guide helps you get started with securing your AWS infrastructure.

## What is AWS Security Autopilot?

AWS Security Autopilot is a SaaS platform that:
- **Ingests security findings** from AWS Security Hub, GuardDuty, IAM Access Analyzer, and Inspector
- **Converts findings into prioritized actions** — Deduplicates and groups related findings
- **Manages exceptions** — Suppress false positives with expiry dates and approvals
- **Executes remediation** — Safe direct fixes or Infrastructure-as-Code PR bundles
- **Generates evidence packs** — SOC 2 / ISO-ready compliance reports

## Quick Start

1. **[Create Account](account-creation.md)** — Sign up and log in
2. **[Connect AWS Account](connecting-aws.md)** — Deploy IAM roles in your AWS account
3. **[Complete Onboarding](features-walkthrough.md#onboarding-wizard)** — Follow the onboarding wizard
4. **[View Findings](features-walkthrough.md#findings-page)** — See your security findings
5. **[Review Actions](features-walkthrough.md#actions-page)** — Prioritized actions to fix
> ⚠️ Status: Planned — not yet implemented
> `features-walkthrough.md` is planned and not present yet.

## Getting Help

- **[Troubleshooting](troubleshooting.md)** — Common issues and solutions
- **Support**: Contact support@yourcompany.com
- **[API Documentation](../api/README.md)** — For technical integrations
> ⚠️ Status: Planned — not yet implemented
> `../api/README.md` is part of the planned `docs/api/` documentation area.

## Documentation

- **[Account Creation](account-creation.md)** — Signup, login, invites
- **[Connecting AWS](connecting-aws.md)** — AWS account connection steps
- **[Features Walkthrough](features-walkthrough.md)** — Complete feature guide
- **[Team Management](team-management.md)** — User invites and roles
- **[Billing](billing.md)** — Subscription and billing
- **[Troubleshooting](troubleshooting.md)** — FAQs and common issues
> ⚠️ Status: Planned — not yet implemented
> `features-walkthrough.md`, `team-management.md`, and `billing.md` are planned and not present yet.

---

## Core Concepts

### Findings vs Actions

- **Findings** — Raw security issues from AWS services (Security Hub, GuardDuty, etc.)
- **Actions** — Prioritized, deduplicated tasks derived from findings

### Remediation Modes

- **Direct Fix** — Safe, automated fixes (e.g., enable S3 public access block)
- **PR Bundle** — Infrastructure-as-Code patches (Terraform/CloudFormation) for you to review and apply

### Exceptions

Suppress false positives with:
- **Reason** — Why this finding is acceptable
- **Expiry date** — When to re-evaluate
- **Approval** — Who approved the exception

---

## Next Steps

After completing onboarding:

1. **Review findings** — Understand your security posture
2. **Create exceptions** — Suppress false positives
3. **Approve remediations** — Fix security issues
4. **Generate evidence packs** — Export compliance reports
5. **Invite team members** — Collaborate on security

---

## Support

- **Email**: support@yourcompany.com
- **Documentation**: [Full Documentation Index](../README.md)
- **Troubleshooting**: [Troubleshooting Guide](troubleshooting.md)
