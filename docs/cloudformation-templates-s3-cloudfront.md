# CloudFormation Templates: S3 + CloudFront (Versioned)

This document describes how to host CloudFormation templates for the SaaS so customers get **one-click "Launch Stack"** links instead of downloading files.

## Approach

### 1. S3 bucket + CloudFront (public, versioned)

- **Put templates in an S3 bucket** (in your SaaS account).
- **Put CloudFront in front** for:
  - Stable HTTPS domain
  - Caching
  - Nice URLs

**Access:**

- Make templates **public-read**, or use a **bucket policy** allowing `s3:GetObject` for the template prefixes only.

**Versioning:**

- **Version the path; do not overwrite files:**
  - `.../cloudformation/read-role/v1.0.0.yaml`
  - `.../cloudformation/sqs-queues/v1.0.0.yaml`

**Why this is best:**

- CloudFormation can always fetch the template by URL.
- You can update templates without breaking existing customers (new versions = new paths).
- You can keep a changelog per version.
- Easy one-click deploy from the UI.

### 2. Generate a "Launch Stack" link in the UI

- Store the **tenant external ID** (already in DB).
- **Screen A — Connect AWS:** One screen with (1) Deploy Read Role: SaaS Account ID + External ID (copy), "Deploy Read Role" button. (2) Paste Role ARN & Validate: Role ARN input (account ID auto-parsed from ARN), AWS Account ID, Regions, Validate button. Backend validates via STS AssumeRole + GetCallerIdentity; status becomes validated.
- **Screen B — Connected Accounts:** Table: Account ID, Role ARN, Regions, Status, Last Validated; per-row actions Validate + Refresh Findings.
- Buttons: **Deploy Read Role** (and optionally **Deploy Queues** if you use customer-deployed SQS; many SaaS keep SQS in their account).

**CloudFormation console** supports prefilled parameters via URL. At minimum you can link to the console with the template URL; users fill parameters in the console. We pre-fill:

- `templateURL` — CloudFront URL to the template (e.g. `https://d123.cloudfront.net/cloudformation/read-role/v1.0.0.yaml`)
- `param_SaaSAccountId` — your SaaS AWS account ID
- `param_ExternalId` — the tenant’s external ID

**In the UI we show:**

- **SaaS Account ID** (your account ID) — copy/paste if needed.
- **External ID** (their external id) — copy/paste if needed.
- **Deploy Read Role** — opens the CloudFormation console with template and params prefilled.

## Configuration

Set in the SaaS backend (env or Secrets Manager):

- `SAAS_AWS_ACCOUNT_ID` — your 12-digit AWS account ID (used in ReadRole trust and in Launch Stack URL).
- `CLOUDFORMATION_READ_ROLE_TEMPLATE_URL` — full HTTPS URL to the Read Role template (e.g. CloudFront: `https://d123.cloudfront.net/cloudformation/read-role/v1.0.0.yaml`).
- `CLOUDFORMATION_DEFAULT_REGION` — default region for the Launch Stack console link (e.g. `us-east-1`).

When `CLOUDFORMATION_READ_ROLE_TEMPLATE_URL` is set, the API includes `saas_account_id` and `read_role_launch_stack_url` in:

- `GET /api/auth/me`
- Login and signup responses
- Accept-invite response

The frontend uses these to show SaaS Account ID, External ID, and the **Deploy Read Role** button on:

- **Onboarding** (step 2: Deploy the Read Role)
- **Settings → Organization**

## Launch Stack URL format

The backend builds the AWS CloudFormation "Create stack" console URL with query params:

- `stackName` — e.g. `SecurityAutopilotReadRole`
- `templateURL` — the CloudFront (or S3) template URL
- `param_SaaSAccountId` — SaaS account ID
- `param_ExternalId` — tenant external ID

Example (conceptually):

`https://us-east-1.console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/new?stackName=SecurityAutopilotReadRole&templateURL=...&param_SaaSAccountId=123456789012&param_ExternalId=ext-xxx`

## Changelog / versions

When you release a new template:

1. Upload the new file under a new version path (e.g. `v1.0.1.yaml`).
2. Update `CLOUDFORMATION_READ_ROLE_TEMPLATE_URL` in the environment to point to the new version (or keep the previous URL for existing links and use the new URL for new tenants — your choice).
3. Document changes in your internal changelog.

Existing customer links continue to use the old URL until you change the env; new users get the new URL from `/api/auth/me`.
